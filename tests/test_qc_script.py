"""Script QC (Stage SCRIPT_QC) tests: PASS path, report artifacts, FAIL rules."""

from __future__ import annotations

import json

import pytest

from app.qc.script_qc import ScriptQCError, check_script
from app.state import load_registry
from qc_fixtures import make_valid_package, qc_cfg


def _setup(tmp_path, pkg=None):
    state = tmp_path / "state"
    reg = load_registry(state)
    ep_id = reg.episode_id_for_slot("slot")
    ep_dir = state / "episodes" / ep_id
    ep_dir.mkdir(parents=True, exist_ok=True)
    pkg = pkg or make_valid_package()
    pkg["episode_id"] = ep_id
    (ep_dir / "package.json").write_text(json.dumps(pkg), encoding="utf-8")
    cfg = qc_cfg(state)
    return cfg, reg, ep_id, ep_dir, pkg


def _rewrite(ep_dir, ep_id, pkg):
    (ep_dir / "episodes" / ep_id / "package.json").write_text(json.dumps(pkg), encoding="utf-8")


def test_valid_package_passes_and_writes_report(tmp_path):
    cfg, reg, ep_id, ep_dir, _ = _setup(tmp_path)
    check_script(cfg, reg, ep_id, {})

    report = json.loads((ep_dir / "qc" / "script_qc.json").read_text(encoding="utf-8"))
    assert report["status"] == "PASS"
    assert report["errors"] == []
    assert report["estimate_sec"] > 0
    entry = reg.get(ep_id)
    assert entry["script_qc"]["status"] == "PASS"


def test_missing_package_fails(tmp_path):
    cfg, reg, ep_id, ep_dir, _ = _setup(tmp_path)
    (ep_dir / "package.json").unlink()
    with pytest.raises(ScriptQCError, match="missing"):
        check_script(cfg, reg, ep_id, {})


def test_banned_word_fails(tmp_path):
    cfg, reg, ep_id, ep_dir, pkg = _setup(tmp_path)
    pkg["scenes"][0]["dialogue"][0]["text"] = "that was so scary for us"
    _rewrite(tmp_path / "state", ep_id, pkg)
    with pytest.raises(ScriptQCError, match="banned"):
        check_script(cfg, reg, ep_id, {})


def test_non_english_text_fails(tmp_path):
    cfg, reg, ep_id, ep_dir, pkg = _setup(tmp_path)
    pkg["scenes"][1]["narration"][0]["text"] = (
        pkg["scenes"][1]["narration"][0]["text"].replace("narration", "narration سلام")
    )
    _rewrite(tmp_path / "state", ep_id, pkg)
    with pytest.raises(ScriptQCError, match="non-English"):
        check_script(cfg, reg, ep_id, {})


def test_curly_quotes_allowed(tmp_path):
    cfg, reg, ep_id, ep_dir, pkg = _setup(tmp_path)
    pkg["scenes"][0]["dialogue"][0]["text"] = "I\u2019ll wait right here, it\u2019s fine!"
    _rewrite(tmp_path / "state", ep_id, pkg)
    check_script(cfg, reg, ep_id, {})  # English typography must not fail


def test_repeated_line_fails(tmp_path):
    cfg, reg, ep_id, ep_dir, pkg = _setup(tmp_path)
    line = {"speaker": "juni", "text": "we should all go to the meadow again today", "emotion": "happy"}
    for scene in pkg["scenes"][:3]:
        scene["dialogue"].append(dict(line))
    _rewrite(tmp_path / "state", ep_id, pkg)
    with pytest.raises(ScriptQCError, match="repeated 3x"):
        check_script(cfg, reg, ep_id, {})


def test_wrong_line_count_fails(tmp_path):
    cfg, reg, ep_id, ep_dir, pkg = _setup(tmp_path)
    pkg["scenes"][0]["dialogue"].extend(
        dict(pkg["scenes"][0]["dialogue"][0], text="extra seventh line of words here")
        for _ in range(2)
    )
    _rewrite(tmp_path / "state", ep_id, pkg)
    with pytest.raises(ScriptQCError, match="dialogue lines outside"):
        check_script(cfg, reg, ep_id, {})


def test_short_narration_fails(tmp_path):
    cfg, reg, ep_id, ep_dir, pkg = _setup(tmp_path)
    pkg["scenes"][2]["narration"] = [{"text": "Too short."}]
    _rewrite(tmp_path / "state", ep_id, pkg)
    with pytest.raises(ScriptQCError, match="narration 2 words"):
        check_script(cfg, reg, ep_id, {})


def test_single_speaker_fails(tmp_path):
    cfg, reg, ep_id, ep_dir, pkg = _setup(tmp_path)
    for scene in pkg["scenes"]:
        for d in scene["dialogue"]:
            d["speaker"] = "juni"
    _rewrite(tmp_path / "state", ep_id, pkg)
    with pytest.raises(ScriptQCError, match="distinct speaker"):
        check_script(cfg, reg, ep_id, {})


def test_title_reuse_fails(tmp_path):
    cfg, reg, ep_id, ep_dir, pkg = _setup(tmp_path)
    other = reg.episode_id_for_slot("other-slot")
    reg.get(other)["title"] = pkg["title"]
    reg.save()
    with pytest.raises(ScriptQCError, match="duplicates"):
        check_script(cfg, reg, ep_id, {})


def test_hook_absent_warns_but_passes(tmp_path):
    cfg, reg, ep_id, ep_dir, pkg = _setup(tmp_path)
    pkg["hook"] = "zorbleflap appears at the fernwood gate tonight"
    _rewrite(tmp_path / "state", ep_id, pkg)
    check_script(cfg, reg, ep_id, {})
    report = json.loads((ep_dir / "qc" / "script_qc.json").read_text(encoding="utf-8"))
    assert report["status"] == "PASS"
    assert any("hook" in w for w in report["warnings"])
    assert reg.get(ep_id)["script_qc"]["warnings"] >= 1
