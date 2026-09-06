# SheetMerge Context

Last updated: 2026-09-06
Current feature branch: `feature/further-ai-integration`
Baseline before workflow-safety commit: `14def8b`
(`docs: record product direction and browser testing setup`). The safety work
described below is included in `feat: complete safe, auditable merge workflow`.

## How to Maintain This File

This is a human-maintained engineering handoff, not an automatically generated
Django artifact. At the end of every implementation session, update the date,
branch/baseline, implemented work, known gaps, test result, and suggested next
work. Do not record secrets, tokens, personal data, or raw customer CSV data.

Use [prompts/start-session.md](prompts/start-session.md) at the beginning of a
session. Record durable architectural choices in [DECISIONS.md](DECISIONS.md),
not in chat history. The README remains the source of truth for local setup.

## Project Purpose

SheetMerge is a Django web app for uploading messy bank or transaction CSV files,
letting the user define the desired merged spreadsheet, using AI to plan column
mappings, and then previewing/exporting the merged result.

The product direction is practical and guided: the user should not need to inspect
each spreadsheet manually. The AI should look at parsed headers and sample rows,
make sensible guesses, ask only blocking questions, and name the exact file and
columns involved when asking for confirmation.

## Repository Rules

- Never commit directly to `main`.
- Check the branch before starting work.
- Explain planned file changes before editing.
- Keep code organized in the existing Django structure:
  - templates in `templates/`
  - views in `views/`
  - forms in `forms/`
  - models in `models/`
- Keep files under 400 lines.
- Use Django templates, not React.
- Do not introduce Docker or Celery unless explicitly requested.
- Run tests after implementation and suggest a commit message.

## Current Branch State

The AI integration, deterministic preview, currency conversion foundation, and
mapping approval work are present in the baseline. The workflow-safety commit
on this branch completes the safety layer: approval-only export,
blocking exceptions, formula protection, amount normalization, provenance,
reconciliation, completion, semantic AI-plan validation, and favicon support.
Review Git status before starting further changes.

## 2026-09-05 — Product direction and local testing setup

- The durable product direction is now recorded in `ROADMAP.md`: SheetMerge is
  a repeatable, auditable financial-export normalization layer for recurring
  monthly-close work, not generic spreadsheet software or a full accounting
  platform.
- Validate first with bookkeepers or accountants handling recurring bank, card,
  and platform exports for small businesses.
- AI should propose a constrained mapping for a new or changed source format;
  a human approves it, and deterministic code executes approved profiles for
  every row. Known formats should normally require no AI call.
- The immediate implementation priority is safe export and transformation
  behavior: approval-only export, blocking exceptions, formula-injection
  protection, amount/date normalization, provenance, and reconciliation.
- A global `playwright` MCP server was configured for Codex using
  `npx @playwright/mcp@latest --isolated --caps=testing`. Node.js 22 is already
  installed. It uses an isolated browser profile and is not application or
  repository configuration. Start a fresh Codex session before using it because
  the current session cannot load newly configured MCP tools dynamically.
- No real customer financial data should be uploaded until the safety gates in
  `ROADMAP.md` are complete.

## Latest Session Handoff

### New-machine setup

- Created the ignored project-local `.venv` with Python 3.12.3 and installed
  the pinned dependencies.
- Created the ignored `.env` file from `.env.template`; the user configured
  `OPENAI_API_KEY` locally. Do not read, print, commit, or copy that secret.
- `./.venv/bin/python manage.py check` passes.
- The initial setup run discovered 135 tests. The later recorded full-suite
  result is 154 passing tests on 2026-09-05; see Test Status below.

### AI-credit operations

- User AI credits are an internal token counter, not a dollar balance: one
  credit is deducted for each total token reported by OpenAI.
- Credits can currently be allocated only through Django admin: select the
  user and edit `AI token credit balance`. The saved value applies to the next
  AI request without restarting the server.
- There is no customer-facing purchase/top-up flow and no exact USD spend cap.
  Because GPT-5.5 prices input and output tokens differently, a token balance
  cannot represent an exact dollar amount.

## Implemented This Session

### Export approval gate and favicon

- CSV export now uses only an explicitly approved `MergePlan`; it no longer
  falls back to the latest plan awaiting review.
- An attempted export with an unapproved plan redirects to column mapping with
  an instruction to approve the mapping first.
- The column-mapping page shows the CSV download link only after approval.
- Added a native SheetMerge SVG favicon and its shared-template regression
  test, eliminating the home page's missing-favicon browser error.

### Export exception gate

