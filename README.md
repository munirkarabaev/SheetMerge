# SheetMerge

**An AI-assisted accounting workflow app for combining transaction CSV files into a consistent, reviewable spreadsheet.**

SheetMerge helps users consolidate bank and transaction exports that use different column names, date formats and debit/credit conventions. Users describe the output they need, review an AI-generated mapping plan, preview the merged data and download the result as CSV.

Developed independently by [munirkarabaev](https://github.com/munirkarabaev), a BSc Computer Science student at King's College London. The application is under development; the core workflow is implemented, with further normalization and interface improvements planned.

## The problem

Combining financial exports often requires manually matching columns and correcting formats before the data can be reviewed together. SheetMerge provides a guided workflow for this task, while keeping the proposed mappings and resulting rows visible to the user.

## Current features

- **Authenticated workspaces:** create and manage merge projects, with access scoped to their owner.
- **CSV ingestion:** upload multiple files, detect delimiters, validate headers and row structure, and retain metadata and sample rows for planning. Supported encodings include UTF-8 with BOM, Windows-1252 and ISO-8859-1.
- **Conversational mapping:** describe the desired output and answer clarification questions. Planning conversations and generated plans are persisted.
- **Structured AI plans:** use the OpenAI Responses API to generate a JSON-schema mapping plan covering output columns, source mappings and supported operations.
- **Review and revision:** inspect per-file mappings, ignored columns, transformation notes and a spreadsheet preview; request changes through natural-language instructions.
- **Deterministic transformations:** combine text fields, retain source filenames, normalize recognized dates to ISO format, combine debit/credit fields into signed amounts and sort recognized dates chronologically.
- **Currency conversion:** convert supported amounts using cached monthly average historical exchange rates, with a Frankfurter provider. Rows retain their original amount and show a preview warning when conversion cannot be completed.
- **Mapping approval and CSV export:** save approval state and export using the approved plan where available, otherwise the latest generated plan.
- **AI usage accounting:** record input/output token usage and deduct it from a per-user credit balance.

## How it works

1. Sign in and create a merge project.
2. Upload transaction CSV files and resolve any parsing errors.
3. Describe the desired spreadsheet in the AI planning chat.
4. Review the mapping plan and merged preview, requesting revisions if needed.
5. Approve the mapping and download the CSV result.

## Technical approach

The AI proposes how source columns should map to the output. Python applies the supported transformations to the original CSV rows to produce previews and exports. This separates interpretation of user intent from execution of the data-processing steps.

Planning context contains file headers, metadata, up to ten sample rows per file and conversation history. Revisions also use the existing plan and a preview sample. The application sends this context to OpenAI when generating or revising a plan.

Exchange rates come from a separate provider-backed service and are cached in the database. The application does not rely on the language model to invent rates. Monetary conversion uses Python's `Decimal` type.

## Example workflow

For example, one bank export might contain `Posted Date`, `Details`, `Debit` and `Credit`, while another uses `Completed Date`, `Description` and `Amount`. A user can request a shared `Date / Description / Amount / Source` output, review the proposed column mappings, and preview the combined rows before exporting.

This is an illustrative use case, not a benchmark or measured customer result.

## Technology

| Area | Technology |
| --- | --- |
| Backend | Python, Django |
| User interface | Django templates, HTML, CSS, JavaScript |
| Authentication | Django authentication, django-allauth; optional Google OAuth configuration |
| Development database | SQLite |
| AI integration | OpenAI Responses API with structured JSON-schema output |
| Data processing | Python CSV, datetime and decimal libraries |
| Exchange rates | Frankfurter-backed service with database caching |
| Testing | Django test framework |

## Local development

Use Python 3.12 or newer supported by Django 6.0. The following describes the repository's development configuration; it is not a production deployment guide.

```bash
git clone https://github.com/munirkarabaev/SheetMerge.git
cd SheetMerge
python -m venv .venv
```

Activate the environment:

```powershell
# Windows PowerShell
.venv\Scripts\Activate.ps1
```

```bash
# macOS / Linux
source .venv/bin/activate
```

Install the dependencies, copy `.env.template` to `.env`, and configure `OPENAI_API_KEY` and `OPENAI_MODEL` for AI planning. Google OAuth settings are optional. Keep credentials in the local environment file.

```bash
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open `http://127.0.0.1:8000/`. AI requests require configured API access and may incur usage charges.

New users start with zero AI token credits. Sign in to `/admin/` with the superuser account, select the development user's record, and set a positive `ai_token_credit_balance` before using AI planning or revision. This application balance is separate from the API account's billing.

## Testing

The repository includes tests for CSV uploads, planning models and services, AI revisions, previews, currency conversion, mapping review and approval, and authenticated workspace views.

```bash
python manage.py test
```

## Current limitations and next steps

- Input processing and export currently use CSV. XLSX support is planned.
- Amount normalization remains limited; general `parse_amount` handling currently passes through the source value, while debit/credit and currency-conversion paths support specific cleanup operations.
- Ambiguous numeric dates are interpreted using day-first formats before month-first formats. Unrecognized dates remain as text and appear after recognized dates when sorting.
- Currency conversion uses monthly average rates. When conversion fails, original amounts remain in the output; preview warnings must be reviewed before using the result.
- Richer conversion provenance and downloadable warning summaries are planned.
- Transaction grouping and suggested groups remain roadmap items.
- Further interface polish and a clearer completion screen after approval/export are planned.
- The checked-in settings are for local development; production deployment remains separate work.

## Project documentation

- [Roadmap](ROADMAP.md): original development phases.
- [Context](CONTEXT.md): detailed implementation notes and known gaps; some earlier notes have been superseded by later work.
- [Decisions](DECISIONS.md): project decision log.

## Maintainer and feedback

Maintained by [munirkarabaev](https://github.com/munirkarabaev). For questions or reproducible problems, use the repository's [issue tracker](https://github.com/munirkarabaev/SheetMerge/issues). Use synthetic transaction data in examples and reports.
