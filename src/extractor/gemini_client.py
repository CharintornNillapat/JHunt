# src/extractor/gemini_client.py
"""
Unified Google Gemini Client & Resilience Module.
Provides shared client initialization, throttling delays, exponential backoff,
fallback model switching, and daily quota exhaustion detection.
"""
from __future__ import annotations

import logging
import os
import random
import re
import time
from typing import Any, Optional, Tuple, TypeVar

from google import genai
from google.genai import types
from pydantic import TypeAdapter

logger = logging.getLogger(__name__)

_UNSET = object()
# Static default. GEMINI_MODEL is read per instance in BaseGeminiService.__init__,
# so an env change after import (tests, notebooks) still takes effect.
DEFAULT_MODEL = "gemini-3.8-flash"
FALLBACK_MODEL = "gemini-2.5-flash"
DEFAULT_RATE_LIMIT_DELAY = 4.0  # Safe for 15 RPM free tier
MAX_RETRIES = 4
INITIAL_BACKOFF = 2.0
REQUEST_TIMEOUT_MS = 30_000
CIRCUIT_BREAK_AFTER = 3  # consecutive calls that exhausted every retry
R = TypeVar("R")


class DailyQuotaExhaustedError(Exception):
    """Raised when the Gemini free-tier daily request quota is completely exhausted."""
    pass


def is_daily_quota_exhausted(err_str: str) -> bool:
    """
    Detects whether an error message indicates the daily quota
    (e.g. GenerateRequestsPerDayPerProjectPerModel or long retry-after delay)
    has been exhausted, rather than a transient burst/RPM limit.
    """
    err_lower = err_str.lower()
    if "generaterequestsperday" in err_lower:
        return True
    if "quota" in err_lower or "exhausted" in err_lower or "429" in err_lower or "retry" in err_lower:
        if "per day" in err_lower or "daily" in err_lower:
            return True
        if re.search(r"retry\s+(?:in|after)\s+\d+\s*(?:h|hr|hour)", err_lower):
            return True
        min_match = re.search(r"retry\s+(?:in|after)\s+(\d+)\s*(?:m|min|minute)", err_lower)
        if min_match:
            try:
                if int(min_match.group(1)) >= 1:
                    return True
            except ValueError:
                return True
    return False


class TransientErrorInfo(tuple):
    """
    Tuple of (is_transient, is_503, is_rate_limit) that evaluates to bool(is_transient)
    in a boolean context and provides structured attribute access.
    """
    is_transient: bool
    is_503: bool
    is_rate_limit: bool
    is_504_or_deadline: bool

    def __new__(cls, is_transient: bool, is_503: bool, is_rate_limit: bool, is_504_or_deadline: bool = False):
        instance = super().__new__(cls, (is_transient, is_503, is_rate_limit))
        instance.is_transient = is_transient
        instance.is_503 = is_503
        instance.is_rate_limit = is_rate_limit
        instance.is_504_or_deadline = is_504_or_deadline
        return instance

    def __bool__(self) -> bool:
        return bool(self.is_transient)


def is_deadline_or_timeout_error(err: Any) -> bool:
    """
    Checks if an error indicates a 504 Gateway Timeout or DEADLINE_EXCEEDED.
    """
    err_str = str(err)
    err_lower = err_str.lower()
    return (
        "504" in err_str
        or "gateway timeout" in err_lower
        or "gateway_timeout" in err_lower
        or "deadline_exceeded" in err_lower
        or "deadline exceeded" in err_lower
    )


def is_transient_error(err: Any) -> TransientErrorInfo:
    """
    Determines whether an error is transient and checks error categories.
    Treats HTTP 504, 502, 500, DEADLINE_EXCEEDED, 429, and 503 as transient.
    Returns TransientErrorInfo(is_transient, is_503, is_rate_limit, is_504_or_deadline).
    """
    err_str = str(err)
    err_lower = err_str.lower()
    is_503 = "503" in err_str or "service unavailable" in err_lower or "unavailable" in err_lower
    is_rate_limit = (
        "429" in err_str
        or "resource_exhausted" in err_lower
        or "rate limit" in err_lower
        or "quota" in err_lower
    )
    is_504_or_deadline = is_deadline_or_timeout_error(err_str)
    is_server_error = (
        "500" in err_str
        or "502" in err_str
        or "bad gateway" in err_lower
        or "bad_gateway" in err_lower
        or "internal server error" in err_lower
        or "internal error" in err_lower
    )
    is_timeout = (
        is_504_or_deadline
        or "timeout" in err_lower
        or "timed out" in err_lower
    )
    is_transient = is_503 or is_rate_limit or is_504_or_deadline or is_server_error or is_timeout
    return TransientErrorInfo(is_transient, is_503, is_rate_limit, is_504_or_deadline)


_is_transient_error = is_transient_error