- Preview processing now records deterministic, export-blocking exceptions for
  invalid non-empty typed date/amount values and failed currency conversions.
- CSV export and its download action are blocked until those exceptions are
  resolved, even when the mapping plan has already been approved.
- Failed currency conversion now leaves the converted output cell blank; it
  never copies the unconverted source amount into that field.

### CSV formula-injection protection

- CSV export now neutralizes formula-like header and cell text beginning with
  `=`, `+`, `-`, or `@` by prefixing an apostrophe.
- Valid signed numeric amounts remain unchanged so they retain spreadsheet
  numeric behavior.

### Amount normalization and currency provenance

- Amount mappings can now declare `amount_format` with explicit decimal and
  thousands separators. Supported US and European formats are normalized to
  canonical decimal text; malformed grouping becomes an export-blocking
  exception.
- Successful currency conversion now records per-row export provenance:
  original/reporting amount and currency, rate, provider, monthly period,
  policy, rounding, and target output column.
- CSV exports include those provenance columns only when conversion occurred.

### Transaction-level provenance

- Every CSV export row now includes source file, original CSV row number,
  original source values, mapping-plan version, applied transformations, and
  mapping review state.
- Provenance remains paired with the correct output row after deterministic
  sorting. The mapping-plan version is the immutable `MergePlan` identifier
  (`plan-<id>`), so later AI revisions cannot overwrite an earlier audit trail.

### Reconciliation and exception review

- Column-mapping review now shows output row count, row counts by source file,
  and normalized totals for each money column.
- Blocking validation failures are shown as categorised Open exceptions.
- Exceptions cannot be silently acknowledged: CSV export remains blocked until
  the user asks AI to revise the plan, reviews the regenerated output, and
  obtains an exception-free result.

### Completed workflow screen

- Approved, exception-free mergesets now have an owner-only completion screen
  with final row/total summary, plan identifier, provenance notice, CSV export,
  and a return link to mapping review.
- The screen enforces the same approval and exception safety gates as export;
  it cannot be used to bypass review.

### Semantic AI-plan validation

- Mapping-ready plans and AI revisions are now semantically validated before
  persistence. Validation rejects unknown/unparsed files, unknown source
  columns, unsupported transforms, invalid output targets and sort operations,
  invalid amount separators, invalid currency codes, and unsafe low-confidence
  currency conversion.
- All accepted AI plans still begin in `needs_review`; human approval remains
  mandatory before export.

### AI Planning Data

- Added `MergesetFile.sample_rows` so parsed files keep sample row data for AI
  context.
- CSV parsing stores the first 10 non-empty data rows as samples.
- AI context includes:
  - mergeset id/name/description
  - parsed source file headers
  - delimiter
  - row count
  - sample rows
  - conversation history
  - file number and filename for each uploaded file

### Planning Models

Added planning persistence models:

- `MergePlanningSession`
- `MergePlanningMessage`
- `MergePlan`

These support a back-and-forth planning conversation, persisted assistant/user
messages, and a saved JSON mapping plan for later review.

### AI Suggestions Chat

The AI suggestions page now has a real chat workflow:

- The page creates or loads a planning session for the mergeset.
- User messages are saved as `MergePlanningMessage` rows.
- Assistant responses are generated by OpenAI and saved.
- The chat submits asynchronously with no full page refresh.
- The user's message appears immediately.
- A temporary assistant `...` typing message is shown while waiting.
- Errors appear inside the chat.
- Pressing Enter sends immediately.
- Shift+Enter keeps a newline.
- The previous suggested-message buttons were removed.
- The first assistant message explains what it needs from the user.
- AI chat font sizes were increased for readability.
- A reset button clears the conversation and related plan, then starts fresh.

### OpenAI Configuration

- Added simple `.env` loading in `config/settings.py`.
- Added `.env.template` with:
  - `OPENAI_API_KEY=`
  - `OPENAI_MODEL=gpt-5.5`
  - Google OAuth placeholders
- `.env` remains ignored and should hold the real API key locally.
- Added `openai==2.43.0` to `requirements.txt`.
- The OpenAI key should never be pasted into chat.

### OpenAI Planning Service

Added `core/services/ai_planning.py`.

The service:

- Builds deterministic planning context from parsed CSV data and chat history.
- Calls the OpenAI Responses API.
- Requests a strict JSON-schema response.
- Returns either:
  - `needs_clarification`
  - `mapping_ready`
- Saves assistant messages.
- Creates a `MergePlan` when mapping is ready.

The planning JSON includes:

- `status`
- `assistant_message`
- `questions`
- `final_columns`
- `file_mappings`
- `result_operations`

