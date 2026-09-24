# AP-001: Establish the read-only plan-only foundation

## Status

COMPLETED

## Objective

Provide a safe first vertical slice that reads a repository, gathers evidence,
and produces a reviewable plan without changing the repository.

## Plan

1. Start in read-only mode and require human approval for any future change.
2. Integrate Ollama using `qwen2.5-coder:1.5b`.
3. Prevent model path hallucinations by supplying a repository inventory and
   validating every returned `filesToInspect` path.
4. Enforce the repository boundary at the HTTP API.
5. Fall back deterministically when evidence is insufficient or Ollama returns
   an unavailable or invalid response.

## Verified result

- Read-only behavior is implemented by `create_plan` and the HTTP API; plans
  carry `mode: plan-only` and `humanApprovalRequired: true`, and the target
  repository is not used as a write location.
- Ollama requests use the configurable endpoint's `/api/generate` route and
  default to `qwen2.5-coder:1.5b`.
- The prompt includes an inventory of repository-relative text files, and
  `_validate_model_plan` rejects any returned path outside that inventory.
- `PROJECT_ROOTS` (with `STREAMBANK_PATH` as a compatibility alias) restricts
  API repositories to configured roots.
- Missing repository evidence, Ollama errors, invalid JSON, incomplete plans,
  and invalid model paths select the deterministic fallback plan.

## Test evidence

The repository test suite was run with:

```text
python3 -m unittest discover -s tests -v
```

Observed result for this repository: **14 tests ran, OK**. The focused
validator tests are included in that count.

## Commit / PR

- Commit: https://github.com/muratcimen/agentic-sdlc-platform/commit/9c6663b6ca4a273b9bf379121b7cf533bc86df6e

## Remaining gaps

- Ollama availability and model quality are not tested against a live service.
- Patch application, target-repository test execution, diff generation, and
  approval-gated sandbox execution remain planned.
- The inventory is intentionally bounded in the model prompt; larger
  repositories need a retrieval strategy before execution features are added.
