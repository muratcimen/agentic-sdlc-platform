import tempfile
import unittest
from pathlib import Path

from app.evidence import analyze_repository


class EvidenceTests(unittest.TestCase):
    def test_extracts_real_java_and_sql_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            java = repository / "TransferService.java"
            java.write_text(
                """@Service
class TransferService {
  @Transactional
  public void transfer(Long accountId) {}
}
"""
            )
            sql = repository / "V4__transfer.sql"
            sql.write_text(
                "CREATE TABLE transfers (id BIGINT);"
                "CREATE UNIQUE INDEX uk_transfer_id ON transfers(id);"
            )

            report = analyze_repository(repository, "daily transfer limit")

            self.assertEqual("READY_FOR_REVIEW", report["status"])
            self.assertEqual(1, report["evidenceSummary"]["transactionalBoundaryCount"])
            self.assertEqual(2, report["evidenceSummary"]["schemaReferenceCount"])
            self.assertEqual("transfer", report["codeReferences"][1]["symbol"])
            self.assertTrue(report["readOnly"])
            self.assertEqual(java.read_text(), java.read_text())

    def test_blocks_when_transfer_evidence_is_absent(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            (repository / "Account.java").write_text("class Account {}")

            report = analyze_repository(repository, "daily transfer limit")

            self.assertEqual("BLOCKED_BY_REPOSITORY_EVIDENCE", report["status"])
            self.assertTrue(report["blockers"])

    def test_non_transfer_request_reaches_ready_for_review(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            (repository / "KycService.java").write_text(
                "@Service\n"
                "class KycService {\n"
                "  @Transactional\n"
                "  public void verifyCustomer(Long id) {}\n"
                "}\n"
            )
            (repository / "V1__kyc.sql").write_text(
                "CREATE TABLE kyc_checks (id BIGINT);"
            )

            report = analyze_repository(repository, "add kyc verification for customers")

            self.assertEqual("READY_FOR_REVIEW", report["status"])
            self.assertEqual([], report["blockers"])
            self.assertGreater(report["evidenceSummary"]["domainEvidenceCount"], 0)
            self.assertTrue(report["readOnly"])

    def test_transfer_request_cannot_pass_the_gate_without_transfer_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            (repository / "AccountService.java").write_text(
                "class AccountService { void transferLimit() {} }\n"
            )
            (repository / "V1__accounts.sql").write_text(
                "CREATE TABLE accounts (id BIGINT);"
            )

            report = analyze_repository(repository, "daily transfer limit")

            self.assertEqual("BLOCKED_BY_REPOSITORY_EVIDENCE", report["status"])
            self.assertTrue(any("domain" in item for item in report["blockers"]))


if __name__ == "__main__":
    unittest.main()
