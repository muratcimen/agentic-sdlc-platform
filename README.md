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

## Local plan-only application

The first executable slice only reads StreamBank and produces a JSON plan. It
does not write repository files, apply patches, or run tests in StreamBank.

```bash
python3 -m unittest discover -s tests -v
python3 -m app.plan \
  --repository ~/projects/StreamBank \
  --output plan.json \
  "Transfer işlemlerinde günlük limit kontrolü eklenmesini planla."
```

Ollama must be available at `http://127.0.0.1:11434`. If it is unavailable or
returns invalid JSON, the application produces a deterministic fallback plan.
