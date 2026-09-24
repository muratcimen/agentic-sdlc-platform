import tempfile
import unittest
from pathlib import Path

from scripts.validate_wiki import validate_task


VALID_TASK = """# AP-001: Example

## Status

COMPLETED

## Objective

Build the thing.

## Plan

1. Do it.

## Verified result

It exists.

## Test evidence

`python3 -m unittest`

## Commit / PR

https://github.com/example/repo/commit/abc123

## Remaining gaps

None.

## Evidence

- `app/plan.py`
"""


class WikiValidatorTests(unittest.TestCase):
    def test_completed_task_with_evidence_and_link_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            (repository / "app").mkdir()
            (repository / "app" / "plan.py").write_text("pass", encoding="utf-8")
            task = repository / "task.md"
            task.write_text(VALID_TASK, encoding="utf-8")

            self.assertEqual([], validate_task(task, repository))

    def test_completed_task_requires_test_evidence_and_commit_link(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            task = repository / "task.md"
            task.write_text(
                VALID_TASK.replace("`python3 -m unittest`", "")
                .replace("https://github.com/example/repo/commit/abc123", ""),
                encoding="utf-8",
            )

            errors = validate_task(task, repository)

            self.assertIn("COMPLETED requires test evidence", "\n".join(errors))
            self.assertIn("COMPLETED requires a GitHub commit or PR link", "\n".join(errors))

    def test_referenced_repository_file_must_exist(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            task = repository / "task.md"
            task.write_text(VALID_TASK.replace("app/plan.py", "app/missing.py"), encoding="utf-8")

            errors = validate_task(task, repository)

            self.assertIn("referenced file does not exist: app/missing.py", "\n".join(errors))


if __name__ == "__main__":
    unittest.main()
