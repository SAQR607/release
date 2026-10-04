"""Pipeline wiring: state-machine bridging inside _execute_stage.

The stage tuples name the step that just ran (e.g. RENDER_QC), so two hops in
the linear order are illegal per _TRANSITIONS and need an intermediate
bookkeeping state. These tests pin the bridge and the failure path (wiring
error must mark FAILED, never crash raw).
"""

from __future__ import annotations

import pytest

from app import pipeline
from app.config import Config
from app.state import Stage, StateError, advance_path, load_registry

CFG = Config(data={"telegram": {"notify_failure": False}}, path=__file__)


# --- advance_path -----------------------------------------------------------


def test_advance_path_direct():
    assert advance_path(Stage.SCRIPTED, Stage.SCRIPT_QC) == [Stage.SCRIPT_QC]


def test_advance_path_same_is_empty():
    assert advance_path(Stage.RENDER_QC, Stage.RENDER_QC) == []


def test_advance_path_bridges_rendered():
    assert advance_path(Stage.RENDERING, Stage.RENDER_QC) == [Stage.RENDERED, Stage.RENDER_QC]


def test_advance_path_bridges_published():
    assert advance_path(Stage.UPLOADING, Stage.SHORTS_READY) == [Stage.PUBLISHED, Stage.SHORTS_READY]


def test_advance_path_unreachable_raises():
    with pytest.raises(StateError):
        advance_path(Stage.COMPLETE, Stage.PLANNED)
    with pytest.raises(StateError):
        advance_path(Stage.PLANNED, Stage.RENDER_QC)


# --- _execute_stage ---------------------------------------------------------


def _registry_at(tmp_path, stage: Stage):
    reg = load_registry(tmp_path / "state")
    ep_id = reg.episode_id_for_slot("slot")
    reg.get(ep_id)["stage"] = stage.value
    reg.save()
    return reg, ep_id


def _stub_call(monkeypatch, err: Exception | None = None):
    def fake_call(module, func, *args, **kwargs):
        if err is not None:
            raise err

    monkeypatch.setattr(pipeline, "_call", fake_call)


def test_execute_stage_bridges_rendering_to_render_qc(tmp_path, monkeypatch):
    reg, ep_id = _registry_at(tmp_path, Stage.RENDERING)
    _stub_call(monkeypatch)
    pipeline._execute_stage(CFG, reg, ep_id, Stage.RENDER_QC, "app.qc.video_qc", "check_video", {})
    assert reg.stage_of(ep_id) == Stage.RENDER_QC


def test_execute_stage_bridges_uploading_to_shorts_ready(tmp_path, monkeypatch):
    reg, ep_id = _registry_at(tmp_path, Stage.UPLOADING)
    _stub_call(monkeypatch)
    pipeline._execute_stage(CFG, reg, ep_id, Stage.SHORTS_READY, "app.content.shorts",
                            "build_short_packages", {})
    assert reg.stage_of(ep_id) == Stage.SHORTS_READY


def test_execute_stage_direct_hop(tmp_path, monkeypatch):
    reg, ep_id = _registry_at(tmp_path, Stage.SCRIPTED)
    _stub_call(monkeypatch)
    pipeline._execute_stage(CFG, reg, ep_id, Stage.SCRIPT_QC, "app.qc.script_qc", "check_script", {})
    assert reg.stage_of(ep_id) == Stage.SCRIPT_QC


def test_execute_stage_wiring_error_marks_failed(tmp_path, monkeypatch):
    reg, ep_id = _registry_at(tmp_path, Stage.PLANNED)
    _stub_call(monkeypatch)
    with pytest.raises(SystemExit):
        pipeline._execute_stage(CFG, reg, ep_id, Stage.COMPLETE, "m", "f", {})
    entry = reg.get(ep_id)
    assert entry["stage"] == Stage.FAILED.value
    assert entry["failed_stage"] == Stage.COMPLETE.value
    assert entry["attempts"] == 1
    assert "state wiring error" in entry["error"]


