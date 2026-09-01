# Start-of-Session Checklist

1. Read `AGENTS.md`, `CONTEXT.md`, `DECISIONS.md`, `ROADMAP.md`, and `SOURCES.md`.
2. Check `git branch --show-current` and `git status --short`; never work
   directly on `main`.
3. For a new feature, create a `feature/<short-name>` branch before editing.
4. Confirm the local environment exists with `.venv/bin/python --version`.
   If it does not, follow the README setup steps. Do not commit `.venv`, `.env`,
   `db.sqlite3`, or `media/`.
5. Before modifying files, state the intended files and why.
6. After implementation, run the relevant tests and update `CONTEXT.md` with
   the current date, branch/commit, changes, gaps, and test result. Add a
   decision or external source entry when applicable.
