# PROJECT.md — Scope, Constraints, Delivery Status

## What this is

An autonomous production system for the kids' YouTube channel **Fernwood
Friends**: gentle animated woodland adventures for ages 4–8. One weekly cycle
produces **3 long episodes + 6 Shorts** with zero human editing, end to end.

## Fixed constraints

| Constraint | Value |
|---|---|
| Weekly output | 3 longs (8–10 min) + 2 Shorts each = 9 videos |
| Formats | Long: 1920×1080 @24fps H.264; Shorts: 1080×1920 @24fps |
| Language | English only (the only Arabic file is `SETUP_AR.md`) |
| Audience | Ages 4–8, Made-for-Kids via the YouTube API |
| Schedule | Mon/Wed/Fri longs, Tue/Thu/Sat Shorts, 16:00 UTC (config-driven) |
| Cost | $0/month recurring (free tiers: GitHub Actions public repo, Groq, YouTube API, Telegram) |
| Compute | GitHub Actions `ubuntu-latest` (4 vCPU / 16 GB / 14 GB SSD) |
| Autonomy | Fully automatic; Telegram SUCCESS/FAILED reports are the only touchpoint |
| Data store | Git-committed JSON state — no database, no extra services |

## Pipeline in one line

`Groq (content) → validation → Kokoro TTS → Pillow frames → FFmpeg encode →
script QC + video QC → YouTube upload + verify → Telegram report`, with an
idempotent `s01eNNN` state machine checkpointing every stage.

## Delivery status

| Layer | Status |
|---|---|
| Phases 1–6: config, state machine, schedule, content engine, audio, render | ✅ done, committed |
| QC gates (script + video, real PASS/FAIL) | ✅ done |
| YouTube publishing (OAuth, resumable upload, verify, thumbnails, Made-for-Kids) | ✅ done |
| Telegram SUCCESS/FAILED reporting | ✅ done |
| Workflows: production / manual / health-check (caching, disk checks, state push) | ✅ done |
| Docs (README, PROJECT, SETUP, SETUP_AR, ARCHITECTURE, OPERATIONS, TROUBLESHOOTING, SECURITY, CONTENT_SYSTEM) | ✅ done |
| Tests (offline/mocked suite, incl. real tiny ffmpeg probes) | ✅ green |
| Groq multi-key failover + `Retry-After` respect | ✅ done (2nd key pending user) |
| Repo + GitHub Secrets + YouTube channel/OAuth | ⬜ user's one-time setup ([SETUP.md](SETUP.md)) |
| First real episode on the runner | ⬜ after secrets are configured |

## Spec-compliance highlights

- **Idempotent**: one registry entry per schedule slot; retries reuse it —
  never duplicates an episode.
- **Resumable**: a killed run resumes at the exact stage; uploads checkpoint
  the video ID *before* verification, so resume is verify-only (never
  double-uploads); Shorts resume per-short (`rendered → uploaded`).
- **Bounded retries**: `qc.max_stage_retries` (default 3) enforced across
  runs; exhausted episodes go terminal with a RED ALERT.
- **Real QC**: script QC re-validates the package plus recipe/English-only/
  repetition rules; video QC probes codecs, resolution, fps, duration, loudness
  and thumbnail with `ffprobe`. Failures mark the episode FAILED — never
  uploaded.
- **Dry-run**: builds and QCs everything, publishes nothing; state stops at
  `RENDER_QC` so the next real run resumes *at* publish.
- **Fresh-checkout safety**: git carries state, never bytes — missing media is
  detected on resume and rebuilt instead of failing.
- **Secrets**: environment only (GitHub Secrets > `.env`), redacted in logs
  and alerts, key slots logged — never keys.
