# src/extractor/text_cleaner.py
"""
Deterministic text pre-cleaning and truncation utility for job descriptions.
Minimizes LLM prompt token usage and inference latency by removing HR boilerplate,
perks, welfare, contact information, and company overviews while preserving
core technical requirements and responsibilities in English and Thai.
"""
from __future__ import annotations

import html
import re
from typing import Optional


# Keywords that signal non-technical sections to strip
BOILERPLATE_START_RE = re.compile(
    r"^(?:[-*•#\s]+)?(?:"
    r"benefits|"
    r"welfare|"
    r"what we offer|"
    r"our perks|"
    r"perks|"
    r"about us|"
    r"about company|"
    r"about the company|"
    r"company overview|"
    r"how to apply|"
    r"employee benefits|"
    r"compensation & benefits|"
    r"equal opportunity employer|"
    r"สวัสดิการ|"
    r"สิทธิประโยชน์|"
    r"เกี่ยวกับบริษัท|"
    r"วิธีการสมัคร|"
    r"ข้อมูลติดต่อ|"
    r"ผลประโยชน์ที่ได้รับ|"
    r"ผู้สนใจสมัครงาน"
    r")(?:\s*:|\s*$)",
    re.IGNORECASE,
)

# Section headers that mark technical content (where boilerplate stripping halts)
TECHNICAL_HEADERS_RE = re.compile(
    r"(?:"
    r"requirements|"
    r"qualifications|"
    r"responsibilities|"
    r"technical skills|"
    r"key skills|"
    r"skills|"
    r"who you are|"
    r"what you will do|"
    r"what you'll do|"
    r"what you need|"
    r"what you'll need|"
    r"what we look for|"
    r"who we are looking for|"
    r"คุณสมบัติ|"
    r"หน้าที่|"
    r"ทักษะ|"
    r"ความรับผิดชอบ|"
    r"รายละเอียดงาน"
    r")",
    re.IGNORECASE,
)

# Line-level patterns for common perks, benefits, and HR noise
NOISE_LINE_PATTERNS = [
    r"(?i)^\s*(?:provident fund|health insurance|life insurance|dental insurance|กองทุนสำรองเลี้ยงชีพ|ประกันสุขภาพ|ประกันชีวิต|ประกันอุบัติเหตุ)\b.*$",
    r"(?i)^\s*(?:annual leave|vacation leave|sick leave|วันลาพักร้อน|วันหยุดประจำปี|โบนัสประจำปี|performance bonus)\b.*$",
    r"(?i)^\s*(?:free snacks|free coffee|company trip|outing|happy hour|ขนมและเครื่องดื่มฟรี)\b.*$",
    r"(?i)^\s*(?:social security|ประกันสังคม|flexible working hours|work from home allowance)\b.*$",
]


def clean_html(raw_html: str) -> str:
    """Strips HTML tags, decodes entities, and normalizes space."""
    if not raw_html:
        return ""
    text = re.sub(r"(?i)<br\s*/?>", "\n", raw_html)
    text = re.sub(r"(?i)</?p\s*>", "\n", text)
    text = re.sub(r"(?i)<li\s*>", "\n- ", text)
    text = re.sub(r"(?i)</?li\s*>", "\n", text)
    text = re.sub(r"(?i)</?(?:ul|ol|div|span|strong|b|em|i|h\d)\b[^>]*>", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = text.replace("\u00a0", " ").replace("\u200b", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def truncate_at_boundary(text: str, max_chars: int) -> str:
    """
    Truncates text to at most max_chars, preferentially cutting at line,
    sentence, or word boundaries.
    """
    if len(text) <= max_chars:
        return text

    chunk = text[:max_chars]
    min_threshold = int(max_chars * 0.7)

    # 1. Prefer line boundary (\n)
    last_nl = chunk.rfind("\n")
    if last_nl >= min_threshold:
        return chunk[:last_nl].rstrip()

    # 2. Prefer sentence boundary (. , .\n, .)
    last_period = max(chunk.rfind(". "), chunk.rfind(".\n"), chunk.rfind("."))
    if last_period >= min_threshold:
        return chunk[:last_period + 1].rstrip()

    # 3. Prefer word boundary (space)
    last_space = chunk.rfind(" ")
    if last_space >= min_threshold:
        return chunk[:last_space].rstrip()

    # 4. Fallback to any earlier line or space boundary
    if last_nl > 0:
        return chunk[:last_nl].rstrip()
    if last_space > 0:
        return chunk[:last_space].rstrip()

    return chunk.rstrip()


def clean_job_description(text: Optional[str], max_chars: int = 1500) -> str:
    """
    Pre-cleans and sanitizes a job description to minimize token usage:
    - Strips HTML markup and decodes entities.
    - Removes perks/welfare, company overviews, and application info (EN & TH).
    - Collapses redundant whitespace and blank lines.
    - Truncates to max_chars at a sentence or line boundary.
    """
    if not text:
        return ""
    if not isinstance(text, str):
        text = str(text)

    cleaned_html = clean_html(text)
    if not cleaned_html:
        return ""

    lines = cleaned_html.splitlines()
    kept = []
    stripping = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if not stripping and kept and kept[-1] != "":
                kept.append("")
            continue

        # Check if line re-enters a technical section
        if TECHNICAL_HEADERS_RE.search(stripped):
            stripping = False
            kept.append(stripped)
            continue

        # Check if line marks the start of a boilerplate section
        if BOILERPLATE_START_RE.match(stripped):
            stripping = True
            continue

        # Check line-level noise
        if any(re.match(pat, stripped) for pat in NOISE_LINE_PATTERNS):
            continue

        if not stripping:
            kept.append(stripped)

    result = "\n".join(kept)
    result = re.sub(r"\n{3,}", "\n\n", result).strip()

    if max_chars is not None and max_chars > 0 and len(result) > max_chars:
        result = truncate_at_boundary(result, max_chars)

    return result
