"""Config loading/validation tests (§39, §42)."""

import json
from pathlib import Path

import pytest

from app.config import Config, ConfigError, load_config, validate_config


def _example() -> dict:
    return json.loads(Path("config/config.example.json").read_text(encoding="utf-8"))


def test_example_config_valid():
    cfg = Config(data=_example(), path=Path("config/config.example.json"))
    assert validate_config(cfg) == []


def test_bad_schedule_rejected():
    data = _example()
    data["schedule"]["long"][0]["day"] = "moonsday"
    problems = validate_config(Config(data=data, path=Path("x")))
    assert any("invalid day" in p for p in problems)


def test_bad_time_rejected():
    data = _example()
    data["schedule"]["long"][0]["time_utc"] = "25:99"
    problems = validate_config(Config(data=data, path=Path("x")))
    assert any("time out of range" in p for p in problems)


def test_english_only_enforced():
    data = _example()
    data["channel"]["language"] = "ar"
    problems = validate_config(Config(data=data, path=Path("x")))
    assert any("must be 'en'" in p for p in problems)


def test_shorts_per_long_locked_to_two():
    data = _example()
    data["content"]["shorts_per_long"] = 1
    problems = validate_config(Config(data=data, path=Path("x")))
    assert any("shorts_per_long" in p for p in problems)


def test_duration_bounds():
    data = _example()
    data["duration"]["long_min_sec"] = 100
    problems = validate_config(Config(data=data, path=Path("x")))
    assert any("long_min_sec" in p for p in problems)


def test_dotted_get():
    cfg = Config(data={"a": {"b": {"c": 42}}}, path=Path("x"))
    assert cfg.get("a.b.c") == 42
    assert cfg.get("a.b.z", "fallback") == "fallback"


def test_missing_config_raises(tmp_path):
    with pytest.raises(ConfigError):
        load_config(tmp_path / "nope.json")
