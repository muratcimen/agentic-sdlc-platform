import tempfile
import unittest
from pathlib import Path

from app.plan import create_plan, discover_files


class PlanTests(unittest.TestCase):
    def test_discovery_is_read_only_and_finds_account_service(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            source = repository / "AccountService.java"
            source.write_text("class AccountService { void transferLimit() {} }")
            before = source.read_text()

            candidates = discover_files(repository, "daily transfer limit")

            self.assertEqual(["AccountService.java"], [item.path for item in candidates])
            self.assertEqual(before, source.read_text())

    def test_fallback_plan_requires_human_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = create_plan(
                "Plan a daily transfer limit",
                Path(directory),
                endpoint="http://127.0.0.1:1",
            )

            self.assertEqual("plan-only", plan["mode"])
            self.assertTrue(plan["humanApprovalRequired"])
            self.assertNotIn("patch", plan)


if __name__ == "__main__":
    unittest.main()
