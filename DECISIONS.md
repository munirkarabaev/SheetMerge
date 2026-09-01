# Architecture Decision Log

Record decisions that affect future implementation or operations. Keep each
entry short, dated, and focused on the decision and its consequence; do not use
this file for a running task list.

## 2026-09-01 — Local development environment

Use a project-local `.venv` created from `requirements.txt`. Virtual
environments, `.env`, SQLite data, and uploaded media are local machine state
and are intentionally excluded from Git.

## 2026-06-19 — Deterministic execution after AI planning

OpenAI produces a validated mapping plan, but Python applies previews, sorting,
normalization, currency conversion, and export. This keeps user-facing output
reproducible and prevents free-form model output from changing data directly.

## 2026-06-19 — Exchange-rate source and cache

Use cached monthly average rates and the Frankfurter provider on cache miss.
Missing or invalid rate data must preserve the original row and surface a
warning rather than prevent the full preview/export.
