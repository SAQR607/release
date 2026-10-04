"""Configuration loading: config/config.json + .env secrets.

Precedence: real environment (GitHub Secrets) > .env file > nothing.
Config files never contain secrets (§39); secrets only via environment.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
ENV_PATH = ROOT / ".env"
EXAMPLE_PATH = CONFIG_DIR / "config.example.json"
LOCAL_PATH = CONFIG_DIR / "config.json"

VALID_DAYS = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6}


class ConfigError(Exception):
    pass


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_env() -> None:
    _load_env_file(ENV_PATH)


def env_str(name: str, default: str | None = None) -> str | None:
    val = os.environ.get(name)
    if val is None or val == "":
        return default
    return val


def env_bool(name: str, default: bool = False) -> bool:
    val = os.environ.get(name)
    if val is None or val == "":
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def groq_keys() -> list[str]:
    raw = env_str("GROQ_API_KEYS", "") or ""
    keys = [k.strip() for k in raw.split(",") if k.strip()]
    return keys


@dataclass
class Config:
    data: dict[str, Any]
    path: Path
    warnings: list[str] = field(default_factory=list)

    def get(self, dotted: str, default: Any = None) -> Any:
        node: Any = self.data
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def require(self, dotted: str) -> Any:
        value = self.get(dotted, None)
        if value is None:
            raise ConfigError(f"Missing required config key: {dotted}")
        return value

    # --- typed convenience views ---
    @property
    def voices(self) -> dict[str, str]:
        return dict(self.get("voices", {}))

    @property
    def fps(self) -> int:
        return int(self.get("render.fps", 24))

    @property
    def width(self) -> int:
        return int(self.get("render.width", 1920))

    @property
    def height(self) -> int:
        return int(self.get("render.height", 1080))

    @property
    def short_size(self) -> tuple[int, int]:
        return (int(self.get("render.short_width", 1080)), int(self.get("render.short_height", 1920)))


def validate_config(cfg: Config) -> list[str]:
    problems: list[str] = []
    for slot_list_key in ("schedule.long", "schedule.shorts"):
        slots = cfg.get(slot_list_key)
        if not isinstance(slots, list) or not slots:
            problems.append(f"{slot_list_key} must be a non-empty list")
            continue
        for slot in slots:
            day = str(slot.get("day", "")).lower()
            if day not in VALID_DAYS:
                problems.append(f"{slot_list_key}: invalid day '{day}'")
            time = str(slot.get("time_utc", ""))
            parts = time.split(":")
            if len(parts) != 2 or not all(p.isdigit() for p in parts):
                problems.append(f"{slot_list_key}: invalid time_utc '{time}'")
            elif not (0 <= int(parts[0]) <= 23 and 0 <= int(parts[1]) <= 59):
                problems.append(f"{slot_list_key}: time out of range '{time}'")
    if cfg.get("channel.language") != "en":
        problems.append("channel.language must be 'en' (English-only content system)")
    lmin = int(cfg.get("duration.long_min_sec", 0))
    lmax = int(cfg.get("duration.long_max_sec", 0))
    if not (300 <= lmin < lmax <= 900):
        problems.append("duration.long_min_sec/long_max_sec must satisfy 300 <= min < max <= 900")
    smin = int(cfg.get("duration.short_min_sec", 0))
    smax = int(cfg.get("duration.short_max_sec", 0))
    if not (15 <= smin < smax <= 60):
        problems.append("duration.short_min_sec/short_max_sec must satisfy 15 <= min < max <= 60")
    if int(cfg.get("content.shorts_per_long", 0)) != 2:
        problems.append("content.shorts_per_long must be 2 (spec: exactly 2 Shorts per episode)")
    if int(cfg.get("render.fps", 0)) not in (12, 15, 20, 24, 25, 30):
        problems.append("render.fps must be a standard frame rate")
    return problems


def load_config(path: Path | None = None, allow_example: bool = False) -> Config:
    load_env()
    cfg_path = path or LOCAL_PATH
    if not cfg_path.exists():
        if allow_example and EXAMPLE_PATH.exists():
            cfg_path = EXAMPLE_PATH
        else:
            raise ConfigError(
                f"Config not found: {cfg_path}. Run `python -m app init` to create config/config.json from the example."
            )
    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid JSON in {cfg_path}: {exc}") from exc
    cfg = Config(data=data, path=cfg_path)
    problems = validate_config(cfg)
    if problems:
        raise ConfigError("Config validation failed:\n- " + "\n- ".join(problems))
    return cfg
