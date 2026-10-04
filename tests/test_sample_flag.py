"""Regression tests for `--sample`: ctx["sample_sec"] must reach the builders.

The bug: pipeline.py sets ctx["sample_sec"] but the stage wrappers read
ctx.get("sample") (never set), so `--sample N` silently rendered the FULL
episode. These tests pin the ctx key AND the render budget math (frames
actually emitted == sample_sec * fps) with ffmpeg fully mocked out.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.audio import stages as audio_stages
from app.config import Config
from app.render import stages as render_stages
from app.render import video as video_mod
from app.state import load_registry


def _cfg(state: Path) -> Config:
    return Config(
        data={
            "paths": {"state": str(state), "workspace": str(state / "workspace")},
            "render": {"fps": 24, "width": 64, "height": 64,
                       "short_width": 64, "short_height": 64, "audio_bitrate": "192k"},
        },
        path=state / "config.json",
    )


def _registry(state: Path) -> tuple:
    reg = load_registry(state)
    ep_id = reg.episode_id_for_slot("test-slot")
    return reg, ep_id


# --- pipeline: cli --sample -> ctx -----------------------------------------


def test_run_long_ctx_carries_sample_sec(tmp_path, monkeypatch):
    from app import pipeline

    state = tmp_path / "state"
    reg, ep_id = _registry(state)
    cfg = _cfg(state)
    monkeypatch.setattr(pipeline, "_load", lambda eid: (cfg, reg, reg.get(eid)))

    seen: list[dict] = []

    def fake_exec(cfg_, reg_, eid, stage, module, func, ctx):
        seen.append(dict(ctx))
        reg_.get(eid)["stage"] = stage.value  # bypass transition legality (tested elsewhere)

    monkeypatch.setattr(pipeline, "_execute_stage", fake_exec)
    pipeline.run_long(ep_id, dry_run=True, sample_sec=25)

    assert seen, "pipeline executed no stages"
    assert all(c["sample_sec"] == 25 for c in seen)
    assert all(c["kind"] == "long" for c in seen)


# --- stage: build_audio -----------------------------------------------------


def test_build_audio_reads_sample_sec(tmp_path, monkeypatch):
    state = tmp_path / "state"
    reg, ep_id = _registry(state)
    ep_dir = state / "episodes" / ep_id
    ep_dir.mkdir(parents=True)
    (ep_dir / "package.json").write_text(json.dumps({"episode_id": ep_id}), encoding="utf-8")

    seen: dict = {}

    def fake_build(cfg, episode_id, package, state_root, limit_scenes=None):
        seen["limit_scenes"] = limit_scenes
        return {"total": 12.3}

    monkeypatch.setattr(audio_stages, "build_long_audio", fake_build)
    cfg = _cfg(state)

    audio_stages.build_audio(cfg, reg, ep_id, {"sample_sec": 25})
    assert seen["limit_scenes"] == 1  # int(25/30)+1

    audio_stages.build_audio(cfg, reg, ep_id, {"sample_sec": 90})
    assert seen["limit_scenes"] == 4  # int(90/30)+1

    audio_stages.build_audio(cfg, reg, ep_id, {})
    assert seen["limit_scenes"] is None  # full episode


# --- stage: render_long -----------------------------------------------------


def _write_long_inputs(state: Path, ep_id: str, scenes: int = 3, dur: float = 30.0) -> Path:
    ep_dir = state / "episodes" / ep_id
    (ep_dir / "audio").mkdir(parents=True, exist_ok=True)
    (ep_dir / "package.json").write_text(
        json.dumps({"episode_id": ep_id, "title": "T", "scenes": [{}] * scenes}), encoding="utf-8"
    )
    timing = {
        "kind": "long",
        "episode_id": ep_id,
        "total": scenes * dur,
        "scenes": [
            {"start": i * dur, "duration": dur, "end": (i + 1) * dur, "lines": [],
             "file": f"scene_{i + 1}.wav"}
            for i in range(scenes)
        ],
    }
    (ep_dir / "audio" / "timing.json").write_text(json.dumps(timing), encoding="utf-8")
    return ep_dir


def test_render_long_passes_sample_sec(tmp_path, monkeypatch):
    state = tmp_path / "state"
    reg, ep_id = _registry(state)
    _write_long_inputs(state, ep_id)

    seen: dict = {}

    def fake_render(cfg, episode_id, package, timing, state_root, sample_sec=None, thumb_dir=None):
        seen["sample_sec"] = sample_sec
        return Path(state_root) / "episodes" / episode_id / "render" / "long.mp4"

    monkeypatch.setattr(render_stages, "render_long_video", fake_render)
    monkeypatch.setattr(render_stages, "render_thumbnail", lambda cfg, pkg, p: p)
    cfg = _cfg(state)

    render_stages.render_long(cfg, reg, ep_id, {"sample_sec": 25})
    assert seen["sample_sec"] == 25
    assert reg.get(ep_id)["video_path"]

    render_stages.render_long(cfg, reg, ep_id, {})
    assert seen["sample_sec"] is None


# --- stage: render_shorts ---------------------------------------------------


def test_render_shorts_passes_sample_sec(tmp_path, monkeypatch):
    state = tmp_path / "state"
    reg, ep_id = _registry(state)
    ep_dir = state / "episodes" / ep_id
    (ep_dir / "audio").mkdir(parents=True, exist_ok=True)
    short_doc = ep_dir / "shorts" / "short_1.json"
    short_doc.parent.mkdir(parents=True, exist_ok=True)
    short_doc.write_text(json.dumps({"short_id": "short_1", "dialogue": []}), encoding="utf-8")
    timing = {"total": 0, "scenes": [],
              "shorts": [{"short_id": "short_1", "duration": 30.0, "file": "short_1.wav", "lines": []}]}
    (ep_dir / "audio" / "timing.json").write_text(json.dumps(timing), encoding="utf-8")

    entry = reg.get(ep_id)
    entry["shorts"] = {"short_1": {"status": "ready", "file": str(short_doc), "title": "t", "kind": "wonder"}}
    reg.save()

    seen: dict = {}

    def fake_short(cfg, episode_id, short, short_timing, index, state_root, sample_sec=None):
        seen["sample_sec"] = sample_sec
        return Path(state_root) / "episodes" / episode_id / "render" / f"short_{index}.mp4"

    monkeypatch.setattr(render_stages, "render_short_video", fake_short)
    cfg = _cfg(state)

    render_stages.render_shorts(cfg, reg, ep_id, {"sample_sec": 15})
    assert seen["sample_sec"] == 15
    assert reg.get(ep_id)["shorts"]["short_1"]["status"] == "rendered"


# --- budget math: frames actually emitted -----------------------------------


class _FakePipe:
    def __init__(self):
        self.writes = 0
        self.bytes = 0

    def write(self, b: bytes):
        self.writes += 1
        self.bytes += len(b)

    def close(self):
        pass


class _FakeProc:
    def __init__(self):
        self.stdin = _FakePipe()
        self.stderr = SimpleNamespace(read=lambda: b"")

    def wait(self):
        return 0

    def poll(self):
        return 0

    def kill(self):
        pass


@pytest.mark.parametrize("sample_sec,expected_frames,expected_parts", [
    (10, 240, 1),   # 10s * 24fps, only scene 0
    (25, 600, 1),   # 25s of a 30s scene
    (None, 2160, 3),  # full 90s episode, 3 parts
])
def test_render_long_video_budget(tmp_path, monkeypatch, sample_sec, expected_frames, expected_parts):
    """With ffmpeg mocked, `sample_sec` must cap frames at sample_sec*fps."""
    state = tmp_path / "state"
    ep_dir = _write_long_inputs(state, "s01e001", scenes=3, dur=30.0)
    cfg = _cfg(state)
    package = json.loads((ep_dir / "package.json").read_text(encoding="utf-8"))
    timing = json.loads((ep_dir / "audio" / "timing.json").read_text(encoding="utf-8"))

    procs: list[_FakeProc] = []

    def fake_spawn(path, w, h, fps):
        proc = _FakeProc()
        procs.append(proc)
        return proc

    def fake_frame(scene, t, dur, cfg_, frame_w=0, frame_h=0, **kw):
        return SimpleNamespace(tobytes=lambda: b"\x00" * (frame_w * frame_h * 3))

    monkeypatch.setattr(video_mod, "_spawn", fake_spawn)
    monkeypatch.setattr(video_mod, "render_frame", fake_frame)
    monkeypatch.setattr(video_mod, "subprocess",
                        SimpleNamespace(run=lambda *a, **k: SimpleNamespace(returncode=0)))

    out = video_mod.render_long_video(cfg, "s01e001", package, timing, state,
                                      sample_sec=sample_sec, thumb_dir=None)

    assert out.name == "long.mp4"
    assert len(procs) == expected_parts
    total_frames = sum(p.stdin.writes for p in procs)
    assert total_frames == expected_frames
    assert sum(p.stdin.bytes for p in procs) == expected_frames * 64 * 64 * 3
