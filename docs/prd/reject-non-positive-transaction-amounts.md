# PRD: Reject non-positive transaction amounts

## Problem

Account deposit and withdrawal endpoints must reject null, zero, and negative
amounts without changing the account balance.

## Acceptance criteria

- Null amounts are rejected.
- Zero and negative amounts are rejected.
- The account balance remains unchanged after rejection.
- The API returns the deterministic `BUSINESS_RULE` error code.
- Existing positive deposit and withdrawal behavior is preserved.
- Unit or integration coverage verifies the rule.

## Scope

- `backend/core-api/src/main/java/com/streambank/accounts/service/impl/AccountServiceImpl.java`
- `backend/core-api/src/main/java/com/streambank/shared/GlobalExceptionHandler.java`
- Account service and HTTP tests

## Risk

Low. The change only normalizes the existing validation failure into the
application's business-error contract; positive transaction behavior is
unchanged.

## Human approval

Required before applying an agent-generated patch to a shared branch.
