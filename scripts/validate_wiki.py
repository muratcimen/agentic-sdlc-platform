"""Validate task pages in the repository wiki."""

from __future__ import annotations

import re
import sys
from pathlib import Path

REQUIRED_HEADINGS = (
    "Status",
    "Objective",
    "Plan",
    "Verified result",
    "Test evidence",
    "Commit / PR",
    "Remaining gaps",
)
VALID_STATUSES = {"PLANNED", "IN_PROGRESS", "BLOCKED", "COMPLETED"}
PATH_PATTERN = re.compile(r"`([^`\n]+)`")
URL_PATTERN = re.compile(r"https://github\.com/[^/\s]+/[^/\s]+/(?:commit|pull)/[^\s)]+")
PATH_SUFFIXES = {".c", ".go", ".java", ".json", ".md", ".py", ".sql", ".ts", ".tsx", ".xml", ".yml", ".yaml"}


def _section(text: str, heading: str) -> str:
    match = re.search(
        rf"^## {re.escape(heading)}\s*$\n(.*?)(?=^## |\Z)",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    return match.group(1).strip() if match else ""


def validate_task(path: Path, repository: Path) -> list[str]:
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    for heading in REQUIRED_HEADINGS:
        if not re.search(rf"^## {re.escape(heading)}\s*$", text, re.MULTILINE):
            errors.append(f"{path}: missing required heading '## {heading}'")

    status = _section(text, "Status")
    if status not in VALID_STATUSES:
        errors.append(
            f"{path}: Status must be one of {', '.join(sorted(VALID_STATUSES))}"
        )

    for reference in PATH_PATTERN.findall(text):
        if reference.startswith(("http://", "https://")) or reference.startswith(
            ("<!--", "AP-", "path/to/")
        ):
            continue
        candidate = Path(reference)
        if (
            not ("/" in reference or "\\" in reference)
            or reference.startswith("/")
            or candidate.suffix.lower() not in PATH_SUFFIXES
        ):
            continue
        if candidate.is_absolute() or ".." in candidate.parts:
            errors.append(f"{path}: reference is not repository-relative: {reference}")
        elif not (repository / candidate).is_file():
            errors.append(f"{path}: referenced file does not exist: {reference}")

    if status == "COMPLETED":
        if not _section(text, "Test evidence"):
            errors.append(f"{path}: COMPLETED requires test evidence")
        if not URL_PATTERN.search(_section(text, "Commit / PR")):
            errors.append(f"{path}: COMPLETED requires a GitHub commit or PR link")
    return errors


def validate_wiki(repository: Path) -> list[str]:
    task_dir = repository / "docs" / "wiki" / "tasks"
    if not task_dir.is_dir():
        return [f"{task_dir}: task directory does not exist"]
    errors: list[str] = []
    for path in sorted(task_dir.glob("*.md")):
        errors.extend(validate_task(path, repository))
    if not list(task_dir.glob("*.md")):
        errors.append(f"{task_dir}: no task pages found")
    return errors


def main() -> int:
    repository = Path(__file__).resolve().parents[1]
    errors = validate_wiki(repository)
    if errors:
        print("\n".join(errors))
        return 1
    print("Wiki validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