def test_execute_stage_failure_marks_failed_with_stage(tmp_path, monkeypatch):
    reg, ep_id = _registry_at(tmp_path, Stage.SCRIPTED)
    _stub_call(monkeypatch, err=ValueError("bad script"))
    with pytest.raises(SystemExit):
        pipeline._execute_stage(CFG, reg, ep_id, Stage.SCRIPT_QC, "m", "f", {})
    entry = reg.get(ep_id)
    assert entry["stage"] == Stage.FAILED.value
    assert entry["failed_stage"] == Stage.SCRIPT_QC.value
    assert "ValueError" in entry["error"]


def test_execute_stage_unavailable_exits_2(tmp_path, monkeypatch):
    reg, ep_id = _registry_at(tmp_path, Stage.AUDIO_READY)
    _stub_call(monkeypatch, err=pipeline.StageUnavailable("app.qc.video_qc not available yet"))
    with pytest.raises(SystemExit) as exc:
        pipeline._execute_stage(CFG, reg, ep_id, Stage.RENDERING, "m", "f", {})
    assert exc.value.code == 2


# --- dry-run gating ---------------------------------------------------------


def _record_run(monkeypatch, tmp_path, stages_out: list, dry: bool, shorts: bool = False):
    """Wire run_long/run_shorts to a recording fake _execute_stage."""
    from app.config import Config as _Config

    state = tmp_path / "state"
    reg = load_registry(state)
    ep_id = reg.episode_id_for_slot("slot")
    if shorts:
        reg.get(ep_id)["stage"] = Stage.SHORTS_READY.value
        vid = tmp_path / "short_1.mp4"
        vid.write_bytes(b"\x00")
        reg.get(ep_id)["shorts"] = {"short_1": {"status": "rendered", "file": "x",
                                                "title": "t", "video_path": str(vid)}}
    reg.save()
    cfg = _Config(data={"telegram": {"notify_failure": False},
                        "paths": {"state": str(state)}}, path=tmp_path / "c.json")
    monkeypatch.setattr(pipeline, "_load", lambda eid: (cfg, reg, reg.get(eid)))

    def fake_exec(cfg_, reg_, eid, stage, module, func, ctx):
        stages_out.append((stage, module, func, dict(ctx)))
        reg_.get(eid)["stage"] = stage.value  # bypass legal-hop checks (covered above)

    monkeypatch.setattr(pipeline, "_execute_stage", fake_exec)
    return reg, ep_id


def test_run_long_dry_stops_before_publish(tmp_path, monkeypatch):
    done: list = []
    reg, ep_id = _record_run(monkeypatch, tmp_path, done, dry=True)
    stage = pipeline.run_long(ep_id, dry_run=True, sample_sec=10)
    names = [s for s, *_ in done]
    assert names == [Stage.SCRIPTED, Stage.SCRIPT_QC, Stage.AUDIO_READY,
                     Stage.RENDERING, Stage.RENDER_QC]
    assert Stage.UPLOADING not in names
    assert stage == Stage.RENDER_QC
    assert reg.get(ep_id)["stage"] == Stage.RENDER_QC.value


def test_run_long_real_reaches_publish(tmp_path, monkeypatch):
    done: list = []
    reg, ep_id = _record_run(monkeypatch, tmp_path, done, dry=False)
    stage = pipeline.run_long(ep_id, dry_run=False, sample_sec=None)
    names = [s for s, *_ in done]
    assert Stage.UPLOADING in names and Stage.SHORTS_READY in names
    assert stage == Stage.SHORTS_READY


def test_run_shorts_dry_skips_publish_stage(tmp_path, monkeypatch):
    done: list = []
    reg, ep_id = _record_run(monkeypatch, tmp_path, done, dry=True, shorts=True)
    stage = pipeline.run_shorts(ep_id, dry_run=True)
    assert done == []  # rendered shorts: nothing to render, publish skipped
    assert stage == Stage.SHORTS_SCHEDULED
    assert reg.get(ep_id)["shorts"]["short_1"]["status"] == "rendered"


