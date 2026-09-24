# Agentic SDLC Platform wiki

This wiki records the platform's architecture, operating concepts, decisions,
and implementation tasks. Pages are repository evidence, not a substitute for
the source code or test suite.

## Current architecture

The current vertical slice is a read-only planning service:

```text
HTTP POST /plans or app.plan CLI
        |
        v
configured repository boundary -> evidence analysis -> candidate/inventory discovery
        |                                      |
        |                                      +-> blocked evidence: deterministic fallback
        v
Ollama /api/generate (qwen2.5-coder:1.5b)
        |
        v
JSON shape + inventory validation -> plan-only result requiring human approval
        |
        v
platform-local plans/<runId>.json (HTTP API only)
```

`app/plan.py` owns discovery, evidence gating, Ollama integration, model-plan
validation, and fallback behavior. `app/evidence.py` extracts code and schema
references without writing to the target repository. `app/server.py` exposes
health, configured-project, plan, and saved-plan endpoints and enforces
configured repository roots. `agent-platform/sandbox/policy.yaml` describes the
future isolated execution boundary; patch and test execution are not yet
implemented by this repository.

## Page conventions

- `tasks/` contains one page per tracked implementation item.
- `decisions/` contains durable architectural decisions and their alternatives.
- `architecture/`, `concepts/`, and `operations/` explain behavior that exists
  today; label planned behavior explicitly.
- Cite repository-relative paths in backticks. The validator checks that cited
  paths exist.

Create a task page by copying `templates/task.md`, replacing every placeholder,
and choosing one status: `PLANNED`, `IN_PROGRESS`, `BLOCKED`, or `COMPLETED`.
When work changes, update the task page in the same change as the code and
record the tests and commit or pull request that support the status. Use
`templates/decision.md` for decisions that affect more than one task.

## Validation

Run the wiki validator from the repository root:

```bash
python3 scripts/validate_wiki.py
```

It checks required task headings and statuses, verifies referenced
repository-relative paths, and requires test evidence plus a commit/PR link for
`COMPLETED` tasks. The focused validator tests run with the rest of the
repository's standard-library suite:

```bash
python3 -m unittest discover -s tests -v
```
