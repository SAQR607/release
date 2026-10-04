"""Content package structural validation tests (§14, §42)."""

import json
from pathlib import Path

from app.config import Config
from app.content.universe import Universe
from app.content.validate import estimate_long_seconds, validate_package, validate_premise


def _cfg() -> Config:
    return Config(data=json.loads(Path("config/config.example.json").read_text(encoding="utf-8")),
                  path=Path("config/config.example.json"))


def _uni() -> Universe:
    return Universe()


def _line(words: int = 20) -> str:
    return " ".join(["tiny"] * words)


def _make_valid_package() -> dict:
    scenes = []
    for i in range(1, 15):
        scenes.append({
            "scene_id": f"sc{i:02d}",
            "location": "hollow_oak_village" if i % 2 else "glimmer_meadow",
            "time_of_day": "day",
            "camera": "static" if i % 3 else "push_in",
            "transition_in": "cut" if i == 1 else "fade",
            "music_mood": "happy",
            "characters": [
                {"id": "juni", "position": "left", "enter": "onscreen", "state": "idle"},
                {"id": "wren", "position": "right", "enter": "onscreen", "state": "idle"},
            ],
            "dialogue": [
                {"speaker": "juni", "text": _line(10), "emotion": "happy", "action": "waves tail"},
                {"speaker": "wren", "text": _line(10), "emotion": "curious", "action": "tilts head"},
            ],
            "narration": [{"text": _line(60)}],
            "props": ["map_scroll"],
            "fx": [],
        })
    return {
        "schema": "fernwood.episode/1",
        "episode_id": "s01e001",
        "title": "The Smallest Light",
        "premise": "Juni helps a friend and notices something magical.",
        "learning_spine": "kindness to small things",
        "duration_target_sec": 540,
        "hook": "What is that tiny light in the grass?",
        "arc_crumb": "First Glimmer lights drift over Glimmer Meadow.",
        "scenes": scenes,
        "shorts": [
            {"short_id": "short_1", "kind": "funny", "title": "Marlow's Big Splash",
             "location": "whispering_stream", "time_of_day": "day", "camera": "static",
             "characters": ["marlow", "juni"],
             "dialogue": [
                 {"speaker": "marlow", "text": _line(40), "emotion": "happy", "action": "claps"},
                 {"speaker": "juni", "text": _line(40), "emotion": "excited", "action": "jumps"},
             ],
             "music_mood": "happy", "duration_target_sec": 34},
            {"short_id": "short_2", "kind": "wonder", "title": "A Light Says Hello",
             "location": "glimmer_meadow", "time_of_day": "dusk", "camera": "push_in",
             "characters": ["wren"],
             "dialogue": [
                 {"speaker": "wren", "text": _line(40), "emotion": "surprised", "action": "spreads wings"},
                 {"speaker": "wren", "text": _line(40), "emotion": "curious", "action": "points"},
             ],
             "music_mood": "mystery", "duration_target_sec": 34},
        ],
        "metadata": {
            "title": "The Smallest Light | Fernwood Friends S1E01",
            "description": "A tiny light appears when Juni helps a friend. Fernwood Friends makes gentle animated woodland adventures for ages 4-8. New long stories Monday, Wednesday and Friday.",
            "tags": ["kids stories", "animated stories for kids", "wholesome kids video",
                     "ages 4-8", "woodland animals", "preschool stories", "kids animation",
                     "gentle stories", "friendship"],
        },
        "callbacks_available": [],
    }


def test_valid_package_passes():
    errors = validate_package(_make_valid_package(), _uni(), _cfg())
    assert errors == []


def test_estimate_in_range():
    est = estimate_long_seconds(_make_valid_package())
    assert 480 <= est <= 600


def test_unknown_location_rejected():
    pkg = _make_valid_package()
    pkg["scenes"][0]["location"] = "hogwarts"
    assert any("unknown location" in e for e in validate_package(pkg, _uni(), _cfg()))


def test_banned_word_rejected():
    pkg = _make_valid_package()
    pkg["scenes"][0]["dialogue"][0]["text"] = "that was so scary and dangerous"
    errs = validate_package(pkg, _uni(), _cfg())
    assert any("banned word" in e for e in errs)


def test_three_shorts_rejected():
    pkg = _make_valid_package()
    pkg["shorts"].append(pkg["shorts"][0])
    assert any("exactly 2 shorts" in e for e in validate_package(pkg, _uni(), _cfg()))


def test_same_short_moods_rejected():
    pkg = _make_valid_package()
    pkg["shorts"][1]["kind"] = "funny"
    assert any("different" in e for e in validate_package(pkg, _uni(), _cfg()))


def test_arc_words_in_short_rejected():
    pkg = _make_valid_package()
    pkg["shorts"][0]["dialogue"][0]["text"] = "Let us visit the cave today my friend."
    assert any("season arc" in e for e in validate_package(pkg, _uni(), _cfg()))


def test_link_in_description_rejected():
    pkg = _make_valid_package()
    pkg["metadata"]["description"] = "Watch here https://example.com now friends!"
    assert any("links" in e for e in validate_package(pkg, _uni(), _cfg()))


def test_word_count_bounds_enforced():
    pkg = _make_valid_package()
    pkg["scenes"][0]["narration"] = []
    pkg["scenes"][0]["dialogue"] = []
    assert any("spoken words" in e for e in validate_package(pkg, _uni(), _cfg()))


def test_premise_arc_required():
    uni = _uni()
    base = {"title": "T", "premise": "P", "learning_spine": "patience", "hook": "H",
            "arc_crumb": None,
            "thumbnail_concept": {"background": "glimmer_meadow", "characters": ["juni"],
                                  "expression": "happy", "text": "A LIGHT"},
            "shorts_moods": ["funny", "wonder"]}
    assert validate_premise(base, uni, arc_required=True)  # null crumb -> error
    base["arc_crumb"] = "Some crumb"
    assert validate_premise(base, uni, arc_required=True) == []
    assert validate_premise(base, uni, arc_required=False)  # non-null crumb on non-arc -> error
    base["arc_crumb"] = None
    assert validate_premise(base, uni, arc_required=False) == []
