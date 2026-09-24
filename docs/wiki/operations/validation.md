# Wiki validation operation

From the repository root, run:

```bash
python3 scripts/validate_wiki.py
```

The command scans `docs/wiki/tasks/*.md`. A task must have the required
headings, a supported `Status`, and repository-relative file references that
exist. A `COMPLETED` task must include a non-empty test-evidence section and a
GitHub commit or pull-request URL. It exits non-zero and prints each violation
when a page is invalid.
