"""Pipeline stage wrappers for audio."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..config import Config
from ..logging_setup import get_logger
from ..state import Registry
from .mix import build_long_audio

log = get_logger("audio")


def build_audio(cfg: Config, reg: Registry, episode_id: str, ctx: dict[str, Any]) -> None:
    """Stage AUDIO_READY: synthesize long-form audio + timing.json contract."""
    pkg_file = Path(cfg.get("paths.state", "state")) / "episodes" / episode_id / "package.json"
    if not pkg_file.exists():
        raise FileNotFoundError(f"package.json missing for {episode_id}")
    package = json.loads(pkg_file.read_text(encoding="utf-8"))
    limit = ctx.get("sample_sec")  # QC sample: first N seconds of scenes only
    timing = build_long_audio(
        cfg, episode_id, package, cfg.get("paths.state", "state"),
        limit_scenes=None if not limit else max(1, int(limit / 30) + 1),
    )
    entry = reg.get(episode_id)
    entry["audio_total_sec"] = timing["total"]
    reg.save()
    log.info("%s audio ready: %.1fs", episode_id, timing["total"])
