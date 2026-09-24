# Repository evidence

Evidence is collected before model planning. `app/evidence.py` reports
repository status, code references, schema references, transactional
boundaries, and blockers. A missing domain signal blocks model planning and
selects the deterministic fallback. This keeps an uncertain request explicit
instead of allowing a model to imply that an implementation already exists.
