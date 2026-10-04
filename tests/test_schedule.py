"""Schedule + plan_due tests (§29, §42)."""

from datetime import datetime, timezone

import pytest

from app.config import load_config
from app.schedule import due_slots, plan_due
from app.state import Stage, load_registry


@pytest.fixture
def cfg(tmp_path):
    # example config is the canonical schema; allow_example bypasses config.json
    c = load_config(allow_example=True)
    return c


def _dt(*args):
    return datetime(*args, tzinfo=timezone.utc)


def test_long_slots_mon_wed_fri(cfg):
    # Monday 2026-10-05 at 16:07 -> Monday long slot is due
    slots = due_slots(cfg, _dt(2026, 10, 5, 16, 7))
    kinds = {s["kind"] for s in slots}
    assert kinds == {"long"}
    longs = [s for s in slots if s["kind"] == "long"]
    assert longs[0]["slot_key"] == "long:2026-10-05T16:00Z"


def test_tuesday_is_shorts_day(cfg):
    # Tuesday evening: Monday's long slot is outside the 26h catch-up window
    slots = due_slots(cfg, _dt(2026, 10, 6, 19, 7))
    kinds = {s["kind"] for s in slots}
    assert kinds == {"shorts"}


def test_nothing_due_before_time(cfg):
    slots = due_slots(cfg, _dt(2026, 10, 5, 15, 59))
    assert slots == []


def test_nothing_due_on_sunday(cfg):
    # Sunday evening: Saturday's shorts slot aged past the catch-up window
    slots = due_slots(cfg, _dt(2026, 10, 4, 19, 7))
    assert slots == []


def test_catchup_window_expires(cfg):
    # slot from >26h ago (Saturday morning checking Friday 16:00 -> 40h) ignored
    slots = due_slots(cfg, _dt(2026, 10, 4, 6, 0))
    assert all(s["kind"] != "long" for s in slots)


def test_plan_due_registers_episode_idempotently(cfg, tmp_path):
    reg = load_registry(tmp_path)
    now = _dt(2026, 10, 5, 16, 7)
    jobs1 = [j for j in plan_due(cfg, reg, now) if j["kind"] == "long"]
    jobs2 = [j for j in plan_due(cfg, reg, now) if j["kind"] == "long"]
    assert len(jobs1) == 1
    assert jobs1[0]["episode_id"] == jobs2[0]["episode_id"]
    assert jobs1[0]["stage"] == Stage.PLANNED.value


def test_plan_due_skips_finished_long_day(cfg, tmp_path):
    reg = load_registry(tmp_path)
    now = _dt(2026, 10, 5, 16, 7)
    jobs = plan_due(cfg, reg, now)
    ep = next(j["episode_id"] for j in jobs if j["kind"] == "long")
    for stage in (Stage.SCRIPTED, Stage.SCRIPT_QC, Stage.AUDIO_READY, Stage.RENDERING,
                  Stage.RENDERED, Stage.RENDER_QC, Stage.UPLOADING, Stage.PUBLISHED,
                  Stage.SHORTS_READY):
        reg.transition(ep, stage)
    jobs_after = plan_due(cfg, reg, now)
    assert all(j.get("episode_id") != ep for j in jobs_after)


def test_shorts_job_pending_after_long_published(cfg, tmp_path):
    reg = load_registry(tmp_path)
    # Claim Monday long
    long_jobs = [j for j in plan_due(cfg, reg, _dt(2026, 10, 5, 16, 7)) if j["kind"] == "long"]
    ep = long_jobs[0]["episode_id"]
    for stage in (Stage.SCRIPTED, Stage.SCRIPT_QC, Stage.AUDIO_READY, Stage.RENDERING,
                  Stage.RENDERED, Stage.RENDER_QC, Stage.UPLOADING, Stage.PUBLISHED,
                  Stage.SHORTS_READY):
        reg.transition(ep, stage)
    # Short packages were built at SHORTS_READY
    reg.get(ep)["shorts"] = {"short_1": {"status": "ready"}, "short_2": {"status": "ready"}}
    reg.save()

    # Tuesday evening: shorts job appears for that episode
    shorts_jobs = [j for j in plan_due(cfg, reg, _dt(2026, 10, 6, 19, 7)) if j["kind"] == "shorts"]
    assert len(shorts_jobs) == 1
    assert shorts_jobs[0]["episode_id"] == ep
    assert sorted(shorts_jobs[0]["pending_shorts"]) == ["short_1", "short_2"]

    # Killed runner after render: stage SHORTS_SCHEDULED, statuses rendered -> still pending
    reg.transition(ep, Stage.SHORTS_SCHEDULED)
    for sh in reg.get(ep)["shorts"].values():
        sh["status"] = "rendered"
    reg.save()
    shorts_jobs_r = [j for j in plan_due(cfg, reg, _dt(2026, 10, 6, 19, 7)) if j["kind"] == "shorts"]
    assert len(shorts_jobs_r) == 1

    # After COMPLETE, no more shorts jobs even with stale statuses
    for sh in reg.get(ep)["shorts"].values():
        sh["status"] = "uploaded"
    reg.transition(ep, Stage.COMPLETE)
    shorts_jobs2 = [j for j in plan_due(cfg, reg, _dt(2026, 10, 6, 19, 7)) if j["kind"] == "shorts"]
    assert shorts_jobs2 == []
