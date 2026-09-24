# Plan-only mode

Plan-only mode is a read-only boundary: it may inspect repository text and
produce a proposed change, but it does not apply patches or execute tests in
the target repository. Every generated plan sets `mode` to `plan-only` and
`humanApprovalRequired` to `true`.

The boundary is implemented in `app/plan.py` and exposed through
`app/server.py`. The API's saved JSON is a platform artifact; it is not a
change to the inspected checkout.
