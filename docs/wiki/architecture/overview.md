# Architecture overview

## Implemented flow

The platform currently turns a natural-language request into a reviewable,
read-only JSON plan. The CLI entry point is `app/plan.py`; the HTTP entry point
is `app/server.py`. Both call `create_plan`.

`create_plan` first rejects a missing repository, discovers relevant text files,
and calls `analyze_repository`. Evidence is marked `READY_FOR_REVIEW` only when
the request has matching code and schema evidence; otherwise planning stops
with a deterministic `BLOCKED_BY_REPOSITORY_EVIDENCE` fallback. For ready
requests, a bounded inventory is placed in the Ollama prompt. The returned JSON
must contain the required plan fields, require human approval, and reference
only inventory paths. Invalid or unavailable model responses use the same
deterministic fallback.

The API validates non-empty requests and, when `PROJECT_ROOTS` or
`STREAMBANK_PATH` is configured, accepts only repositories under those roots.
It persists API results in the platform's `plans/` directory, never in the
target repository. Health and project endpoints expose service state without
scanning project contents.

## Not implemented yet

The sandbox policy is documented in `agent-platform/sandbox/policy.yaml`, but
this repository does not yet apply patches, run target-repository tests, produce
diffs, or perform approval-gated execution. Those are later stages of the
intended `plan -> approval -> sandbox -> tests -> review` flow.
