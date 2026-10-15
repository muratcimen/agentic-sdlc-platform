# AP-002: Align plan schema contract and generalize evidence gate

## Status

COMPLETED

## Objective

Close the two contract gaps in the plan-only slice: the agent-contract schema
did not describe the plan that `app/plan.py` actually produces, and repository
evidence gating was hardcoded to the transfer domain, blocking every
non-transfer request.

## Plan

1. Rewrite `docs/agent-contracts/plan-output.schema.json` so its required keys
   match `REQUIRED_PLAN_KEYS` plus `request` and `mode`, and encode the
   read-only guarantees as schema constraints.
2. Replace the hardcoded transfer vocabulary in `app/evidence.py` with shared
   `domain_terms` and `candidate_terms` helpers so the evidence gate derives
   from the request; the transfer vocabulary only widens the gate when the
   request mentions it.
3. Make `discover_files` in `app/plan.py` consume the shared helper, removing
   the duplicated expansion table.
4. Add contract tests that keep the schema, the prompt, and the fallback plan
   aligned, and evidence tests for transfer and non-transfer requests.

## Verified result

- `docs/agent-contracts/plan-output.schema.json` requires exactly
  `REQUIRED_PLAN_KEYS | {request, mode}` and asserts `mode: plan-only`,
  `humanApprovalRequired: true`, the `status` enum, and
  `repositoryEvidence.readOnly: true`.
- `analyze_repository` gates on request-derived terms: a KYC request with
  matching code and schema evidence reaches `READY_FOR_REVIEW`, while a
  transfer-flavored request without transfer evidence stays
  `BLOCKED_BY_REPOSITORY_EVIDENCE`.
- `app/plan.py` no longer duplicates the expansion table; it imports
  `candidate_terms` from `app/evidence.py`.

## Test evidence

```text
python -m unittest discover -s tests -v
Ran 22 tests in 3.736s
OK
```

The wiki validator script `scripts/validate_wiki.py` also passes.

## Commit / PR

https://github.com/muratcimen/agentic-sdlc-platform/pull/2

## Remaining gaps

- The schema is validated in tests only; `create_plan` still does not validate
  model output against the schema at runtime (the key/paths checks predate
  this change).
- The `EXPANSIONS` table remains a hand-maintained English/Turkish keyword
  list; a retrieval strategy is still needed for larger repositories.

## Evidence

- `docs/agent-contracts/plan-output.schema.json`
- `app/evidence.py`
- `app/plan.py`
- `tests/test_schema_contract.py`
- `tests/test_evidence.py`
