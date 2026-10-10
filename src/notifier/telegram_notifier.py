# src/notifier/telegram_notifier.py
"""
Telegram notification client with HTML formatting, throttling,
job alert dispatching, and Daily Market Intelligence Brief reporting.
"""
from __future__ import annotations

import html
import logging
import os
import time
from typing import Any, List, Optional

import requests
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class TelegramNotifier:
    """
    Sends HTML-escaped job alerts and market briefs to Telegram.
    Enforces a minimum interval between sends and retries on 429.
    """

    MIN_SEND_INTERVAL = 1.0
    MAX_RETRY_AFTER = 60
    TIMEOUT = 10

    def __init__(
        self,
        token: Optional[str] = None,
        chat_id: Optional[str] = None,
    ):
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")

        if not self.token or not self.chat_id:
            raise ValueError("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing from environment")

        self.base_url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        self._last_sent: Optional[float] = None

    def _throttle(self) -> None:
        """Sleeps just long enough to keep sends MIN_SEND_INTERVAL apart."""
        if self._last_sent is None:
            return
        elapsed = time.monotonic() - self._last_sent
        remaining = self.MIN_SEND_INTERVAL - elapsed
        if remaining > 0:
            time.sleep(remaining)

    @staticmethod
    def _describe_error(response: requests.Response) -> str:
        """Extracts Telegram's error description from the response body."""
        try:
            body = response.json()
        except ValueError:
            return f"HTTP {response.status_code}: {response.text[:200]}"
        description = body.get("description") or "(no description)"
        return f"HTTP {response.status_code}: {description}"

    def send(self, message: str) -> bool:
        """
        Sends an HTML-formatted message to Telegram.
        Returns True on success, False on failure.
        """
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

        for attempt in (1, 2):
            self._throttle()
            try:
                response = requests.post(self.base_url, json=payload, timeout=self.TIMEOUT)
            except requests.exceptions.RequestException as e:
                logger.error(f"[TelegramNotifier] Outbound request failed: {e}")
                return False
            finally:
                self._last_sent = time.monotonic()

            if response.ok:
                return True

            if response.status_code == 429 and attempt == 1:
                try:
                    retry_after = response.json().get("parameters", {}).get("retry_after", 1)
                except ValueError:
                    retry_after = 1
                retry_after = min(int(retry_after or 1), self.MAX_RETRY_AFTER)
                logger.warning(f"[TelegramNotifier] Rate limited; retrying in {retry_after}s")
                time.sleep(retry_after)
                continue

            logger.error(f"[TelegramNotifier] Failed to send message: {self._describe_error(response)}")
            return False

        return False

    def send_job_alert(
        self,
        title: str,
        company: str,
        url: str,
        location: str = "",
        salary: str = "",
        work_type: str = "",
    ) -> bool:
        """
        Formats a structured job alert and dispatches it with HTML escaping.
        """
        esc_title = html.escape(title)
        esc_company = html.escape(company)
        esc_url = html.escape(url, quote=True)

        lines = [
            "🚨 <b>New Job Alert</b>\n",
            f"<b>{esc_title}</b>",
            f"🏢 {esc_company}",
        ]

        if location:
            lines.append(f"📍 {html.escape(location)}")
        if salary:
            lines.append(f"💰 {html.escape(salary)}")
        if work_type:
            lines.append(f"🕐 {html.escape(work_type)}")

        lines.append(f'🔗 <a href="{esc_url}">View Job</a>')

        return self.send("\n".join(lines))

    def send_market_brief(
        self,
        top_pairs: List[tuple[str, str]],
        generated_title: Optional[str] = None,
        role: Optional[str] = None,
        total_analyzed: int = 0,
    ) -> bool:
        """
        Sends a compact Daily Market Intelligence Brief summarizing
        dominant tech co-occurrences and newly generated portfolio blueprints.
        """
        lines = [
            "📊 <b>Thailand Tech Market Intelligence Brief</b>\n",
        ]

        if total_analyzed > 0:
            lines.append(f"Analyzed {total_analyzed} active tech job postings in Thailand.\n")

        if top_pairs:
            lines.append("🔥 <b>Top Co-occurring Tech Stacks:</b>")
            for pair in top_pairs[:4]:
                t1, t2 = html.escape(pair[0]), html.escape(pair[1])
                lines.append(f"• <b>{t1}</b> + <b>{t2}</b>")
            lines.append("")

        if generated_title and role:
            esc_title = html.escape(generated_title)
            esc_role = html.escape(role)
            lines.append("💡 <b>New Portfolio Blueprint Generated:</b>")
            lines.append(f"<b>{esc_title}</b>")
            lines.append(f"🎯 Target Role: <code>{esc_role}</code>")

        return self.send("\n".join(lines))
