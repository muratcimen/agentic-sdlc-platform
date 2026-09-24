from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

IGNORED_PARTS = {".git", ".idea", "target", "__pycache__", ".mvn"}
SOURCE_SUFFIXES = {".java", ".sql", ".xml", ".yml", ".yaml", ".properties"}


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
    query_terms = set(re.findall(r"[A-Za-z0-9_-]+", lower_query))
    expansions = {
        "transfer": {"account", "deposit", "withdraw", "transaction"},
        "limit": {"account", "transaction", "service", "controller"},
    }
    for term in tuple(query_terms):
        query_terms.update(expansions.get(term, set()))
    transfer_terms = ("transfer", "transaction", "deposit", "withdraw", "limit")
    relevant_code = [
        asdict(reference)
        for reference in code
        if not lower_query
        or any(
            term in reference.symbol.lower() or term in reference.evidence.lower()
            for term in query_terms
        )
    ]
    relevant_schema = [
        asdict(reference)
        for reference in schema
        if any(term in reference.object_name.lower() or term in reference.evidence.lower()
               for term in transfer_terms)
    ]
    transactional = [
        asdict(reference)
        for reference in code
        if "@Transactional" in reference.annotations
    ]
    transfer_evidence = [
        item for item in relevant_code
        if any(term in (item["symbol"] + " " + item["evidence"]).lower()
               for term in ("transfer", "deposit", "withdraw", "transaction"))
    ]
    status = "READY_FOR_REVIEW"
    blockers: list[str] = []
    if not transfer_evidence:
        status = "BLOCKED_BY_REPOSITORY_EVIDENCE"
        blockers.append("No transfer or transaction code reference was found.")
    if not relevant_schema:
        blockers.append("No transfer-related SQL table, index, or constraint was found.")
        if status == "READY_FOR_REVIEW":
            status = "BLOCKED_BY_REPOSITORY_EVIDENCE"
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
            "transferEvidenceCount": len(transfer_evidence),
        },
        "blockers": blockers,
        "readOnly": True,
    }
