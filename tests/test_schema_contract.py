import json
import tempfile
import unittest
from pathlib import Path

from app.plan import REQUIRED_PLAN_KEYS, _fallback_plan, discover_files

SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "agent-contracts"
    / "plan-output.schema.json"
)


class SchemaContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    def test_schema_required_keys_match_plan_contract(self):
        self.assertEqual(
            set(self.schema["required"]),
            REQUIRED_PLAN_KEYS | {"request", "mode"},
        )

    def test_schema_declares_every_required_property(self):
        self.assertTrue(REQUIRED_PLAN_KEYS.issubset(self.schema["properties"]))
        self.assertIn("request", self.schema["properties"])
        self.assertIn("mode", self.schema["properties"])
        self.assertTrue(self.schema["additionalProperties"] is False)

    def test_schema_enforces_read_only_guarantees(self):
        properties = self.schema["properties"]
        self.assertEqual("plan-only", properties["mode"]["const"])
        self.assertIs(True, properties["humanApprovalRequired"]["const"])
        self.assertEqual(
            ["READY_FOR_REVIEW", "BLOCKED_BY_REPOSITORY_EVIDENCE"],
            properties["status"]["enum"],
        )
        self.assertIs(True, properties["repositoryEvidence"]["properties"]["readOnly"]["const"])

    def test_fallback_plan_satisfies_schema_required_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = _fallback_plan("Plan a daily transfer limit", [], None)

        for key in self.schema["required"]:
            self.assertIn(key, plan)
        for key in plan:
            self.assertIn(key, self.schema["properties"])
        self.assertEqual("plan-only", plan["mode"])
        self.assertIs(True, plan["humanApprovalRequired"])
        self.assertIn(plan["status"], self.schema["properties"]["status"]["enum"])

    def test_model_prompt_requests_every_contract_key(self):
        source = (Path(__file__).resolve().parents[1] / "app" / "plan.py").read_text(
            encoding="utf-8"
        )
        prompt_start = source.index("prompt = f")
        prompt_end = source.index("try:", prompt_start)
        prompt_section = source[prompt_start:prompt_end]
        for key in REQUIRED_PLAN_KEYS:
            if key in {"repositoryEvidence", "humanApprovalRequired", "status"}:
                continue
            self.assertIn(key, prompt_section, f"prompt does not mention {key}")

    def test_discovery_uses_shared_candidate_terms(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            source = repository / "TransferService.java"
            source.write_text("class TransferService { void transfer() {} }")

            candidates = discover_files(repository, "havale limiti ekle")

            self.assertEqual(["TransferService.java"], [item.path for item in candidates])


if __name__ == "__main__":
    unittest.main()