def calculate_backoff_sleep(
    is_503: bool,
    consecutive_503: int,
    current_backoff: float,
) -> Tuple[float, float]:
    """
    Computes sleep time with jitter for transient retries.
    Returns (sleep_seconds, next_backoff).
    """
    if is_503:
        wait_schedule = [5.0, 10.0, 20.0]
        base_wait = wait_schedule[min(max(consecutive_503 - 1, 0), len(wait_schedule) - 1)]
        jitter = random.uniform(0.5, 2.0)
        return base_wait + jitter, current_backoff
    else:
        jitter = random.uniform(0.2, 1.0)
        return current_backoff + jitter, current_backoff * 2.0


class BaseGeminiService:
    """
    Base service handling common Gemini client initialization, rate limiting,
    and throttling delays across extraction, ideation, and filtering.
    """

    _is_transient_error = staticmethod(is_transient_error)

    def __init__(
        self,
        api_key: Any = _UNSET,
        model: Optional[str] = None,
        rate_limit_delay: float = DEFAULT_RATE_LIMIT_DELAY,
        client: Any = _UNSET,
        model_name: Optional[str] = None,
    ):
        if api_key is _UNSET:
            self.api_key = (os.getenv("GEMINI_API_KEY") or "").strip()
        else:
            self.api_key = (api_key or "").strip()

        env_model = (os.getenv("GEMINI_MODEL") or "").strip()
        chosen_model = (model_name or model or env_model or DEFAULT_MODEL).strip()
        self.model = chosen_model
        self.model_name = chosen_model
        self.rate_limit_delay = rate_limit_delay
        self._last_call_time: float = 0.0
        self._consecutive_failures = 0

        if client is not _UNSET:
            self.client = client
        elif self.api_key:
            self.client = genai.Client(
                api_key=self.api_key,
                http_options=types.HttpOptions(timeout=REQUEST_TIMEOUT_MS),
            )
        else:
            self.client = None

    def _throttle(self) -> None:
        """Enforces a minimum pause between API calls to honor free tier quotas."""
        if self._last_call_time > 0:
            elapsed = time.monotonic() - self._last_call_time
            sleep_needed = self.rate_limit_delay - elapsed
            if sleep_needed > 0:
                time.sleep(sleep_needed)

    def _record_call(self) -> None:
        """Records timestamp of outbound call for throttling calculations."""
        self._last_call_time = time.monotonic()

    def _generate(self, contents: str, config: types.GenerateContentConfig, schema: type[R]) -> Optional[R]:
        """
        One structured call: retries, 503 / 504 model fallback, and a breaker that spans calls.
        `schema` is a Pydantic model or `list[Model]`; the response is validated against it.
        """
        adapter = TypeAdapter(schema)
        if not self.client:
            logger.warning(f"[{type(self).__name__}] No client configured; skipping generation.")
            return None

        if self._consecutive_failures >= CIRCUIT_BREAK_AFTER:
            raise DailyQuotaExhaustedError(
                f"Circuit open after {self._consecutive_failures} consecutive failed calls"
            )

        model, backoff, n503 = self.model, INITIAL_BACKOFF, 0
        tag = type(self).__name__
        for attempt in range(1, MAX_RETRIES + 1):
            self._throttle()
            self._record_call()
            try:
                resp = self.client.models.generate_content(model=model, contents=contents, config=config)
                raw = getattr(resp, "parsed", None)
                if raw is not None:
                    parsed = adapter.validate_python(raw)
                elif getattr(resp, "text", None):
                    parsed = adapter.validate_json(resp.text)
                else:
                    parsed = None
                if parsed is not None:
                    self._consecutive_failures = 0
                    return parsed
                logger.warning(f"[{tag}] Attempt {attempt}: empty response.")
            except Exception as e:
                err = str(e)
                if is_daily_quota_exhausted(err):
                    raise DailyQuotaExhaustedError(err) from e
                transient_info = is_transient_error(err)
                if not transient_info.is_transient:
                    logger.error(f"[{tag}] Non-transient error: {err[:200]}")
                    break
                is_503 = transient_info.is_503
                is_504_or_deadline = transient_info.is_504_or_deadline
                if is_503:
                    n503 += 1
                    if n503 >= 2 and model != FALLBACK_MODEL:
                        model = FALLBACK_MODEL
                elif is_504_or_deadline:
                    if model != FALLBACK_MODEL:
                        model = FALLBACK_MODEL
                if attempt < MAX_RETRIES:
                    sleep_s, backoff = calculate_backoff_sleep(is_503, n503, backoff)
                    logger.warning(
                        f"[{tag}] Transient error ({err[:120]}); retry {attempt}/{MAX_RETRIES} in {sleep_s:.1f}s on {model}."
                    )
                    time.sleep(sleep_s)
        self._consecutive_failures += 1
        return None
