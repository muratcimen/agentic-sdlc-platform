from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

IGNORED_PARTS = {".git", ".idea", "target", "__pycache__", ".mvn"}
SOURCE_SUFFIXES = {".java", ".sql", ".xml", ".yml", ".yaml", ".properties"}

# Domain vocabulary shared by discovery, evidence context, and the evidence gate.
EXPANSIONS = {
    "transfer": {"account", "deposit", "withdraw", "transaction"},
    "havale": {"transfer", "transaction", "deposit", "withdraw"},
    "limit": {"account", "transaction", "service", "controller"},
    "günlük": {"account", "transaction", "service"},
    "limitini": {"account", "transaction", "service"},
}
TRANSFER_VOCABULARY = {"transfer", "transaction", "deposit", "withdraw", "havale"}
MIN_TERM_LENGTH = 3


def domain_terms(text: str) -> set[str]:
    """Return request terms, widened with the transfer vocabulary on demand.

    Only the words the caller actually wrote (length >= 3) are used as the
    evidence gate, so a request without a domain word cannot pass the gate
    through a generic entity expansion such as "account".
    """
    core = {
        term.lower()
        for term in re.findall(r"\w+", text.lower())
        if len(term) >= MIN_TERM_LENGTH
    }
    if core & TRANSFER_VOCABULARY:
        return core | TRANSFER_VOCABULARY
    return core


def candidate_terms(text: str) -> set[str]:
    """Return domain terms plus known entity expansions for discovery."""
    terms = domain_terms(text)
    for term in re.findall(r"\w+", text.lower()):
        if len(term) >= MIN_TERM_LENGTH:
            terms.update(EXPANSIONS.get(term, ()))
    return terms


@dataclass(frozen=True)
class CodeReference:
    path: str
    symbol: str
    kind: str
    annotations: list[str]
    evidence: str


@dataclass(frozen=True)
class SchemaReference:
    path: str
    object_name: str
    kind: str
    evidence: str


def _files(repository: Path, suffixes: set[str]) -> list[Path]:
    return [
        path
        for path in repository.rglob("*")
        if path.is_file()
        and path.suffix.lower() in suffixes
        and not any(part in IGNORED_PARTS for part in path.parts)
    ]


def _relative(path: Path, repository: Path) -> str:
    return path.relative_to(repository).as_posix()


def _java_references(repository: Path) -> list[CodeReference]:
    references: list[CodeReference] = []
    class_pattern = re.compile(
        r"(?P<annotations>(?:(?:@\w+(?:\([^)]*\))?\s*)*))"
        r"\b(?:public\s+|private\s+|protected\s+)?"
        r"(?:abstract\s+|final\s+)?(?:class|interface|record|enum)\s+"
        r"(?P<name>[A-Za-z_$][\w$]*)"
    )
    method_pattern = re.compile(
        r"(?P<annotations>(?:(?:@\w+(?:\([^)]*\))?\s*)*))"
        r"(?P<signature>(?:(?:public|private|protected|static|final|synchronized|"
        r"abstract|native|default|<[^>]+>|[\w<>, ?\[\].]+)\s+)+"
        r"(?P<name>[A-Za-z_$][\w$]*)\s*\([^;{}]*\))"
    )
    for path in _files(repository, {".java"}):
        text = path.read_text(encoding="utf-8", errors="ignore")
        relative = _relative(path, repository)
        for match in class_pattern.finditer(text):
            annotations = re.findall(r"@\w+(?:\([^)]*\))?", match.group("annotations"))
            references.append(
                CodeReference(
                    path=relative,
                    symbol=match.group("name"),
                    kind="class",
                    annotations=annotations,
                    evidence=match.group(0).strip().replace("\n", " "),
                )
            )
        for match in method_pattern.finditer(text):
            annotations = re.findall(r"@\w+(?:\([^)]*\))?", match.group("annotations"))
            references.append(
                CodeReference(
                    path=relative,
                    symbol=match.group("name"),
                    kind="method",
                    annotations=annotations,
                    evidence=match.group(0).strip().replace("\n", " "),
                )
            )
    return references


def _schema_references(repository: Path) -> list[SchemaReference]:
    references: list[SchemaReference] = []
    patterns = (
        ("table", re.compile(r"\bCREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([A-Za-z_][\w.]*)", re.I)),
        ("index", re.compile(r"\bCREATE\s+(?:UNIQUE\s+)?INDEX\s+([A-Za-z_][\w.]*)", re.I)),
        ("constraint", re.compile(r"\bCONSTRAINT\s+([A-Za-z_][\w.]*)", re.I)),
    )
    for path in _files(repository, {".sql"}):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for kind, pattern in patterns:
            for match in pattern.finditer(text):
                start = max(0, text.rfind("\n", 0, match.start()) + 1)
                end = text.find("\n", match.end())
                evidence = text[start : end if end >= 0 else len(text)].strip()
                references.append(
                    SchemaReference(
                        path=_relative(path, repository),
                        object_name=match.group(1),
                        kind=kind,
                        evidence=evidence,
                    )
                )
    return references


def analyze_repository(repository: Path, query: str = "") -> dict[str, Any]:
    if not repository.is_dir():
        raise ValueError(f"Repository does not exist: {repository}")
    code = _java_references(repository)
    schema = _schema_references(repository)
    lower_query = query.lower()
    context = candidate_terms(lower_query)
    gate = domain_terms(lower_query)
    relevant_code = [
        asdict(reference)
        for reference in code
        if not lower_query
        or any(
            term in reference.symbol.lower() or term in reference.evidence.lower()
            for term in context
        )
    ]
    relevant_schema = [
        asdict(reference)
        for reference in schema
        if not lower_query
        or any(
            term in reference.object_name.lower() or term in reference.evidence.lower()
            for term in context
        )
    ]
    transactional = [
        asdict(reference) for reference in code if "@Transactional" in reference.annotations
    ]
    gate_code = [
        reference
        for reference in code
        if any(
            term in reference.symbol.lower() or term in reference.evidence.lower()
            for term in gate
        )
    ]
    gate_schema = [
        reference
        for reference in schema
        if any(
            term in reference.object_name.lower() or term in reference.evidence.lower()
            for term in gate
        )
    ]
    status = "READY_FOR_REVIEW"
    blockers: list[str] = []
    if not lower_query:
        status = "BLOCKED_BY_REPOSITORY_EVIDENCE"
        blockers.append("The request is empty.")
    else:
        if not gate_code:
            status = "BLOCKED_BY_REPOSITORY_EVIDENCE"
            blockers.append("No code reference matched the request domain.")
        if not gate_schema:
            status = "BLOCKED_BY_REPOSITORY_EVIDENCE"
            blockers.append("No SQL table, index, or constraint matched the request domain.")
    return {
        "status": status,
        "repository": str(repository),
        "query": query,
        "codeReferences": relevant_code,
        "transactionalBoundaries": transactional,
        "schemaReferences": relevant_schema,
        "evidenceSummary": {
            "javaReferenceCount": len(relevant_code),
            "transactionalBoundaryCount": len(transactional),
            "schemaReferenceCount": len(relevant_schema),
            "domainEvidenceCount": len(gate_code) + len(gate_schema),
        },
        "blockers": blockers,
        "readOnly": True,
    }
