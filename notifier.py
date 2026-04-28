# notifier.py
import requests
import os
from dotenv import load_dotenv

load_dotenv()


class TelegramNotifier:
    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.base_url = f"https://api.telegram.org/bot{self.token}/sendMessage"

        if not self.token or not self.chat_id:
            raise ValueError("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing from .env")

    def send(self, message: str) -> bool:
        """
        Sends a Markdown-formatted message to Telegram.
        Returns True on success, False on failure.
        """
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        }

        try:
            response = requests.post(self.base_url, json=payload, timeout=10)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            print(f"[Notifier] Failed to send message: {e}")
            return False

    def send_job_alert(self, title: str, company: str, url: str) -> bool:
        """
        Formats a structured job alert and sends it.
        """
        message = (
            f"🚨 *New Job Alert*\n\n"
            f"*{title}*\n"
            f"🏢 {company}\n"
            f"🔗 [View Job]({url})"
        )
        return self.send(message)


if __name__ == "__main__":
    notifier = TelegramNotifier()
    success = notifier.send_job_alert(
        title="Senior Python Engineer",
        company="Acme Corp",
        url="https://th.jobsdb.com/job/12345"
    )
    print("Message sent!" if success else "Something went wrong.")