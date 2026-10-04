"""Video QC tests: probe logic (mocked ffprobe), stage PASS/FAIL, real ffmpeg smoke."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from app.qc import video_qc
from app.qc.video_qc import VideoQCError, check_video, probe_video
from app.state import load_registry
from qc_fixtures import qc_cfg

HAS_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def _probe_data(w=1920, h=1080, fps="24/1", dur=10.0, audio=True):
    streams = [{"codec_type": "video", "codec_name": "h264",
                "width": w, "height": h, "r_frame_rate": fps}]
    if audio:
        streams.append({"codec_type": "audio", "codec_name": "aac", "sample_rate": "44100"})
    return {"streams": streams, "format": {"duration": str(dur)}}


def _fake_file(path: Path, size: int = 200_000) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x00" * size)
    return path


def _make_thumb(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.effect_noise((1280, 720), 64).convert("RGB").save(path, "JPEG", quality=92)
    return path


# --- probe_video ------------------------------------------------------------


@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg/ffprobe not installed")
def test_probe_real_ffmpeg_smoke(tmp_path):
    out = tmp_path / "tiny.mp4"
    subprocess.run(
        [shutil.which("ffmpeg"), "-y", "-loglevel", "error",
         "-f", "lavfi", "-i", "color=c=blue:s=64x36:r=24:d=1",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
         "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-shortest", str(out)],
        check=True,
    )
    errors = probe_video(out, width=64, height=36, fps=24, duration=1.0,
                         duration_tol=0.6, min_bytes=100)
    assert errors == []


def test_probe_missing_file(tmp_path):
    errs = probe_video(tmp_path / "nope.mp4")
    assert "missing file" in errs[0]


def test_probe_too_small(tmp_path):
    p = _fake_file(tmp_path / "v.mp4", 100)
    errs = probe_video(p, min_bytes=100_000)
    assert any("too small" in e for e in errs)


def test_probe_wrong_resolution(monkeypatch, tmp_path):
    p = _fake_file(tmp_path / "v.mp4")
    monkeypatch.setattr(video_qc, "_ffprobe", lambda path: _probe_data(w=640, h=360))
    errs = probe_video(p, width=1920, height=1080)
    assert any("width" in e for e in errs) and any("height" in e for e in errs)


def test_probe_no_audio(monkeypatch, tmp_path):
    p = _fake_file(tmp_path / "v.mp4")
    monkeypatch.setattr(video_qc, "_ffprobe", lambda path: _probe_data(audio=False))
    errs = probe_video(p, require_audio=True)
    assert any("no audio stream" in e for e in errs)


def test_probe_duration_mismatch(monkeypatch, tmp_path):
    p = _fake_file(tmp_path / "v.mp4")
    monkeypatch.setattr(video_qc, "_ffprobe", lambda path: _probe_data(dur=5.0))
    errs = probe_video(p, duration=480.0, duration_tol=6.0)
    assert any("duration" in e for e in errs)


def test_probe_bad_fps(monkeypatch, tmp_path):
    p = _fake_file(tmp_path / "v.mp4")
    monkeypatch.setattr(video_qc, "_ffprobe", lambda path: _probe_data(fps="30/1"))
    errs = probe_video(p, fps=24)
    assert any("fps" in e for e in errs)


def test_probe_volume_checks(monkeypatch, tmp_path):
    p = _fake_file(tmp_path / "v.mp4")
    monkeypatch.setattr(video_qc, "_ffprobe", lambda path: _probe_data())
    monkeypatch.setattr(video_qc, "_volume_db", lambda path: -70.0)
    assert any("near silent" in e for e in probe_video(p, check_volume=True))
    monkeypatch.setattr(video_qc, "_volume_db", lambda path: None)
    assert any("loudness" in e for e in probe_video(p, check_volume=True))
    monkeypatch.setattr(video_qc, "_volume_db", lambda path: -18.5)
    assert probe_video(p, check_volume=True) == []


# --- check_video stage ------------------------------------------------------


def _setup(tmp_path):
    state = tmp_path / "state"
    reg = load_registry(state)
    ep_id = reg.episode_id_for_slot("slot")
    base = state / "episodes" / ep_id
    (base / "audio").mkdir(parents=True, exist_ok=True)
    (base / "audio" / "timing.json").write_text(json.dumps({"total": 10.0}), encoding="utf-8")
    video = _fake_file(base / "render" / "long.mp4")
    thumb = _make_thumb(base / "render" / "thumb.jpg")
    entry = reg.get(ep_id)
    entry["video_path"] = str(video)
    entry["thumbnail_path"] = str(thumb)
    reg.save()
    return qc_cfg(state), reg, ep_id, base


def test_stage_passes_sample_mode(tmp_path, monkeypatch):
    cfg, reg, ep_id, base = _setup(tmp_path)
    monkeypatch.setattr(video_qc, "_ffprobe", lambda path: _probe_data(dur=10.0))
    monkeypatch.setattr(video_qc, "_volume_db", lambda path: -20.0)

    check_video(cfg, reg, ep_id, {"sample_sec": 10})

    report = json.loads((base / "qc" / "video_qc.json").read_text(encoding="utf-8"))
    assert report["status"] == "PASS"
    assert report["sample"] is True
    assert reg.get(ep_id)["video_qc"]["status"] == "PASS"


def test_stage_duration_from_timing_when_no_sample(tmp_path, monkeypatch):
    cfg, reg, ep_id, base = _setup(tmp_path)
    monkeypatch.setattr(video_qc, "_ffprobe", lambda path: _probe_data(dur=10.0))
    monkeypatch.setattr(video_qc, "_volume_db", lambda path: -20.0)

    check_video(cfg, reg, ep_id, {})
    report = json.loads((base / "qc" / "video_qc.json").read_text(encoding="utf-8"))
    assert report["status"] == "PASS"
    assert report["expected_duration_sec"] == 10.0


def test_stage_wrong_resolution_fails(tmp_path, monkeypatch):
    cfg, reg, ep_id, base = _setup(tmp_path)
    monkeypatch.setattr(video_qc, "_ffprobe", lambda path: _probe_data(w=640, h=360, dur=10.0))
    monkeypatch.setattr(video_qc, "_volume_db", lambda path: -20.0)

    with pytest.raises(VideoQCError, match="width"):
        check_video(cfg, reg, ep_id, {"sample_sec": 10})
    report = json.loads((base / "qc" / "video_qc.json").read_text(encoding="utf-8"))
    assert report["status"] == "FAIL"


def test_stage_missing_video_fails(tmp_path):
    cfg, reg, ep_id, base = _setup(tmp_path)
    reg.get(ep_id)["video_path"] = str(tmp_path / "gone.mp4")
    reg.save()
    with pytest.raises(VideoQCError, match="missing file"):
        check_video(cfg, reg, ep_id, {"sample_sec": 10})


def test_stage_silent_audio_fails(tmp_path, monkeypatch):
    cfg, reg, ep_id, base = _setup(tmp_path)
    monkeypatch.setattr(video_qc, "_ffprobe", lambda path: _probe_data(dur=10.0))
    monkeypatch.setattr(video_qc, "_volume_db", lambda path: -70.0)
    with pytest.raises(VideoQCError, match="near silent"):
        check_video(cfg, reg, ep_id, {"sample_sec": 10})


def test_stage_missing_thumbnail_fails(tmp_path, monkeypatch):
    cfg, reg, ep_id, base = _setup(tmp_path)
    monkeypatch.setattr(video_qc, "_ffprobe", lambda path: _probe_data(dur=10.0))
    monkeypatch.setattr(video_qc, "_volume_db", lambda path: -20.0)
    Path(reg.get(ep_id)["thumbnail_path"]).unlink()
    with pytest.raises(VideoQCError, match="thumbnail missing"):
        check_video(cfg, reg, ep_id, {"sample_sec": 10})


def test_transcribe_gate_fails_on_empty(tmp_path, monkeypatch):
    cfg, reg, ep_id, base = _setup(tmp_path)
    monkeypatch.setattr(video_qc, "_ffprobe", lambda path: _probe_data(dur=10.0))
    monkeypatch.setattr(video_qc, "_volume_db", lambda path: -20.0)
    monkeypatch.setenv("QC_TRANSCRIBE", "1")
    monkeypatch.setattr(video_qc, "_transcribe", lambda path, seconds: "")
    with pytest.raises(VideoQCError, match="transcript too short"):
        check_video(cfg, reg, ep_id, {"sample_sec": 10})


def test_transcribe_gate_passes_on_text(tmp_path, monkeypatch):
    cfg, reg, ep_id, base = _setup(tmp_path)
    monkeypatch.setattr(video_qc, "_ffprobe", lambda path: _probe_data(dur=10.0))
    monkeypatch.setattr(video_qc, "_volume_db", lambda path: -20.0)
    monkeypatch.setenv("QC_TRANSCRIBE", "1")
    monkeypatch.setattr(video_qc, "_transcribe",
                        lambda path, seconds: "Juni waited patiently by the stream with friends.")
    check_video(cfg, reg, ep_id, {"sample_sec": 10})
    report = json.loads((base / "qc" / "video_qc.json").read_text(encoding="utf-8"))
    assert report["transcribed"] is True
