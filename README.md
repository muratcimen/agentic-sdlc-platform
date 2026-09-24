# Agentic SDLC Platform

A separate platform for turning product requirements into safe, testable and reviewable repository changes.

## Repository boundary

- `StreamBank` contains the Java/Spring banking application.
- This repository contains orchestration, repository tools, sandbox execution, knowledge retrieval, evaluations and observability.

The platform must never write directly to a shared or production checkout. It works against a temporary repository copy, applies explicit tool and path policies, runs tests, produces a diff and waits for human approval.

## Initial vertical slice

```text
PRD -> structured plan -> human approval -> sandbox patch -> tests -> diff/review
```

The first scenario is rejecting null, zero and negative account transaction amounts in StreamBank.
