# ADR-001: Start with read-only planning

## Status

Accepted

## Decision

Begin with a read-only plan-only slice that requires human approval before any
future write or execution stage.

## Rationale

The platform operates around other repositories. Keeping the first slice
read-only limits blast radius while repository evidence, model output shape,
path validation, and boundary enforcement are established and testable.

## Consequences

The current service cannot apply patches or run target tests. Those capabilities
must be added behind explicit approval and sandbox policy rather than inferred
from a plan.

## Evidence

- `app/plan.py`
- `app/server.py`
- `agent-platform/sandbox/policy.yaml`
