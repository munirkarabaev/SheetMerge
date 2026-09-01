# SheetMerge

SheetMerge is an AI-assisted web application that helps users combine messy transaction spreadsheets into one clean, organized spreadsheet.

Users upload multiple CSV/XLSX files from different sources.

The application:
- Detects transaction columns
- Standardizes formats
- Merges transactions
- Groups similar transactions
- Sorts by date and month
- Exports a clean spreadsheet

The AI assistant can ask clarification questions and propose a structured merge
plan. Python deterministically applies the approved plan for previews and
exports.

## Local setup

The virtual environment is intentionally not committed. On a new machine,
install Python 3.12+ and create a project-local environment:

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements.txt
cp .env.template .env
./.venv/bin/python manage.py migrate
./.venv/bin/python manage.py runserver
```

Add real OpenAI or Google OAuth values only to `.env`; it is ignored by Git.
Run the test suite with:

```bash
./.venv/bin/python manage.py test
```

## Project handoff documentation

- `CONTEXT.md` — current implementation state, known gaps, and test status.
- `DECISIONS.md` — durable technical decisions and their consequences.
- `ROADMAP.md` — completed work and prioritized upcoming work.
- `SOURCES.md` — external services, configuration names, and failure behavior.
- `prompts/start-session.md` — the required session checklist.

These are deliberately human-maintained; Django and Git do not automatically
update them after a coding session.
