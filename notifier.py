# notifier.py
"""
Backward compatibility bridge re-exporting TelegramNotifier from src.notifier.
"""
from src.notifier.telegram_notifier import TelegramNotifier

__all__ = ["TelegramNotifier"]

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