Supported transforms in the plan contract:

- `copy`
- `parse_date`
- `parse_amount`
- `debit_credit_to_signed_amount`
- `credit_debit_to_signed_amount`
- `combine_text`
- `constant_source_name`
- `ignore`

### Prompt Direction

The user wants the AI to be less abstract and more guiding.

Important prompt rules already added:

- If the user confirms the previous interpretation, return `mapping_ready`
  instead of asking for confirmation again.
- Do not repeat a question that has already been answered.
- Ask only for missing information that blocks a safe mapping.
- Write naturally, not like a robotic checklist.
- If a column is uncertain, name the exact source columns or options.
- Guide the user without requiring them to inspect the spreadsheets.
- Make a best guess per file and ask the user to confirm or correct it.
- Refer to files by file number and filename.
- Do not ask abstract questions like "which date field?" without naming the
  specific files and candidate columns.
- When ready, tell the user to proceed to column mapping.
- Preserve every final output column requested by the user.
- If the user asks to keep all fields or all columns, include all available
  source headers unless the user explicitly excludes some.
- Do not collapse a wide spreadsheet into Date/Description/Amount unless the
  user asked for that simplified transaction format.
- Use `result_operations` for whole-spreadsheet edits such as sorting.

Example of desired clarification style:

> For file 1 (bank.csv), I would use `Posted Date` as the date column. For file
> 2 (revolut.csv), I would use `Completed Date`. Is that right?

### Column Mapping Page

Added a column mapping review page:

- Route: `/mergesets/<pk>/column-mapping/`
- View: `MergesetColumnMappingView`
- Template: `core/templates/core/mergesets/mergeset_column_mapping.html`

It shows:

- Final columns
- Per-file mappings
- Ignored columns
- Transform notes
- Result operations
- Spreadsheet preview

The AI suggestions page reveals a "Review column mapping" link once a plan is
ready.

### Deterministic Preview

Added `core/services/merge_preview.py`.

The preview applies the saved `MergePlan.plan_json` to uploaded CSV rows.

Current behavior:

- Reads parsed CSV files from storage.
- Builds merged preview rows according to `file_mappings`.
- Shows all rows by default.
- Supports an optional preview `limit`.
- Applies `result_operations`, including chronological sorting for recognized
  date values.
- Normalizes recognized date values to ISO `YYYY-MM-DD` when the mapping uses
  `parse_date`.
- Also normalizes recognized date values when the final output column type is
  `date`, even if the AI produced a `copy` transform.

Normalization behavior and limitations:

- Money-typed output columns normalize amounts using the mapping's explicit
  `amount_format`, or the legacy default separators when omitted. The
  `parse_amount` transform alone does not normalize non-money output columns.
- Date parsing supports common bank-export formats, but ambiguous numeric dates
  are interpreted with day-first formats before month-first formats.
- Unrecognized date values are kept as their original text and sorted after
  recognized dates. Invalid non-empty date-typed values or `parse_date` results
  also create blocking exceptions that prevent export.

### Preview UI

The final preview table was made collapsible:

- Preview is not tall by default.
- A button toggles between showing and hiding it.
- Expanded preview scrolls within a bounded area.
- JS lives in `core/static/core/js/column_mapping.js`.

### AI Plan Revision

Added AI edits from the column mapping page:

- Service: `core/services/ai_revision.py`
- Form: `MergePlanRevisionForm`
- The user can ask for changes after seeing the preview, such as sorting rows.
- The revision service sends the current plan, the user's instruction, and a
  preview sample to OpenAI.
- OpenAI must return a full `mapping_ready` plan, not a partial patch.
- New revised plans are saved as new `MergePlan` rows.

Important limitation:

- The AI revises the plan JSON. The actual preview is still generated
  deterministically by Python from that plan.
- Sorting recognizes supported date formats and orders them chronologically;
  unrecognized values follow recognized dates in their original relative order.
  When no values parse as dates, sorting falls back to text ordering.

### Encoding

CSV decoding now accepts more than strict UTF-8:

- `utf-8-sig`
- `cp1252`
- `iso-8859-1`

`decode_csv_content` is shared by CSV parsing and preview generation.

This means common files with characters like `Café` can be parsed and previewed.

### Currency Planning Contract

The AI planning response contract includes currency intent and explicit amount
locale metadata. Conversion is executed only by deterministic Python services.

Added:

- `output_currency`
- `currency_conversion`
- Per-file `detected_currency`
- `convert_currency` transform
- Optional `amount_format` with decimal and thousands separators for amount
  mappings