def test_run_shorts_real_publishes(tmp_path, monkeypatch):
    done: list = []
    reg, ep_id = _record_run(monkeypatch, tmp_path, done, dry=False, shorts=True)
    stage = pipeline.run_shorts(ep_id, dry_run=False)
    assert [f for _, _, f, _ in done] == ["publish_shorts"]
    assert stage == Stage.COMPLETE


# --- media guards (fresh checkout: git carries state, never bytes) ----------


def test_run_long_fresh_checkout_downgrades_to_audio(tmp_path, monkeypatch):
    done: list = []
    reg, ep_id = _record_run(monkeypatch, tmp_path, done, dry=False)
    reg.get(ep_id)["stage"] = Stage.RENDER_QC.value  # dry-stop point, no media on disk
    reg.save()
    stage = pipeline.run_long(ep_id, dry_run=False)
    names = [s for s, *_ in done]
    assert names[0] == Stage.AUDIO_READY  # fell back, skipped nothing
    assert Stage.UPLOADING in names and stage == Stage.SHORTS_READY


def test_run_long_resume_publish_when_media_present(tmp_path, monkeypatch):
    done: list = []
    reg, ep_id = _record_run(monkeypatch, tmp_path, done, dry=False)
    base = tmp_path / "state" / "episodes" / ep_id
    (base / "audio").mkdir(parents=True)
    (base / "audio" / "timing.json").write_text("{}", encoding="utf-8")
    vid = base / "render" / "long.mp4"
    vid.parent.mkdir(parents=True)
    vid.write_bytes(b"\x00")
    reg.get(ep_id)["stage"] = Stage.RENDER_QC.value
    reg.get(ep_id)["video_path"] = str(vid)
    reg.save()
    stage = pipeline.run_long(ep_id, dry_run=False)
    assert [s for s, *_ in done] == [Stage.UPLOADING, Stage.SHORTS_READY]
    assert stage == Stage.SHORTS_READY


def test_run_shorts_rerenders_when_media_missing(tmp_path, monkeypatch):
    done: list = []
    reg, ep_id = _record_run(monkeypatch, tmp_path, done, dry=True, shorts=True)
    reg.get(ep_id)["shorts"]["short_1"].pop("video_path", None)  # fresh checkout
    stage = pipeline.run_shorts(ep_id, dry_run=True)
    assert [s for s, *_ in done] == [Stage.SHORTS_SCHEDULED]
    assert reg.get(ep_id)["shorts"]["short_1"]["status"] == "ready"


# --- bounded retries across runs -------------------------------------------


def test_run_long_terminal_after_attempt_budget(tmp_path, monkeypatch):
    done: list = []
    reg, ep_id = _record_run(monkeypatch, tmp_path, done, dry=False)
    entry = reg.get(ep_id)
    entry["stage"] = Stage.FAILED.value
    entry["failed_stage"] = Stage.SCRIPT_QC.value
    entry["attempts"] = 3  # default qc.max_stage_retries
    reg.save()
    with pytest.raises(SystemExit, match="exhausted"):
        pipeline.run_long(ep_id, dry_run=False)
    assert done == []  # nothing ran


def test_run_long_retries_below_budget(tmp_path, monkeypatch):
    done: list = []
    reg, ep_id = _record_run(monkeypatch, tmp_path, done, dry=False)
    entry = reg.get(ep_id)
    entry["stage"] = Stage.FAILED.value
    entry["failed_stage"] = Stage.SCRIPT_QC.value
    entry["attempts"] = 2
    reg.save()
    stage = pipeline.run_long(ep_id, dry_run=False)
    assert [s for s, *_ in done][0] == Stage.SCRIPT_QC  # resumes at the failure
    assert stage == Stage.SHORTS_READY
