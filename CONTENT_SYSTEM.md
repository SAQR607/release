# CONTENT_SYSTEM.md — Prompts, Recipes, QC Rules

How a blank slot becomes a validated, publishable episode.

## The universe (what the model may use)

`universe/` holds the canon that every prompt is grounded in:

- `CHARACTER_BIBLE.md`, `LOCATION_BIBLE.md`, `STORY_BIBLE.md`,
  `WORLD_BIBLE.md`, `BRAND_BIBLE.md`, `ASSET_BIBLE.md`
- `manifest.json` — machine-readable cast (7 characters), locations (7),
  music moods, learning spines. Generation never invents out-of-canon names.

Regenerate committed art from the manifest: `python -m app assets`.

## Generation recipes (Groq `openai/gpt-oss-120b`)

Four sequential calls per long episode, JSON-mode, bounded by
`config.json → groq` (`max_tokens 5600`, `temperature 0.8`, attempts 6):

1. **Universe/season pass** — episode concept, cast roles, learning spine.
2. **Format pass** — title, description, tags within YouTube limits.
3. **Shorts pass** — exactly 2 shorts, self-contained vertical mini-stories,
   2 **different** moods from `SHORT_MOODS = funny | wonder | heart | music |
   surprise | playful`, each `<=40` char titles.
4. **Story pass** — **14 scenes × 5 dialogue lines** + narration per scene,
   with the `__PREMISE_JSON__` placeholder bound to the earlier passes.

Every response is parsed (`extract_json` handles fences/prose), validated
(`content/validate.py` — schema, durations, exactly-2-shorts, moods, voice
names, YouTube metadata caps), and checked against canon memory
(`story_memory/`, no re-used premises, no contradictory facts).

Episodes are idempotent: a valid `package.json` short-circuits regeneration.

## Audio contract

- **Voices**: config `voices` maps narrator + 7 characters to Kokoro voices
  (`af_bella`, `af_heart`, `am_michael`, …).
- **TTS**: kokoro-onnx (quantized, CPU, disk line-cache; thread cap
  `TTS_THREADS`). ~0.2× realtime — the dominant cost of an episode.
- **Mix**: per-scene WAVs → 44.1 kHz stereo master, ducked music bed
  (`music.enabled`, procedural royalty-free-by-construction), SFX layer,
  then a `timing.json` contract (durations, files, per-line timing) consumed
  by both the video renderer and Shorts.
- Music moods resolve via `MOOD_ALIASES` (`emotional→tender`,
  `discovery→wonder`); unknown moods fall back to `happy`.
- Shorts are held to 25–45 s by extending the music tail + end SFX.

## Script QC (`qc/script_qc.py`) — runs before any audio

Re-runs full package validation, then enforces:

| Rule | Bound |
|---|---|
| Dialogue lines per scene | 3–6 (recipe: exactly 5) |
| Words per dialogue line | 5–14 |
| Narration words per scene | 30–50 |
| Repeated phrase | never ≥3× identical |
| Speakers | exactly the cast in the manifest voices (narrator + 7) |
| Language | English only: Latin-1 letters/punct + typographic chars (`’ ‑ – “ ” …`); Arabic/CJK/Cyrillic/emoji = FAIL |
| Hook | warning if the first scene lacks a hook (not fatal) |
| Titles | no duplicate/re-used titles across episodes |

Writes `qc/script_qc.json` and records PASS/FAIL on the registry entry. FAIL
→ episode FAILED, nothing generated.

## Video QC (`qc/video_qc.py`) — runs before any upload

`ffprobe`/`ffmpeg` against config expectations:

| Check | Rule |
|---|---|
| Video stream | h264, exactly `render.width×height` (1920×1080 long / 1080×1920 short), fps = 24 ±0.5 |
| Duration | target ± `render_duration_tolerance_sec` (15 s) for longs, ±4 s shorts |
| Audio | aac present, loudness ≥ −45 dBFS (catches silent mixes) |
| Thumbnail | JPEG exactly 1280×720, 10 KB–2 MB (YouTube limits) |
| Transcript (opt-in) | `QC_TRANSCRIBE=1`: faster-whisper `tiny` int8 must find speech |

Writes `qc/video_qc.json`; FAIL → FAILED + RED ALERT, upload never attempted.

## Publishing (what the model's output becomes)

- Long: title/description/tags from the format pass + series line; category
  from `channel.youtube_category_id`; `privacy` per config (default public);
  `selfDeclaredMadeForKids=true`.
- Shorts: standalone body, **`#shorts`** tag, and a cross-link line back to
  the parent long's title.
- Upload is resumable; the video ID is checkpointed **before** verification;
  status must read `processed` (polled) before PUBLISHED is recorded; the
  thumbnail is best-effort (non-fatal).

## Memory

`state/story_memory/` stores canon facts + per-episode summaries so each new
script knows what already happened (nobody dies, nothing is forgotten, arcs
carry across the season).
