# src/extractor/text_sanitizer.py
"""
Text sanitization utilities for Job Descriptions (JDs).
Strips HTML, boilerplate, non-technical noise (benefits, EEO clauses),
and normalizes whitespace while strictly preserving technical requirements,
tools, and responsibilities in English and Thai.
"""
from __future__ import annotations

import html
import re
from typing import Any, Dict, List


# Patterns for boilerplate sections to prune
BOILERPLATE_SECTION_PATTERNS = [
    # Benefits & Perks (EN & TH)
    r"(?i)(?:benefits|what we offer|our perks|employee benefits|compensation & benefits|สวัสดิการ|ผลประโยชน์ที่ได้รับ)\s*:?.*?(?=(?:requirements|qualifications|responsibilities|หน้าที่|คุณสมบัติ|\Z))",
    # EEO / Diversity statements
    r"(?i)(?:equal opportunity employer|we are an equal opportunity|diversity and inclusion|commitment to diversity|ความเท่าเทียมในการจ้างงาน).*?(?=\n\n|\Z)",
    # How to apply / Contact outro
    r"(?i)(?:how to apply|interested candidates|please send your (?:resume|cv)|apply now|ผู้สนใจสมัครงาน|กรุณาส่งเรซูเม่).*?(?=\n\n|\Z)",
]

# Line-level patterns for common noise
NOISE_LINE_PATTERNS = [
    r"(?i)^\s*(?:provident fund|health insurance|life insurance|dental insurance|กองทุนสำรองเลี้ยงชีพ|ประกันสุขภาพ|ประกันชีวิต|ประกันอุบัติเหตุ)\b.*$",
    r"(?i)^\s*(?:annual leave|vacation leave|sick leave|วันลาพักร้อน|วันหยุดประจำปี|โบนัสประจำปี|performance bonus)\b.*$",
    r"(?i)^\s*(?:free snacks|free coffee|company trip|outing|happy hour|ขนมและเครื่องดื่มฟรี)\b.*$",
    r"(?i)^\s*(?:social security|ประกันสังคม|flexible working hours|work from home allowance)\b.*$",
]


def clean_html(raw_html: str) -> str:
    """
    Strips HTML tags, converts line breaks/lists to spaces or newlines,
    and decodes HTML entities.
    """
    if not raw_html:
        return ""

    # Normalize HTML line breaks and list items
    text = re.sub(r"(?i)<br\s*/?>", "\n", raw_html)
    text = re.sub(r"(?i)</?p\s*>", "\n", text)
    text = re.sub(r"(?i)<li\s*>", "\n- ", text)
    text = re.sub(r"(?i)</?li\s*>", "\n", text)
    text = re.sub(r"(?i)</?(?:ul|ol|div|span|strong|b|em|i|h\d)\b[^>]*>", " ", text)

    # Remove any remaining HTML tags
    text = re.sub(r"<[^>]+>", " ", text)

    # Decode HTML entities (e.g. &amp;, &nbsp;, &gt;)
    text = html.unescape(text)

    # Normalize non-breaking spaces and unicode spaces
    text = text.replace("\u00a0", " ").replace("\u200b", "")

    # Normalize whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def strip_boilerplate(text: str) -> str:
    """
    Removes standard HR boilerplate, benefits, and EEO statements,
    while retaining requirements, responsibilities, and technical stacks.
    """
    if not text:
        return ""

    cleaned = text

    # Remove block-level boilerplate
    for pattern in BOILERPLATE_SECTION_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned, flags=re.DOTALL)

    # Filter out individual noise lines
    kept_lines: List[str] = []
    for line in cleaned.splitlines():
        line_stripped = line.strip()
        if not line_stripped:
            continue
        if any(re.match(pat, line_stripped) for pat in NOISE_LINE_PATTERNS):
            continue
        kept_lines.append(line_stripped)

    result = "\n".join(kept_lines)
    result = re.sub(r"\n\s*\n+", "\n\n", result)
    return result.strip()


def build_sanitized_job_prompt(job: Dict[str, Any], max_chars: int = 2500) -> str:
    """
    Constructs a compact, high-signal representation of the job description
    ready for LLM extraction, respecting token quotas.
    """
    title = clean_html(str(job.get("title") or ""))
    company = clean_html(str(job.get("company") or ""))
    location = clean_html(str(job.get("location") or ""))
    salary = clean_html(str(job.get("salary") or ""))

    # Raw content fields: teaser and bullet_points
    teaser = clean_html(str(job.get("teaser") or ""))
    teaser_clean = strip_boilerplate(teaser)

    bullet_points = job.get("bullet_points") or []
    cleaned_bullets: List[str] = []
    if isinstance(bullet_points, list):
        for b in bullet_points:
            cleaned_b = strip_boilerplate(clean_html(str(b)))
            if cleaned_b:
                cleaned_bullets.append(f"- {cleaned_b}")

    bullets_text = "\n".join(cleaned_bullets)

    # Assemble structured summary
    parts = [
        f"Title: {title}",
        f"Company: {company}",
    ]
    if location:
        parts.append(f"Location: {location}")
    if salary:
        parts.append(f"Salary: {salary}")
    if teaser_clean:
        parts.append(f"Summary: {teaser_clean}")
    if bullets_text:
        parts.append(f"Key Points:\n{bullets_text}")

    full_text = "\n\n".join(parts)
    if len(full_text) > max_chars:
        full_text = full_text[:max_chars] + "\n...[truncated for length]"

    return full_text
