"""Audio unit tests: SFX/music pure functions + mixing with mocked TTS (no real synthesis)."""

from __future__ import annotations

import json

import numpy as np
import pytest

from app.audio import music, sfx, tts
from app.audio import mix as amix

CFG = {
    "render": {"sample_rate": 44100, "fps": 24},
    "music": {"enabled": True, "bed_gain_db": -16.0, "sfx_gain_db": -10.0},
    "tts": {"speed": 1.0},
    "voices": {"narrator": "af_bella", "Juni": "af_heart", "Bramble": "am_michael"},
    "duration": {"short_min_sec": 25},
}


@pytest.fixture(autouse=True)
def fake_tts(monkeypatch):
    """Replace kokoro with a deterministic tone so tests never load the model."""

    def _synth(text, voice="af_bella", speed=1.0, cache_dir=None):
        dur = max(0.4, min(2.5, 0.06 * len(text.split())))
        n = int(dur * 24000)
        t = np.arange(n) / 24000
        y = (0.3 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
        return y, 24000

    monkeypatch.setattr(tts, "synth", _synth)
    return _synth


# --- pure generators -------------------------------------------------------


@pytest.mark.parametrize("name", sfx.SFX)
def test_sfx_render_shapes(name):
    y = sfx.render(name, sr=44100)
    assert y.ndim == 1 and y.dtype == np.float32
    assert y.shape[0] > 1000
    assert np.isfinite(y).all()
    assert np.abs(y).max() > 1e-4


def test_sfx_deterministic():
    a = sfx.render("chime", seed=3)
    b = sfx.render("chime", seed=3)
    assert np.array_equal(a, b)


@pytest.mark.parametrize("mood", music.MOODS)
def test_music_bed_moods(mood):
    bed = music.render_bed(mood, 2.0, 44100)
    assert bed.shape[0] >= int(2.0 * 44100) - 10
    assert np.isfinite(bed).all()
    assert np.abs(bed).max() > 1e-4


def test_music_unknown_mood_falls_back():
    bed = music.render_bed("no-such-mood", 1.0, 44100)
    assert bed.shape[0] > 0


def test_music_mood_aliases_map_to_closest_bed():
    # manifest moods emotional/discovery have no program of their own
    assert np.array_equal(music.render_bed("emotional", 0.5), music.render_bed("tender", 0.5))
    assert np.array_equal(music.render_bed("discovery", 0.5), music.render_bed("wonder", 0.5))


# --- speech marks ----------------------------------------------------------


def test_line_voice_lookup_case_insensitive():
    voices, narrator = amix._voices(CFG)
    assert amix._line_voice(voices, narrator, "juni") == "af_heart"
    assert amix._line_voice(voices, narrator, "JUNI") == "af_heart"
    assert amix._line_voice(voices, narrator, "unknown-speaker") == narrator
    assert amix._line_voice(voices, narrator, "") == narrator


def test_scene_speech_marks_and_gaps(tmp_path):
    scene = {
        "dialogue": [
            {"speaker": "Juni", "text": "I can wait right here.", "emotion": "calm"},
            {"speaker": "Bramble", "text": "That is a good plan.", "emotion": "happy"},
        ],
        "narration": [{"text": "Juni counts the clouds while the forest hums along."}],
    }
    voices, narrator = amix._voices(CFG)
    track, end, sr, marks = amix._scene_speech(scene, voices, narrator, tmp_path, 1.0)

    assert sr == 24000
    assert len(marks) == 3
    assert marks[0]["start"] == 0.5  # lead-in
    assert marks[0]["emotion"] == "calm"
    assert marks[1]["emotion"] == "happy"
    assert marks[2]["speaker"] == "narrator"
    assert marks[2]["emotion"] == "neutral"
    # monotonic, inside the track
    for m in marks:
        assert 0 <= m["start"] < m["end"] <= end + 1e-6
    assert marks[0]["end"] <= marks[1]["start"]
    assert marks[1]["end"] <= marks[2]["start"]
    # gaps: 0.42 after each dialogue line, 0.6 narration tail
    assert marks[1]["start"] - marks[0]["end"] == pytest.approx(0.42, abs=0.05)
    assert marks[2]["start"] - marks[1]["end"] == pytest.approx(0.42, abs=0.05)
    assert end - marks[2]["end"] == pytest.approx(1.2, abs=0.05)  # 0.6 post-narration gap + 0.6 tail
    assert track.shape[0] == int(end * 24000)
    assert np.abs(track).max() > 0


def test_scene_speech_skips_empty_text(tmp_path):
    scene = {"dialogue": [{"speaker": "Juni", "text": ""}], "narration": [{"text": "Hello there."}]}
    voices, narrator = amix._voices(CFG)
    _, _, _, marks = amix._scene_speech(scene, voices, narrator, tmp_path, 1.0)
    assert len(marks) == 1
    assert marks[0]["speaker"] == "narrator"


def test_scene_sfx_mapping():
    events = amix._scene_sfx({"fx": ["glimmer_sparkle", "leaf_swirl"]}, 44100)
    names = [e[0] for e in events]
    assert "chime" in names and "whoosh" in names
    assert amix._scene_sfx({"fx": []}, 44100) == []


# --- scene render ----------------------------------------------------------


def test_render_scene_track_shape():
    scene = {"dialogue": [{"speaker": "Juni", "text": "Wait with me.", "emotion": "calm"}],
             "fx": ["speech_pop"], "music_mood": "tender"}
    voices, narrator = amix._voices(CFG)
    track, sr, scene_len, marks = amix._render_scene(scene, 1, CFG, voices, narrator,
                                                     "cache", 1.0)
    assert sr == 44100
    assert track.shape == (int(scene_len * 44100), 2)
    assert np.isfinite(track).all()
    assert np.abs(track).max() > 1e-3  # speech + bed present
    assert len(marks) == 1


# --- full builds -----------------------------------------------------------


def _tiny_package():
    scene = {
        "scene_id": "sc01",
        "location": "Fernwood Green",
        "tod": "day",
        "music_mood": "happy",
        "fx": ["glimmer_sparkle"],
        "dialogue": [{"speaker": "Juni", "text": "One two three four five six.", "emotion": "happy"}],
        "narration": [{"text": "A quiet morning settles over the fernwood clearings."}],
        "camera_move": "static",
        "transition_in": "fade",
    }
    return {"episode_id": "t1", "title": "T", "scenes": [scene, dict(scene, scene_id="sc02")]}


def test_build_long_audio(tmp_path):
    pkg = _tiny_package()
    timing = amix.build_long_audio(CFG, "t1", pkg, tmp_path)

    out = tmp_path / "episodes" / "t1" / "audio"
    assert (out / "master.wav").exists()
    assert (out / "timing.json").exists()
    data = json.loads((out / "timing.json").read_text(encoding="utf-8"))
    assert data == timing
    assert timing["kind"] == "long"
    assert len(timing["scenes"]) == 2
    # cumulative starts, durations match total
    acc = 0.0
    for entry in timing["scenes"]:
        assert (out / entry["file"]).exists()
        assert entry["start"] == pytest.approx(acc, abs=0.01)
        assert entry["duration"] > 0
        assert entry["end"] == pytest.approx(entry["start"] + entry["duration"], abs=0.01)
        assert len(entry["lines"]) >= 1
        for m in entry["lines"]:
            # line marks are scene-relative (renderer uses local t)
            assert 0 <= m["start"] < m["end"] <= entry["duration"] + 0.01
        acc = entry["end"]
    assert timing["total"] == pytest.approx(acc, abs=0.01)


def test_build_long_audio_limit_scenes(tmp_path):
    timing = amix.build_long_audio(CFG, "t1", _tiny_package(), tmp_path, limit_scenes=1)
    assert len(timing["scenes"]) == 1


def test_build_short_audio_min_duration(tmp_path):
    short = {"short_id": "t1s1", "kind": "wonder",
             "dialogue": [{"speaker": "Juni", "text": "Wow!", "emotion": "excited"}],
             "narration": [{"text": "A tiny surprise."}]}
    entry = amix.build_short_audio(CFG, "t1", short, 1, tmp_path)

    out = tmp_path / "episodes" / "t1" / "audio"
    path = out / entry["file"]
    assert path.exists()
    # short must reach 25s target even with tiny speech
    assert entry["duration"] >= CFG["duration"]["short_min_sec"] + 0.5
    assert entry["duration"] <= 45.0 + 1.0
    assert entry["lines"], "shorts need line marks for lip sync"
    import soundfile as sf
    info = sf.info(str(path))
    assert info.samplerate == 44100
    assert abs(info.duration - entry["duration"]) < 0.05


def test_short_mood_by_kind(tmp_path):
    short = {"short_id": "x", "kind": "funny",
             "dialogue": [{"speaker": "Juni", "text": "Ha ha ha!", "emotion": "happy"}]}
    entry = amix.build_short_audio(CFG, "t2", short, 1, tmp_path)
    assert entry["kind"] == "funny"
    assert entry["duration"] >= 25
