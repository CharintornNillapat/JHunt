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


def is_transient_error(err_str: str) -> Tuple[bool, bool, bool]:
    """
    Determines whether an error is transient and checks error categories.
    Returns (is_transient, is_503, is_rate_limit).
    """
    err_lower = err_str.lower()
    is_503 = "503" in err_str or "service unavailable" in err_lower or "unavailable" in err_lower
    is_rate_limit = (
        "429" in err_str
        or "resource_exhausted" in err_lower
        or "rate limit" in err_lower
        or "quota" in err_lower
    )
    is_transient = is_503 or is_rate_limit or "timeout" in err_lower or "timed out" in err_lower
    return is_transient, is_503, is_rate_limit


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
        One structured call: retries, 503 model fallback, and a breaker that spans calls.
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
                transient, is_503, _ = is_transient_error(err)
                if not transient:
                    logger.error(f"[{tag}] Non-transient error: {err[:200]}")
                    break
                if is_503:
                    n503 += 1
                    if n503 >= 2 and model != FALLBACK_MODEL:
                        model = FALLBACK_MODEL
                if attempt < MAX_RETRIES:
                    sleep_s, backoff = calculate_backoff_sleep(is_503, n503, backoff)
                    logger.warning(
                        f"[{tag}] Transient error ({err[:120]}); retry {attempt}/{MAX_RETRIES} in {sleep_s:.1f}s on {model}."
                    )
                    time.sleep(sleep_s)
        self._consecutive_failures += 1
        return None
