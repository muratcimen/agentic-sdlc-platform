from __future__ import annotations

import argparse
import json
import os
import re
import uuid
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from .evidence import analyze_repository


DEFAULT_MODEL = "qwen2.5-coder:1.5b"
IGNORED_PARTS = {".git", ".idea", "target", "__pycache__", ".mvn"}
TEXT_SUFFIXES = {".java", ".md", ".sql", ".xml", ".yml", ".yaml", ".properties"}
REQUIRED_PLAN_KEYS = {
    "summary",
    "missingInformation",
    "acceptanceCriteria",
    "filesToInspect",
    "proposedChanges",
    "humanApprovalRequired",
    "status",
    "currentFlow",
    "businessRuleContract",
    "domainDesign",
    "dataModel",
    "atomicTransactionFlow",
    "integrationAndAudit",
    "failureScenarios",
    "validation",
    "releasePlan",
    "decisionAlternatives",
    "invariants",
    "repositoryEvidence",
}


@dataclass(frozen=True)
class FileCandidate:
    path: str
    score: int
    matches: list[str]


def discover_files(repository: Path, request: str, limit: int = 12) -> list[FileCandidate]:
    terms = {
        term.lower()
        for term in re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]{2,}", request)
    }
    expansions = {
        "transfer": {"account", "deposit", "withdraw", "transaction"},
        "limit": {"account", "transaction", "service", "controller"},
        "günlük": {"account", "transaction", "service"},
        "limitini": {"account", "transaction", "service"},
    }
    for term in tuple(terms):
        terms.update(expansions.get(term, set()))
    candidates: list[FileCandidate] = []
    for path in repository.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if any(part in IGNORED_PARTS for part in path.parts):
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore").lower()
        except OSError:
            continue
        matches = sorted(term for term in terms if term in content or term in path.name.lower())
        if matches:
            candidates.append(
                FileCandidate(
                    path=path.relative_to(repository).as_posix(),
                    score=len(matches),
                    matches=matches,
                )
            )
    return sorted(candidates, key=lambda item: (-item.score, item.path))[:limit]


def _model_request(prompt: str, model: str, endpoint: str) -> str:
    payload = json.dumps(
        {"model": model, "prompt": prompt, "stream": False, "format": "json"}
    ).encode()
    request = urllib.request.Request(
        f"{endpoint.rstrip('/')}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        body = json.loads(response.read())
    return str(body["response"])


def _fallback_plan(
    request: str, files: list[FileCandidate], evidence: dict[str, Any] | None = None
) -> dict[str, Any]:
    return {
        "request": request,
        "summary": "Create a reviewed implementation plan without changing files.",
        "missingInformation": ["Exact daily limit value and account/customer scope."],
        "acceptanceCriteria": [
            "The applicable daily transfer limit is defined.",
            "Transfers over the limit are rejected without changing the balance.",
            "A rejected transfer is recorded in the audit trail.",
            "Unit and integration tests cover accepted, rejected, and concurrent transfers.",
        ],
        "filesToInspect": [asdict(candidate) for candidate in files],
        "proposedChanges": [
            "Identify the transfer domain service and transaction boundary.",
            "Define the limit policy and audit event contract.",
            "Add tests for the limit, rollback, audit, and concurrency behavior.",
        ],
        "humanApprovalRequired": True,
        "mode": "plan-only",
        "status": evidence["status"] if evidence else "BLOCKED_BY_REPOSITORY_EVIDENCE",
        "repositoryEvidence": evidence,
        "currentFlow": {
            "status": "unverified",
            "references": evidence.get("codeReferences", []) if evidence else [],
        },
        "businessRuleContract": {"status": "BLOCKED_BY_BUSINESS_DECISION"},
        "domainDesign": {"status": "unverified"},
        "dataModel": {
            "status": "unverified",
            "references": evidence.get("schemaReferences", []) if evidence else [],
        },
        "atomicTransactionFlow": {"status": "unverified"},
        "integrationAndAudit": {"status": "unverified"},
        "failureScenarios": {"status": "unverified"},
        "validation": {"status": "unverified"},
        "releasePlan": {"status": "unverified"},
        "decisionAlternatives": [],
        "invariants": [],
    }


def _validate_model_plan(plan: Any, inventory: set[str]) -> dict[str, Any]:
    if not isinstance(plan, dict) or not REQUIRED_PLAN_KEYS.issubset(plan):
        raise ValueError("Model returned an incomplete plan")
    if plan["humanApprovalRequired"] is not True:
        raise ValueError("Model plan must require human approval")
    paths = plan["filesToInspect"]
    if not isinstance(paths, list) or not all(
        isinstance(path, str) and path in inventory for path in paths
    ):
        raise ValueError("Model returned paths outside the repository inventory")
    return plan


def create_plan(
    request: str,
    repository: Path,
    model: str = DEFAULT_MODEL,
    endpoint: str = "http://127.0.0.1:11434",
) -> dict[str, Any]:
    if not repository.is_dir():
        raise ValueError(f"Repository does not exist: {repository}")
    files = discover_files(repository, request)
    evidence = analyze_repository(repository, request)
    if evidence["status"] == "BLOCKED_BY_REPOSITORY_EVIDENCE":
        return _fallback_plan(request, files, evidence)
    inventory = sorted(
        path.relative_to(repository).as_posix()
        for path in repository.rglob("*")
        if path.is_file()
        and path.suffix.lower() in TEXT_SUFFIXES
        and not any(part in IGNORED_PARTS for part in path.parts)
    )
    context = "\n".join(
        f"- {candidate.path} (matches: {', '.join(candidate.matches)})"
        for candidate in files
    ) or "- No matching text files were found."
    inventory_context = "\n".join(f"- {path}" for path in inventory[:80])
    prompt = f"""You are a read-only software planning assistant.
Do not invent file paths. Every filesToInspect path must exist in the repository inventory.
Return valid JSON with keys: summary, missingInformation, acceptanceCriteria,
filesToInspect, proposedChanges, tests, currentFlow, businessRuleContract,
domainDesign, dataModel, atomicTransactionFlow, integrationAndAudit,
failureScenarios, validation, releasePlan, decisionAlternatives, invariants,
status, repositoryEvidence, humanApprovalRequired.
The human must approve any future change.

Request:
{request}

Repository candidates:
{context}

Repository inventory:
{inventory_context}

Verified repository evidence:
{json.dumps(evidence, ensure_ascii=False)}
"""
    try:
        plan = json.loads(_model_request(prompt, model, endpoint))
        plan = _validate_model_plan(plan, set(inventory))
        plan["request"] = request
        plan["mode"] = "plan-only"
        plan["humanApprovalRequired"] = True
        plan["status"] = evidence["status"]
        plan["repositoryEvidence"] = evidence
        plan.setdefault("filesToInspect", [asdict(candidate) for candidate in files])
        return plan
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return _fallback_plan(request, files, evidence)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a read-only PRD plan.")
    parser.add_argument("request", help="PRD or feature request")
    parser.add_argument(
        "--repository",
        type=Path,
        default=Path(os.environ.get("STREAMBANK_PATH", "../StreamBank")),
    )
    parser.add_argument("--output", type=Path, default=Path("plan.json"))
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()
    plan = create_plan(args.request, args.repository.resolve(), args.model)
    plan["runId"] = str(uuid.uuid4())
    plan["createdAt"] = datetime.now(timezone.utc).isoformat()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(plan, indent=2, ensure_ascii=False))
    print(f"\nSaved read-only plan to {args.output}", flush=True)


if __name__ == "__main__":
    main()
