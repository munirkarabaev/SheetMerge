# Contributing

## Local environment

Use the ignored project-local `.venv` described in the README. Do not commit
`.venv/`, `venv/`, `.env`, `db.sqlite3`, or `media/`.

## Branches

Never commit directly to main.

Examples:

feature/django-setup
feature/file-upload
feature/spreadsheet-parser
feature-column-mapping
feature-export-xlsx
feature-ai-assistant

Before editing, state the planned file changes. After implementation, run the
relevant tests and update the handoff documentation when the project state,
roadmap, a durable decision, or an external source changed.

## Commit Messages

Examples:

Add Django project structure
Implement file upload workflow
Add transaction normalization service
Implement spreadsheet export
