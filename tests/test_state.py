"""State machine and registry tests (§31, §32, §42)."""

import pytest

from app.state import Registry, Stage, StateError, load_registry


@pytest.fixture
def reg(tmp_path):
    return load_registry(tmp_path)


def test_slot_allocates_deterministic_id(reg):
    id1 = reg.episode_id_for_slot("long:2026-10-05T16:00Z")
    id2 = reg.episode_id_for_slot("long:2026-10-05T16:00Z")
    assert id1 == id2
    assert id1.startswith("s01e")
    # second slot gets the next number
    id3 = reg.episode_id_for_slot("long:2026-10-07T16:00Z")
    assert id3 != id1


def test_happy_path_transitions(reg):
    ep = reg.episode_id_for_slot("long:2026-10-05T16:00Z")
    order = [
        Stage.SCRIPTED, Stage.SCRIPT_QC, Stage.AUDIO_READY, Stage.RENDERING,
        Stage.RENDERED, Stage.RENDER_QC, Stage.UPLOADING, Stage.PUBLISHED,
        Stage.SHORTS_READY, Stage.SHORTS_SCHEDULED, Stage.COMPLETE,
    ]
    for stage in order:
        reg.transition(ep, stage)
    assert reg.stage_of(ep) == Stage.COMPLETE


def test_illegal_transition_rejected(reg):
    ep = reg.episode_id_for_slot("long:2026-10-05T16:00Z")
    with pytest.raises(StateError):
        reg.transition(ep, Stage.PUBLISHED)  # skips SCRIPTED..
    with pytest.raises(StateError):
        reg.transition(ep, Stage.FAILED)  # must use mark_failed


def test_terminal_states_locked(reg):
    ep = reg.episode_id_for_slot("long:2026-10-05T16:00Z")
    reg.transition(ep, Stage.SCRIPTED)
    reg.mark_failed(ep, "boom", failed_stage="SCRIPTED")
    assert reg.stage_of(ep) == Stage.FAILED
    with pytest.raises(StateError):
        reg.transition(ep, Stage.SCRIPT_QC)


def test_failure_increments_attempts_and_resumes(reg):
    ep = reg.episode_id_for_slot("long:2026-10-05T16:00Z")
    reg.transition(ep, Stage.SCRIPTED)
    reg.transition(ep, Stage.SCRIPT_QC)
    reg.mark_failed(ep, "llm down", failed_stage="SCRIPT_QC")
    assert reg.get(ep)["attempts"] == 1
    assert reg.can_retry(ep, 3) is True
    assert not reg.can_retry(ep, 1)
    assert reg.resume_stage(ep) == Stage.SCRIPT_QC


def test_persistence_reload(tmp_path):
    path = tmp_path / "registry.json"
    r1 = Registry(path)
    ep = r1.episode_id_for_slot("long:2026-10-05T16:00Z")
    r1.transition(ep, Stage.SCRIPTED, title="A Title")
    r2 = Registry(path)
    assert r2.stage_of(ep) == Stage.SCRIPTED
    assert r2.get(ep)["title"] == "A Title"