The prompt tells the AI to detect source currencies from currency columns,
headers, symbols, filenames, and sample rows. If currency conversion is needed
but the source currency is ambiguous, the AI should ask a concrete question
naming the file and evidence. Exchange rates must not be invented by AI; the
deterministic exchange-rate service described below supplies cached/provider rates.

### Exchange Rate Cache

Added deterministic exchange-rate foundations:

- Model: `ExchangeRate`
- Service: `core/services/exchange_rates.py`
- Migration: `core/migrations/0009_exchangerate.py`

The service supports:

- Same-currency rates as `1`
- Cached monthly average lookup
- Provider-based fetch and cache-on-miss
- Default Frankfurter provider for monthly grouped historical rates
- Validation for three-letter currency codes, valid months, and positive rates
- Clear `ExchangeRateError` failures for missing or invalid rate data

The default provider is Frankfurter's public v2 API. Tests use fake providers and
fake HTTP responses, so the test suite does not depend on live network access.
Preview and export now apply `convert_currency` through the deterministic preview
layer. If conversion cannot be completed for a row, SheetMerge leaves the
converted cell blank, records a blocking exception, and prevents CSV export.

Implemented conversion behavior:

- Uses the row month from a parsed date mapping.
- Uses per-file `detected_currency` and plan-level target currency.
- Uses cached/fetched monthly average rates via `get_monthly_average_rate`.
- Formats converted values to two decimal places.
- Records provenance for every successful conversion, including original and
  reporting values/currencies, rate, provider, period, policy, and rounding.
- Leaves converted values blank and blocks export when the amount,
  source/target currency, row date, or exchange-rate lookup is unavailable.
- Shows conversion intent, detected currencies, and warnings on the column
  mapping review page.

### Mapping Approval

The column mapping review page now supports approving the latest generated merge
plan.

Implemented approval behavior:

- Route: `/mergesets/<pk>/column-mapping/approve/`
- View: `MergesetApproveMappingView`
- Owner-only POST approval.
- Marks the latest merge plan as `approved`.
- Moves any other plans for the same mergeset back to `needs_review`.
- Marks the related planning session as `approved`.
- CSV export uses only the approved plan. If no approved plan exists, it
  redirects the owner to review/approval and does not create a download.
- Opening an approved mergeset resumes directly at the column mapping review.
- Approved workflows redirect direct AI chat access back to the review page.
- The review page hides the "Back to AI chat" action once the mapping is
  approved.

## Important Next Work

Date normalization and chronological sorting now exist in the deterministic
preview layer. The next practical work is to continue the end-to-end workflow:

1. Define data retention/deletion behavior, restrict sensitive logging, and
   disclose which source samples are sent to AI.

## Known Gaps

- Export/download is CSV-only.
- Date normalization currently outputs ISO `YYYY-MM-DD`.
- Date-aware sorting relies on recognized common date formats; unrecognized dates
  remain visible but sort after recognized dates.
- Existing plans without `amount_format` retain the legacy `.` decimal and `,`
  thousands default; review non-default source formats before approval.
- AI revisions can request operations that the deterministic preview layer must
  support; unsupported behavior should be handled in Python, not assumed from
  the AI text.
- Debit/credit amount transforms now avoid double minus signs when a debit value
  is already negative, and treat accounting parentheses like `(3.25)` as
  negative.

## File Size Notes

Files close to the 400-line policy:

- `core/tests/test_ai_suggestions.py` is 398 lines. Do not add more tests there;
  create a new test file.
- `core/tests/test_ai_planning_service.py` is 398 lines. Do not add more tests
  there; create a new focused test file or split existing tests.
- `core/views/mergesets.py` is 356 lines. Keep future view growth cautious.
- `core/tests/test_mergeset_file_uploads.py` is 336 lines.

## Test Status

The full suite passed on 2026-09-06: 154 tests in 105.196 seconds, using
`./.venv/bin/python manage.py test` in Ubuntu/WSL. Django system checks passed
and `manage.py makemigrations --check --dry-run` reported no changes.

On 2026-09-06, documentation was reconciled against the current implementation
for amount normalization, sorting, currency failures, and CSV-only support.
The subsequent commit-preparation session ran the checks above and excluded
generated `.playwright-mcp/` browser artifacts through `.gitignore`.

Documentation-only changes do not require the Django suite. For implementation
changes, create the ignored local virtual environment described in the README,
then run:

```bash
./.venv/bin/python manage.py test
```

## Suggested Commit Message

`feat: complete safe, auditable merge workflow`
