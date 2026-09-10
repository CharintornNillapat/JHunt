# notifier.py
import html
import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()


class TelegramNotifier:
    # Telegram allows roughly 20 messages/minute to a single chat. One second
    # between sends keeps us comfortably under that without stretching a typical
    # run. Enforced inside send() so every caller is covered, not just the
    # pipeline loop in main.notify_jobs().
    MIN_SEND_INTERVAL = 1.0

    # Guard against a hostile or absurd retry_after stalling a CI run.
    MAX_RETRY_AFTER = 60

    TIMEOUT = 10

    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")

        if not self.token or not self.chat_id:
            raise ValueError("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing from .env")

        self.base_url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        self._last_sent: float | None = None

    def _throttle(self):
        """Sleeps just long enough to keep sends MIN_SEND_INTERVAL apart."""
        if self._last_sent is None:
            return
        elapsed = time.monotonic() - self._last_sent
        remaining = self.MIN_SEND_INTERVAL - elapsed
        if remaining > 0:
            time.sleep(remaining)

    @staticmethod
    def _describe_error(response: requests.Response) -> str:
        """
        Pulls Telegram's own error text out of the response body.

        A failed call returns {"ok": false, "description": "..."} which says
        exactly what went wrong ("can't parse entities...", "chat not found").
        Far more useful than the bare HTTPError string.
        """
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

        Retries once on HTTP 429, honouring the retry_after Telegram supplies.
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
                print(f"[Notifier] Request failed: {e}")
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
                print(f"[Notifier] Rate limited; retrying in {retry_after}s")
                time.sleep(retry_after)
                continue

            print(f"[Notifier] Failed to send message: {self._describe_error(response)}")
            return False

        return False

    def send_job_alert(self, title: str, company: str, url: str,
                       location: str = "", salary: str = "",
                       work_type: str = "") -> bool:
        """
        Formats a structured job alert and sends it.

        Every dynamic field is HTML-escaped. Titles routinely contain characters
        that are markup to Telegram — 'Developer (C++ & Python)', 'Dev <Remote>' —
        and an unescaped one returns HTTP 400, silently losing the alert.
        The rendered layout is unchanged from the Markdown version.
        """
        esc_title = html.escape(title)
        esc_company = html.escape(company)
        esc_url = html.escape(url, quote=True)

        lines = [
            f"🚨 <b>New Job Alert</b>\n",
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


if __name__ == "__main__":
    notifier = TelegramNotifier()

    cases = [
        {
            "title": "Senior Python Engineer",
            "company": "Acme Corp",
            "url": "https://th.jobsdb.com/job/12345",
            "location": "Bangkok",
            "salary": "100,000 - 150,000 THB",
            "work_type": "Full-time / Hybrid",
        },
        # Regression case: every one of these characters is markup to Telegram
        # and returned HTTP 400 under the old unescaped Markdown mode.
        {
            "title": "Developer (C++ & Python) <Urgent> *Rockstar* [Remote]",
            "company": "<Test & Co> — 100% \"Legit\"",
            "url": "https://th.jobsdb.com/job/67890",
            "location": "กรุงเทพ & Nonthaburi",
            "salary": "฿40,000 – ฿60,000 per month",
            "work_type": "Full time / On-site",
        },
    ]

    results = []
    for case in cases:
        ok = notifier.send_job_alert(**case)
        results.append(ok)
        print(f"{'sent ' if ok else 'FAILED'} | {case['title']}")

    print("\nMessage sent!" if all(results) else "\nSomething went wrong.")
