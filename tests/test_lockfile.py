import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class TestLockfileTargetsCiPython(unittest.TestCase):
    def test_lock_compiled_for_ci_python_version(self):
        workflow = (ROOT / ".github" / "workflows" / "scraper_cron.yml").read_text(encoding="utf-8")
        lock_header = "\n".join((ROOT / "requirements.lock").read_text(encoding="utf-8").splitlines()[:5])

        ci = re.search(r"uv python install (\d+\.\d+)", workflow)
        lock = re.search(r"--python-version (\d+\.\d+)", lock_header)

        self.assertIsNotNone(ci, "CI workflow no longer pins a Python via 'uv python install'")
        self.assertIsNotNone(lock, "requirements.lock was compiled without --python-version")
        self.assertEqual(lock.group(1), ci.group(1))


if __name__ == "__main__":
    unittest.main()
