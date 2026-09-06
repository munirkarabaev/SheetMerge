# External Services and Sources

This file identifies external dependencies whose behavior affects SheetMerge.
Update it whenever a provider, API version, or data policy changes. Never put
credentials, access tokens, or private URLs here.

| Source | Purpose | Configuration | Failure behavior |
| --- | --- | --- | --- |
| OpenAI Responses API | Generates structured merge-planning and revision proposals | `OPENAI_API_KEY`, `OPENAI_MODEL` in ignored `.env` | The planning request returns an error; no merge is executed from model text. |
| Frankfurter v2 API | Fetches monthly historical currency averages on cache miss | No local key currently required | Preserve source data and show the preview row with a blank converted cell, a warning, and a blocking exception; prevent export until resolved. |
| Google OAuth via django-allauth | Optional sign-in provider | `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET` in ignored `.env` | Google sign-in is unavailable; email/password auth remains available. |

See `.env.template` for variable names and `core/services/exchange_rates.py` for
the provider integration.
