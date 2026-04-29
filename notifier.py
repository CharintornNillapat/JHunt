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

    def send_job_alert(self, title: str, company: str, url: str,
                       location: str = "", salary: str = "",
                       work_type: str = "") -> bool:
        """
        Formats a structured job alert and sends it.
        """
        lines = [
            f"🚨 *New Job Alert*\n",
            f"*{title}*",
            f"🏢 {company}",
        ]
        
        if location:  
            lines.append(f"📍 {location}")
        if salary:    
            lines.append(f"💰 {salary}")
        if work_type: 
            lines.append(f"🕐 {work_type}")
            
        lines.append(f"🔗 [View Job]({url})")

        return self.send("\n".join(lines))


if __name__ == "__main__":
    notifier = TelegramNotifier()
    success = notifier.send_job_alert(
        title="Senior Python Engineer",
        company="Acme Corp",
        url="https://th.jobsdb.com/job/12345",
        location="Bangkok",
        salary="100,000 - 150,000 THB",
        work_type="Full-time / Hybrid"
    )
    print("Message sent!" if success else "Something went wrong.")