# src/extractor/salary_parser.py
"""
Deterministic Salary Parser & Compensation Intelligence Engine.
Extracts normalized minimum, maximum, and currency from platform payloads
and unstructured job postings with strict sanity guardrails.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional, Tuple, Union

# Regex pre-compiled patterns
RE_EN_DASH = re.compile(r"[\u2013\u2014\u2212]")
RE_PHONE = re.compile(r"\b0\d{1,2}[-\s]?\d{3,4}[-\s]?\d{4}\b")
RE_POSTAL_CONTEXT = re.compile(r"(?i)(?:postal\s*code|postcode|zip\s*code|รหัสไปรษณีย์|แขวง|เขต|จ\.)\s*[:\s]*\d{5}\b")
RE_SALARY_ANCHOR = re.compile(
    r"(?i)(?:salary|เงินเดือน|ค่าตอบแทน|compensation|remuneration|รายได้|ค่าจ้าง|base\s*salary|offer)(?:\s*\([^)]*\))?\s*[:=\-\s]\s*",
    re.UNICODE,
)
RE_COUNT_NOUN = re.compile(
    r"(?i)^\s*(?:merchants?|users?|people|engineers?|customers?|clients?|members?|accounts?|คน|ร้านค้า|ท่าน)(?:\b|\s|$)",
    re.UNICODE,
)

# Normalization constants
HOURLY_HOURS_PER_MONTH = 160  # 40 hrs/wk * 4 weeks
DAILY_DAYS_PER_MONTH = 22     # 22 working days/month
MONTHS_PER_YEAR = 12

MIN_REALISTIC_THB = 15_000
MAX_REALISTIC_THB = 1_000_000

MIN_REALISTIC_USD = 500
MAX_REALISTIC_USD = 30_000


def _normalize_text(text: str) -> str:
    """Standardizes dashes, currency symbols, and Thai formatting."""
    if not text:
        return ""
    # Normalize Unicode dashes to standard hyphen
    t = RE_EN_DASH.sub("-", text)
    # Strip .- common in Thai prices (e.g. 50,000.-)
    t = re.sub(r"\.-", "", t)
    return t.strip()


def _detect_currency(text: str) -> str:
    """Detects compensation currency ISO code, defaulting to THB."""
    lower = text.lower()
    if any(k in lower for k in ("usd", "$", "dollar", "us dollar")):
        return "USD"
    if any(k in lower for k in ("eur", "€", "euro")):
        return "EUR"
    if any(k in lower for k in ("sgd", "s$", "singapore dollar")):
        return "SGD"
    if any(k in lower for k in ("gbp", "£", "pound")):
        return "GBP"
    if any(k in lower for k in ("jpy", "¥", "yen")):
        return "JPY"
    return "THB"


def _detect_period(text: str) -> str:
    """Detects pay frequency (hourly, daily, yearly, or default monthly)."""
    lower = re.sub(r"\s+", " ", text.lower())
    if re.search(r"(?:/\s*(?:hr|hour|ชม|ชั่วโมง)|per\s+hour|ต่อ\s*ชั่วโมง|ต่อ\s*ชม)", lower):
        return "hourly"
    if re.search(r"(?:/\s*day|per\s+day|ต่อ\s*วัน)", lower):
        return "daily"
    if re.search(r"(?:/\s*(?:year|yr|annum)|per\s+(?:year|annum)|ต่อ\s*ปี|annually|yearly)", lower):
        return "yearly"
    return "monthly"


def _get_local_context(norm: str, match_start: int, match_end: int) -> str:
    """Extracts narrow surrounding window around a match, bounded by sentence delimiters."""
    prefix = norm[max(0, match_start - 25) : match_start]
    delim_idx = max(prefix.rfind("."), prefix.rfind(";"), prefix.rfind("\n"))
    if delim_idx != -1:
        prefix = prefix[delim_idx + 1 :]

    suffix = norm[match_end : min(len(norm), match_end + 35)]
    delim_match = re.search(r"[.;\n]|\s{2,}", suffix)
    if delim_match:
        suffix = suffix[: delim_match.start()]

    return prefix + norm[match_start:match_end] + suffix


def _parse_number_token(token: str, context_has_k: bool = False) -> Optional[int]:
    """
    Parses number tokens such as '50,000', '30k', '1.2m', or '40' (with context_has_k).
    Returns integer value or None if invalid.
    """
    cleaned = token.replace(",", "").replace(" ", "").strip()
    if not cleaned:
        return None

    # e.g., 30k, 50K
    if cleaned[-1] in ("k", "K"):
        try:
            return int(float(cleaned[:-1]) * 1_000)
        except ValueError:
            return None

    # e.g., 1.2m, 1M
    if cleaned[-1] in ("m", "M"):
        try:
            return int(float(cleaned[:-1]) * 1_000_000)
        except ValueError:
            return None

    try:
        val = float(cleaned)
        if context_has_k and val < 1_000:
            return int(val * 1_000)
        return int(val)
    except ValueError:
        return None


def _apply_period_multiplier(val: Optional[int], period: str) -> Optional[int]:
    """Converts hourly, daily, or annual figures into monthly figures."""
    if val is None:
        return None
    if period == "hourly":
        return int(round(val * HOURLY_HOURS_PER_MONTH))
    if period == "daily":
        return int(round(val * DAILY_DAYS_PER_MONTH))
    if period == "yearly":
        return int(round(val / MONTHS_PER_YEAR))
    return val


def _is_realistic(val: Optional[int], currency: str) -> bool:
    """Sanity guardrail rejecting values outside realistic monthly tech thresholds."""
    if val is None:
        return True
    if currency == "THB":
        return MIN_REALISTIC_THB <= val <= MAX_REALISTIC_THB
    if currency in ("USD", "EUR", "SGD", "GBP"):
        return 300 <= val <= 100_000
    if currency == "JPY":
        return 100_000 <= val <= 15_000_000
    return MIN_REALISTIC_THB <= val <= MAX_REALISTIC_THB


def _extract_from_platform_payload(payload: Union[str, Dict[str, Any]]) -> Optional[Tuple[Optional[int], Optional[int], str]]:
    """Checks for structured platform payloads (dict or JSON string)."""
    data = None
    if isinstance(payload, dict):
        data = payload
    elif isinstance(payload, str) and payload.strip().startswith("{") and payload.strip().endswith("}"):
        try:
            data = json.loads(payload)
        except Exception:
            data = None

    if not isinstance(data, dict):
        return None

    currency = str(data.get("currency") or "THB").upper()

    min_raw = data.get("min") or data.get("min_salary") or data.get("from") or data.get("minimum")
    max_raw = data.get("max") or data.get("max_salary") or data.get("to") or data.get("maximum")

    min_val = None
    max_val = None
    if min_raw is not None:
        try:
            min_val = int(float(str(min_raw).replace(",", "").strip()))
        except (ValueError, TypeError):
            pass
    if max_raw is not None:
        try:
            max_val = int(float(str(max_raw).replace(",", "").strip()))
        except (ValueError, TypeError):
            pass

    if min_val is not None and not _is_realistic(min_val, currency):
        min_val = None
    if max_val is not None and not _is_realistic(max_val, currency):
        max_val = None

    if min_val is not None and max_val is not None and min_val > max_val:
        min_val, max_val = max_val, min_val

    if min_val is not None or max_val is not None:
        return min_val, max_val, currency
    return None


def _extract_from_text(text: str) -> Tuple[Optional[int], Optional[int], str]:
    """Scans free text for salary ranges, upper/lower bounds, and individual salaries."""
    norm = _normalize_text(text)
    if not norm:
        return None, None, "THB"

    # Fast rejection: purely non-disclosed boilerplate strings
    lower = norm.lower()
    if lower in ("negotiable", "ตามตกลง", "not specified", "unspecified", "ตามโครงสร้างบริษัท", "competitive", "none", "n/a"):
        return None, None, "THB"

    # 1. Range Pattern: e.g. 50,000 - 80,000, 30k - 50k, 30 - 50k, ฿23,000 - ฿25,000
    range_regex = re.compile(
        r"(?:฿|THB|\$)?\s*"
        r"(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?[kKmM]?|\d{5,7})\s*"
        r"(?:-|to|ถึง|~)\s*"
        r"(?:฿|THB|\$)?\s*"
        r"(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?[kKmM]?|\d{5,7})",
        re.IGNORECASE,
    )
    for match in range_regex.finditer(norm):
        trailing = norm[match.end() : match.end() + 35]
        if RE_COUNT_NOUN.search(trailing):
            continue

        num1_str = match.group(1).strip()
        num2_str = match.group(2).strip()

        # Reject phone numbers (e.g. 081-1234567 or 02-1234567)
        if num1_str.startswith("0") and not num1_str.lower().endswith(("k", "m")):
            continue

        local_ctx = _get_local_context(norm, match.start(), match.end())
        curr = _detect_currency(local_ctx)
        period = _detect_period(local_ctx)

        has_k = num2_str.lower().endswith("k") or "k" in norm[match.start():match.end()].lower()
        val1 = _parse_number_token(num1_str, context_has_k=has_k)
        val2 = _parse_number_token(num2_str, context_has_k=False)

        val1 = _apply_period_multiplier(val1, period)
        val2 = _apply_period_multiplier(val2, period)

        if val1 is not None and val2 is not None:
            if val1 > val2:
                val1, val2 = val2, val1
            if _is_realistic(val1, curr) and _is_realistic(val2, curr):
                return val1, val2, curr

    # 2. Up to / Max Only Pattern: e.g. Up to 120,000, สูงสุด 120,000, <= 100k
    max_regex = re.compile(
        r"(?:up\s*to|upto|maximum|max|สูงสุด|ไม่เกิน|<=|<)\s*"
        r"(?:฿|THB|\$)?\s*"
        r"(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?[kKmM]|\d{5,7})",
        re.IGNORECASE,
    )
    for match in max_regex.finditer(norm):
        trailing = norm[match.end() : match.end() + 35]
        if RE_COUNT_NOUN.search(trailing):
            continue

        local_ctx = _get_local_context(norm, match.start(), match.end())
        curr = _detect_currency(local_ctx)
        period = _detect_period(local_ctx)

        max_str = match.group(1).strip()
        max_val = _parse_number_token(max_str)
        max_val = _apply_period_multiplier(max_val, period)
        if max_val is not None and _is_realistic(max_val, curr):
            return None, max_val, curr

    # 3. From / Min Only Pattern: e.g. From 40,000, เริ่มต้น 40,000
    min_regex = re.compile(
        r"(?:starting\s+from|start\s+from|from|minimum|min|เริ่มต้น(?:ที่)?|ตั้งแต่|>=|>|more\s+than)\s*"
        r"(?:฿|THB|\$)?\s*"
        r"(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?[kKmM]|\d{5,7})",
        re.IGNORECASE,
    )
    for match in min_regex.finditer(norm):
        trailing = norm[match.end() : match.end() + 35]
        if RE_COUNT_NOUN.search(trailing):
            continue

        local_ctx = _get_local_context(norm, match.start(), match.end())
        curr = _detect_currency(local_ctx)
        period = _detect_period(local_ctx)

        min_str = match.group(1).strip()
        min_val = _parse_number_token(min_str)
        min_val = _apply_period_multiplier(min_val, period)
        if min_val is not None and _is_realistic(min_val, curr):
            return min_val, None, curr

    # Suffix + pattern: e.g. 40,000+, 40k+
    suffix_plus_regex = re.compile(
        r"(?:฿|THB|\$)?\s*"
        r"(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?[kKmM]|\d{5,7})\s*\+",
        re.IGNORECASE,
    )
    for match in suffix_plus_regex.finditer(norm):
        trailing = norm[match.end() : match.end() + 35]
        if RE_COUNT_NOUN.search(trailing):
            continue

        local_ctx = _get_local_context(norm, match.start(), match.end())
        curr = _detect_currency(local_ctx)
        period = _detect_period(local_ctx)

        min_str = match.group(1).strip()
        min_val = _parse_number_token(min_str)
        min_val = _apply_period_multiplier(min_val, period)
        if min_val is not None and _is_realistic(min_val, curr):
            return min_val, None, curr

    # 4. Single explicit salary with currency/period indicator (e.g. 60,000 THB / month, 500 THB/hr)
    single_regex = re.compile(
        r"(?:salary|เงินเดือน|ค่าตอบแทน|compensation)?\s*"
        r"(?:฿|THB|\$)?\s*"
        r"(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?[kKmM]|\d{2,7})\s*"
        r"(?:THB|บาท|฿|USD|\$|baht|\/\s*(?:month|mo|hr|hour|day|year|ชม|ชั่วโมง)|ต่อ\s*(?:เดือน|ชั่วโมง|ชม|วัน|ปี))",
        re.IGNORECASE,
    )
    for match in single_regex.finditer(norm):
        trailing = norm[match.end() : match.end() + 35]
        if RE_COUNT_NOUN.search(trailing):
            continue

        local_ctx = _get_local_context(norm, match.start(), match.end())
        curr = _detect_currency(local_ctx)
        period = _detect_period(local_ctx)

        val_str = match.group(1).strip()
        val = _parse_number_token(val_str)
        val = _apply_period_multiplier(val, period)
        if val is not None and _is_realistic(val, curr):
            return val, val, curr

    return None, None, "THB"


def parse_salary(
    raw_salary_text: Optional[Union[str, Dict[str, Any]]] = None,
    description: Optional[str] = None,
) -> Tuple[Optional[int], Optional[int], str]:
    """
    Deterministic salary extraction engine.
    Extracts (min_salary, max_salary, currency).
    - Platform Payload First: Check structured salary objects or JSON.
    - Regex Text Parsing: Parse raw_salary_text then description for standard Thai/English patterns.
    - Sanity Guardrails: Enforce realistic tech thresholds and reject year ranges, postal codes, and phone numbers.
    """
    # 1. Platform payload first
    if raw_salary_text:
        structured = _extract_from_platform_payload(raw_salary_text)
        if structured is not None:
            return structured

        if isinstance(raw_salary_text, str):
            min_s, max_s, curr = _extract_from_text(raw_salary_text)
            if min_s is not None or max_s is not None:
                return min_s, max_s, curr

    # 2. Inspect description for compensation patterns if header was undisclosed
    if description and isinstance(description, str):
        for anchor_match in RE_SALARY_ANCHOR.finditer(description):
            window = description[anchor_match.start() : anchor_match.end() + 150]
            min_s, max_s, curr = _extract_from_text(window)
            if min_s is not None or max_s is not None:
                return min_s, max_s, curr

    return None, None, "THB"
