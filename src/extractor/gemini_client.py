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
from typing import Any, Optional, Tuple

from google import genai

logger = logging.getLogger(__name__)

_UNSET = object()
DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
FALLBACK_MODEL = "gemini-2.5-flash"
DEFAULT_RATE_LIMIT_DELAY = 4.0  # Safe for 15 RPM free tier
MAX_RETRIES = 4
INITIAL_BACKOFF = 2.0


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
    is_transient = is_503 or is_rate_limit or "timeout" in err_lower
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

        chosen_model = (model_name or model or os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)).strip()
        self.model = chosen_model
        self.model_name = chosen_model
        self.rate_limit_delay = rate_limit_delay
        self._last_call_time: float = 0.0

        if client is not _UNSET:
            self.client = client
        elif self.api_key:
            self.client = genai.Client(api_key=self.api_key)
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
