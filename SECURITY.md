# SECURITY.md — Secrets, Redaction, Least Privilege

## Rules

1. **Secrets live only in the environment.** Never in `config/*.json`, never in
   code, never in docs, never in git.
2. **Precedence:** real environment (GitHub Secrets) > `.env` file > nothing
   (`app/config.py`). On runners there is no `.env`; locally it is gitignored.
3. **Logs and alerts are redacted.** `logging_setup.redact()` masks values that
   look like keys/tokens; the Groq client logs only `groq_key_slot_used=<n>` —
   never a key; exceptions are truncated and redacted before reaching Telegram.

## Secret inventory

| Name | Where it lives | Used by |
|---|---|---|
| `GROQ_API_KEYS` | GitHub Secrets / `.env` | content generation (comma-separated pool) |
| `TELEGRAM_BOT_TOKEN` | GitHub Secrets / `.env` | SUCCESS / RED ALERT reports |
| `TELEGRAM_CHAT_ID` | GitHub Secrets / `.env` | report destination |
| `YOUTUBE_CLIENT_ID` / `YOUTUBE_CLIENT_SECRET` / `YOUTUBE_REFRESH_TOKEN` | GitHub Secrets / `.env` | Data API uploads |
| `GITHUB_TOKEN` | provided by Actions | state push (`contents: write`) — automatic, never hardcoded |

`.env.example` contains placeholders only (`REPLACE_…`), which `doctor`
treats as "not configured".

## What git refuses (`.gitignore`)

- Secrets: `.env`, `.env.*` (except the template), `client_secret*.json`,
  `credentials*.json`, `token*.json`, `*oauth*secret*`
- Media: `*.mp4/*.wav/…`, `workspace/`, `state/episodes/*/audio|video|render|qc|uploads/`
- Models/caches: `models/`, `.cache/`, `hf_home/`
- Logs: `*.log`, `logs/`

Tracked state (`registry.json`, packages, story memory) contains titles,
stages, QC results and YouTube **video IDs** — no secrets. Verify before
pushing: `git diff` and look.

## Workflow least privilege

| Workflow | Permissions | Why |
|---|---|---|
| `production`, `manual` | `contents: write` | push `state/` back after runs |
| `health_check` | `contents: read` | tests must not mutate the repo |

- Secrets are injected at job scope only where needed; workflows never echo
  them, and artifacts contain QC JSON + logs only (redacted).
- User inputs reach scripts via `env:` (not shell interpolation).
- Pushes use `GITHUB_TOKEN`, which does **not** trigger other workflows
  (no recursion); state commits also carry `[skip ci]`.
- `concurrency` prevents overlapping production runs.

## Telegram exposure

Messages contain: episode id, stage, truncated error (redacted), attempts,
YouTube link/privacy, QC statuses. **They never contain keys, tokens, URLs
with credentials, or file contents.**

## If a secret leaks

1. Rotate it at the source immediately (Groq console, BotFather, Google Cloud
   credentials, YouTube token via `youtube-oauth`).
2. Update the GitHub Secret (and local `.env`).
3. Check git history — if a real value was ever committed, rewriting history
   and forcing a push is required (prefer: rotate first, history cleanup later).
4. `doctor --online` to confirm the new credentials work.

## Local dev hygiene

- Never run production locally (also a machine-stability rule — see README).
- Don't paste keys into prompts, issues, screenshots, or log excerpts when
  asking for help — a `gsk_…` style masked prefix with the tail removed is
  enough to identify which key you mean.
