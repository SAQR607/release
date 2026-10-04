# Fernwood Friends — Autonomous Kids' YouTube Pipeline

A fully automated content system: **Groq writes the scripts → Kokoro speaks them →
Pillow/FFmpeg render 2D animation → QC gates every output → YouTube publishes →
Telegram reports.** GitHub Actions is the production computer; the whole system
runs at $0/month recurring cost.

**Output:** 3 long episodes/week (8–10 min, 1920×1080) + exactly 2 Shorts per
long (25–45 s, 1080×1920) — 9 videos/week, English only, ages 4–8.

## Quick start (development machine)

```bash
python3.12 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m app init            # creates config/config.json + .env template
$EDITOR .env                  # add your Groq key (and optionally Telegram)
python -m app doctor          # environment gate — must be PASS
python -m pytest -q           # full test suite (all offline/mocked)
```

FFmpeg must be on `PATH` (`ffmpeg -version`).

> **Rule: production never runs locally.** Full TTS, full renders, Whisper and
> end-to-end runs belong on GitHub Actions (see [SETUP.md](SETUP.md)). The local
> machine is for code, tests, tiny samples and git only.

## Commands

| Command | Purpose |
|---|---|
| `python -m app init` | Create config/state/workspace scaffolding |
| `python -m app doctor [--online]` | Environment + credential gate |
| `python -m app status` | Episode stages at a glance |
| `python -m app schedule [--json]` | Which jobs are due right now |
| `python -m app produce [--dry-run] [--sample N]` | Run **every** due job (production entry) |
| `python -m app run [--episode ID]` | Long-day pipeline (build → QC → publish) |
| `python -m app run-shorts --episode ID` | Shorts-day pipeline (render → publish) |
| `python -m app dry-run [--episode ID] [--sample N]` | Full build + QC, publishing stubbed |
| `python -m app youtube-oauth` | One-time OAuth flow → refresh token |
| `python -m app snapshot [--telegram]` | Channel stats report |
| `python -m app assets` | Rebuild committed art assets |

## Production (GitHub Actions)

Three workflows in `.github/workflows/`:

- **`production.yml`** — cron `5 16 * * 1-6` (Mon–Sat, 5 min after the 16:00
  UTC slots) or manual dispatch (`production` / `dry-run` / `sample` modes).
  Runs `produce`, then pushes updated state back to the repo.
- **`manual.yml`** — on-demand tests, doctor, status, snapshot, dry-run.
- **`health_check.yml`** — daily tests + doctor (online when secrets exist).

State (registry, packages, story memory) lives in git; media never does — the
pipeline rebuilds anything missing on a fresh checkout. See
[OPERATIONS.md](OPERATIONS.md).

## Documentation

| Document | Contents |
|---|---|
| [PROJECT.md](PROJECT.md) | Scope, constraints, delivery status |
| [SETUP.md](SETUP.md) | English setup guide (repo, secrets, OAuth) |
| [SETUP_AR.md](SETUP_AR.md) | دليل الإعداد بالعربية |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Modules, state machine, data flow |
| [OPERATIONS.md](OPERATIONS.md) | Runbook: schedules, resumes, recovery |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Errors and their fixes |
| [SECURITY.md](SECURITY.md) | Secrets handling and redaction |
| [CONTENT_SYSTEM.md](CONTENT_SYSTEM.md) | Prompts, recipes, QC rules |

## Universe

The show bible lives in `universe/` (characters, locations, brand, world) and
drives every generation prompt.
