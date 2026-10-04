# TROUBLESHOOTING.md

Start with `python -m app doctor` (add `--online` to test live credentials).
Checks are PASS / WARN / FAIL; FAIL blocks production, WARN does not.

## Environment

| Symptom | Fix |
|---|---|
| `ffmpeg not found on PATH` | Install FFmpeg and open a new shell (`ffmpeg -version`) |
| `ffprobe` FAIL | ffprobe ships with FFmpeg — reinstall/repair the install |
| `module ... import ok` FAIL (pillow/numpy/…) | `pip install -r requirements.txt` into the active venv |
| `config` FAIL | `python -m app init` then fix `config/config.json` JSON errors |
| `state` FAIL | Ensure `state/` is writable; delete `.lock` leftovers if a run died mid-write |
| Tests fail locally with path errors | Run from the repo root: `python -m pytest -q` |

## Credentials

| Symptom | Cause / Fix |
|---|---|
| `groq_keys` FAIL "empty or placeholder" | Set `GROQ_API_KEYS` in `.env` (local) or GitHub Secrets |
| `groq_keys` WARN "failover needs 2+" | Add a second comma-separated key — not an error |
| Groq HTTP 401/403 repeatedly | Keys rotated/revoked — issue new keys; the client disables dead slots, then raises `GroqExhausted` |
| Groq error 1010 / Cloudflare ban | Client already sends the required User-Agent; if you changed code, keep `python-requests/2.32.3` |
| Groq 429/413 | Free-tier TPM/RPM (org-wide). Client waits same-slot, honoring `Retry-After` (default 62 s). Persistent 429 = you hit the 8K TPM / 30 RPM budget — reduce `max_tokens`/`reasoning_effort` or wait for the window |
| `telegram` WARN | `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` unset — alerts silently skipped while `telegram.notify_failure=false` |
| Telegram 403 | Bot removed from chat or token revoked — recreate via BotFather, update chat ID |
| `youtube` WARN (missing …) | Expected until you run `python -m app youtube-oauth` and add the 3 YouTube secrets ([SETUP.md](SETUP.md) §5) |
| YouTube `invalid_grant` | Refresh token revoked/expired (password change, consent reset) — redo `youtube-oauth`, update the secret |
| YouTube `quotaExceeded` | Your daily 10,000-unit pool is spent (unlikely at our load: ~910/day). Never set a retry loop on quota — the client classifies it as non-retryable and the episode FAILs for tomorrow's catch-up |

## Pipeline

| Symptom | Cause / Fix |
|---|---|
| `RED ALERT … stage: <X>` | Read the stage name: SCRIPT_QC → read `state/episodes/<id>/qc/script_qc.json`; RENDER_QC → `qc/video_qc.json`; UPLOADING → YouTube error in registry `error` field |
| `state wiring error` | A stage finished in an illegal state — bug in `_LONG_ORDER`/stage code; episode is FAILED with the message; report/fix, reset `attempts` |
| `StageUnavailable` (exit 2) | Code for a stage isn't in this checkout (partial deploy) — push the full tree |
| `attempt budget exhausted` | 3 failures used. Fix the root cause, set `"attempts": 0` in `state/registry.json`, push ([OPERATIONS.md](OPERATIONS.md)) |
| Dry-run stopped, nothing published | By design: state = `RENDER_QC`; dispatch a real run to publish |
| `no long-form job due now` | Outside the 16:00 UTC slot window or episode already advanced — `python -m app schedule` to inspect |
| `X is at <stage>; shorts day requires SHORTS_READY` | Long isn't finished/verified — run the long first (`plan_due` normally orders this for you) |
| Episode rebuilt unexpectedly | Fresh checkout lacked media (git carries state, never bytes) — the guard logs `missing … rebuilding from audio`. Normal after a crash; expensive only when TTS had to repeat |
| Upload took too long / job killed | 429s + slow uplink; runner limit is 6 h — check the Groq wait logs; retry resumes at verify if the ID checkpointed |

## Rendering / QC

| Symptom | Cause / Fix |
|---|---|
| `audio near silent` | Mix bug or missing WAVs — delete `state/episodes/<id>/audio/` and resume at AUDIO_READY |
| `duration … outside ±15 s` | Timing drift — check `timing.json` totals vs config `duration.*`; the sample flag (`--sample`) must never be used for real QC runs |
| `thumbnail … != JPEG 1280×720` | Thumbnail generator changed — see `render/thumbnail.py` |
| Whisper/`QC_TRANSCRIBE` failures | Opt-in only: set `QC_TRANSCRIBE=1` after the `tiny` model is cached; otherwise skip is normal |
| Render looks wrong / colors off | Art is committed under `assets/` — rebuild with `python -m app assets` |

## GitHub Actions

| Symptom | Fix |
|---|---|
| Workflow never triggers | `schedule` runs only on the **default branch**; check timezone (cron is UTC) |
| State push fails ("could not push state") | Someone pushed mid-run — the job rebase-retries 3×; if it persists, pull locally, push, re-run |
| `less than 4 GB free` | The disk-check step refused to build; it frees ~6 GB itself — if media accumulated (custom changes), trim `state/episodes/*/render/` |
| Secrets seem ignored | Secrets must exist with exact names; `.env` placeholders do **not** override real env vars — but unset secrets fall through to `.env`, which doesn't exist on runners |
| health-check red before setup | Expected: `groq_keys` FAIL until `GROQ_API_KEYS` is configured |
| Model downloads every run | The `models` cache missed — check `hashFiles('requirements.txt')` changed only when it should; add `restore-keys` (already present) |
