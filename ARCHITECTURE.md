# ARCHITECTURE.md — Modules, State Machine, Data Flow

## Big picture

```
                 ┌────────────── GitHub Actions (ubuntu-latest) ──────────────┐
                 │  production.yml (cron Mon–Sat 16:05 UTC)                    │
                 │    python -m app produce                                    │
                 │      ├─ plan_due()  → which jobs are due                   │
                 │      ├─ run_long()  → PLANNED … SHORTS_READY   (long day)   │
                 │      └─ run_shorts()→ SHORTS_READY … COMPLETE  (shorts day) │
                 │    git push state/   (state in git, media never)            │
                 └─────────────────────────────────────────────────────────────┘
   Groq API                state/ (git)                YouTube API      Telegram
 content engine ──► registry + packages ──► uploads ──► + verify ──► SUCCESS/FAILED
```

## Module map

| Layer | Modules | Role |
|---|---|---|
| Entry | `cli.py` (`python -m app …`) | 11 subcommands; `produce` is the CI entry |
| Orchestration | `pipeline.py` | Runs `_LONG_ORDER` stages, checkpoints, alerts, dry-run gating, media guards, retry budget |
| State | `state.py` | `Stage` enum, `_TRANSITIONS`, `advance_path()`, atomic `Registry` (registry.json) |
| Schedule | `schedule.py` | Config-driven UTC slots, 26 h catch-up, `plan_due()` joins slots with registry |
| Content | `content/engine.py` `prompts.py` `validate.py` `shorts.py` `memory.py` `universe.py` | Groq recipes (universe/format/shorts/story), package validation, canon memory |
| LLM client | `groq_client.py` | Key-pool failover, bounded backoff, `Retry-After` on 429/413, slot-only logging |
| Audio | `audio/tts.py` (kokoro-onnx) `mix.py` `music.py` `sfx.py` `stages.py` | Line-cache TTS, 44.1 kHz stereo master + `timing.json` contract, procedural beds/SFX |
| Render | `render/scene.py` (Pillow) `video.py` (FFmpeg) `thumbnail.py` `art/` `stages.py` | Frames → H.264 parts → concat → mux; committed PNG art; JPEG thumbnail |
| QC | `qc/script_qc.py` `qc/video_qc.py` | Real PASS/FAIL gates (see [CONTENT_SYSTEM.md](CONTENT_SYSTEM.md)) |
| YouTube | `youtube/oauth.py` `metadata.py` `publish.py` `channel.py` `errors.py` | Installed-app OAuth, resumable upload, verify poll, thumbnails, quota classification |
| Infra | `config.py` `doctor.py` `telegram_client.py` `logging_setup.py` `retry.py` | Secrets precedence, health gate, reports, redaction |

## State machine

```
PLANNED → SCRIPTED → SCRIPT_QC → AUDIO_READY → RENDERING → RENDERED
        → RENDER_QC → UPLOADING → PUBLISHED → SHORTS_READY
        → SHORTS_SCHEDULED → COMPLETE
Any state → FAILED (bounded); COMPLETE/FAILED are terminal
```

- `transition()` enforces only the forward edges above; `advance_path()`
  bridges the two bookkeeping hops the linear pipeline needs
  (`RENDERING→RENDER_QC` via `RENDERED`, `UPLOADING→SHORTS_READY` via
  `PUBLISHED`). A wiring error marks FAILED + alerts — it never crashes raw.
- Idempotency: deterministic `s01eNNN` ids; one registry entry per schedule
  slot, so retries and re-runs reuse the same episode — never duplicate.
- Resume: `failed_stage` records where to re-enter; `_next_index()` resumes
  *at* the failed step, or at the step after one that completed.

## Long-day pipeline (`run_long`)

| # | Stage | Module:function | What happens |
|---|---|---|---|
| 1 | SCRIPTED | `content.engine:run_generation` | Groq builds package.json (universe → format → shorts → 14-scene story), validated + memory-checked |
| 2 | SCRIPT_QC | `qc.script_qc:check_script` | Re-validates + recipe/English/repetition rules → `qc/script_qc.json` |
| 3 | AUDIO_READY | `audio.stages:build_audio` | Kokoro TTS per line → scenes → master mix → `timing.json` (long + both shorts) |
| 4 | RENDERING | `render.stages:render_long` | Pillow frames → x264 parts → concat → mux → thumbnail |
| 5 | RENDER_QC | `qc.video_qc:check_video` | ffprobe: codec/resolution/fps/duration/loudness/thumbnail (+ optional Whisper) |
| 6 | UPLOADING | `youtube.publish:publish_long` | Resumable upload (ID checkpointed **before** verify) → verify poll → thumbnail → SUCCESS alert |
| 7 | SHORTS_READY | `content.shorts:build_short_packages` | Splits the 2 shorts into standalone docs, status `ready` |

Dry-run stops after #5 (state = `RENDER_QC`), so the next real run resumes
*at* publish with everything already QCd.

## Shorts-day pipeline (`run_shorts`)

Per-short statuses drive idempotency:
`ready → rendered → uploaded` (failures: `rendering_failed`, `upload_failed`).

```
render_shorts (audio if needed → vertical render)  →  publish_shorts
  only touches shorts whose status says work is needed; per-short checkpoints
```

## Persistence model (critical)

- **Git carries state, never bytes.** Committed: `state/registry.json`,
  `state/episodes/*/package.json`, `state/episodes/*/shorts/*.json`,
  `state/story_memory/`, docs, assets. Ignored: audio, renders, thumbnails,
  logs, models.
- Each workflow run starts from a fresh checkout. Before resuming a stage that
  needs media (render, publish), the pipeline checks the files exist; if not
  it **falls back to AUDIO_READY** (long) or flips the short back to `ready`
  (shorts) and rebuilds — instead of failing on missing bytes.
- After every run (even failed), `production.yml` commits and pushes `state/`
  so the next run resumes exactly where this one stopped.

## Failure handling

`_execute_stage` wraps every stage: on exception → `mark_failed` (stage +
error, attempts+1) → Telegram RED ALERT → `SystemExit(1)`;
`StageUnavailable` → exit 2. Retries are bounded across runs
(`qc.max_stage_retries`, default 3); an exhausted episode goes terminal with
a final alert (reset `attempts` in the registry to manually re-arm).

## Workflows

| Workflow | Trigger | Behavior |
|---|---|---|
| `production.yml` | cron `5 16 * * 1-6` + dispatch (production/dry-run/sample) | concurrency `production` (never cancels), pip + model caches, disk-free ≥ 4 GB check, thread caps, `produce`, always: push state; on failure: upload QC artifacts |
| `manual.yml` | dispatch: tests/doctor/status/schedule/snapshot/dry-run | same setup, never publishes; persists dry-run state |
| `health_check.yml` | daily 07:00 UTC + dispatch | pytest + offline doctor + online doctor when secrets exist; read-only |
