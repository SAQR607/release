"""Shared QC fixtures: synthetic packages that satisfy validate_package.

Calibrated against the real generator output: 5 dialogue lines x 8-12 words
per scene, 40-word narrations, 14 scenes (1100+ spoken words), unique line
texts everywhere (the script QC rejects repetition).
"""

from __future__ import annotations

import json
from pathlib import Path

from app.config import Config

_FILLER = ["the", "friends", "play", "together", "kindly", "today", "gently", "along"]


def _dialogue_line(scene: int, line: int, words: int = 8) -> str:
    head = [f"s{scene:02d}", f"l{line}"]
    return " ".join(head + _FILLER[: max(0, words - len(head))])


def _narration(scene: int, words: int = 40) -> str:
    head = f"narration for scene {scene:02d}"
    rest = ["the"] * max(0, words - len(head.split()))
    return head + " " + " ".join(rest)


def make_valid_package() -> dict:
    scenes = []
    for i in range(1, 15):
        speakers = ["juni", "wren"] if i % 2 else ["wren", "juni"]
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
                {"speaker": speakers[j % 2], "text": _dialogue_line(i, j),
                 "emotion": "happy", "action": "waves tail"}
                for j in range(5)
            ],
            "narration": [{"text": _narration(i)}],
            "props": ["map_scroll"],
            "fx": [],
        })
    short_lines = lambda s, n, w=12: [
        {"speaker": "marlow" if s == 1 else "wren",
         "text": " ".join([f"q{s}{j}"] + _FILLER[: w - 1]),
         "emotion": "happy", "action": "claps"}
        for j in range(n)
    ]
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
             "characters": ["marlow", "juni"], "dialogue": short_lines(1, 5),
             "music_mood": "happy", "duration_target_sec": 34},
            {"short_id": "short_2", "kind": "wonder", "title": "A Light Says Hello",
             "location": "glimmer_meadow", "time_of_day": "dusk", "camera": "push_in",
             "characters": ["wren"], "dialogue": short_lines(2, 5),
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


def example_cfg() -> Config:
    path = Path("config/config.example.json")
    return Config(data=json.loads(path.read_text(encoding="utf-8")), path=path)


def qc_cfg(state: Path) -> Config:
    """Example config with paths redirected into tmp (test isolation)."""
    path = Path("config/config.example.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("paths", {})
    data["paths"]["state"] = str(state)
    data["paths"]["workspace"] = str(state / "workspace")
    return Config(data=data, path=path)
