# Roadmap

## Product direction

SheetMerge is a financial-export normalization and reconciliation layer for
recurring monthly-close work. It is not a generic spreadsheet-merging tool and
not a replacement for accounting software. Its output should feed an
accountant's workflow or an established system such as Xero or QuickBooks.

The initial customer to validate is a bookkeeper or accountant who repeatedly
collects exports for small businesses. A representative customer receives
monthly Revolut Business, card, Stripe, and Shopify CSV exports, then needs a
clean, traceable dataset without rebuilding a spreadsheet each month.

The product promise is: turn approved recurring bank, card, and platform
exports into a repeatable, auditable monthly dataset that an accountant can
trust. The primary value is saved close-process time, repeatability, and
exception handling—not lower AI-token usage.

### AI role and operating model

- For a new or changed source format, AI may inspect headers and a small,
  representative sample and propose a constrained mapping plan.
- A human reviews and approves the proposed mapping and its accounting-sensitive
  assumptions.
- Deterministic code applies the approved plan to every row; AI must not run per
  row, generate executable transformations, invent amounts/dates/currencies, or
  invent exchange rates.
- Approved plans become reusable source profiles keyed to a source-schema
  fingerprint. Known formats should normally run with no AI call.
- AI is used again only for low-confidence or changed formats, and the result is
  reviewed before it affects an export.

### Product progression

1. Manual CSV upload with approved source profiles, safe normalization,
   provenance, exceptions, reconciliation, and accountant-ready export.
2. A recurring "upload this month's files" close workflow using saved profiles.
3. Controlled file-inbox or cloud-folder import.
4. Direct integrations only for a small number of validated, high-demand
   sources; Revolut is a later candidate, not an initial dependency.

## Completed foundations

- Django project, custom user accounts, and dashboard
- Mergesets, file upload, CSV parsing, and spreadsheet previews
- AI-assisted planning and semantically validated, constrained mapping plans
- Deterministic mapping preview and mandatory human mapping approval
- Approval-only CSV export with spreadsheet-formula protection
- Export-blocking validation exceptions for dates, amounts, and currency
  conversion failures
- Explicit US/European amount normalization rules
- Transaction and currency-conversion provenance in exports
- Reconciliation totals, open-exception review, and a completed-workflow screen
- Deterministic monthly exchange-rate conversion with cached provider rates

## Next: prepare safely for real customer financial data

- Define data retention and deletion behavior for uploaded source files,
  previews, plans, and exports.
- Restrict and audit sensitive-data logging; ensure error reports do not expose
  financial rows, samples, or secrets.
- Clearly disclose which representative source samples are sent to AI, why, and
  when; obtain any necessary customer acknowledgement.
- Bound upload sizes, row counts, and processing time; paginate previews and
  make failure states deterministic.
- Move the Django secret key and debug setting to environment-based development
  and production configuration.

## Before using real customer financial data

- Complete every item in “Next: prepare safely for real customer financial
  data,” and test the resulting controls with representative non-customer data.

## Before charging customers or public launch

- Use PostgreSQL and private production file storage with backups and restoration
  procedures.
- Configure HTTPS, secure cookies, allowed hosts, security headers, monitoring,
  rate limits, dependency maintenance, and incident handling.
- Move long-running imports/exports into idempotent background jobs with status,
  retries, and cancellation.
- Add saved source profiles based on source-schema fingerprints so approved
  mappings can be reused without another AI call.
- Provide customer-visible spend controls and clear pricing rather than treating
  raw token counts as a monetary balance.
- Add privacy terms, support procedures, and appropriate financial-data
  operational controls.

## Later enhancements

- Add XLSX import/export if it remains a validated product requirement.
- Transaction grouping and categorization.
- Richer conversational corrections, constrained by deterministic execution.
- Controlled duplicate-candidate detection with explanations.
- File-inbox or cloud-folder imports, then selective direct integrations only
  after the recurring file-upload workflow is validated.

## Deliberately do not build yet

- A full accounting platform or general ledger.
- Generic AI spreadsheet transformations or per-row LLM processing.
- Broad bank OAuth integrations, PDF extraction, or a large connector catalogue.
