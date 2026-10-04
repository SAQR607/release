"""Audio stage public API."""

from __future__ import annotations

import json
from pathlib import Path

from .mix import build_long_audio, build_short_audio

__all__ = ["build_long_audio", "build_short_audio", "build_audio"]


def build_audio(cfg: dict, episode_id: str, package: dict, state_root: str | Path,
                limit_scenes: int | None = None) -> dict:
    """Long audio + both shorts audio in one timing.json contract."""
    timing = build_long_audio(cfg, episode_id, package, state_root, limit_scenes=limit_scenes)
    if not limit_scenes:
        shorts = package.get("shorts", [])
        st = []
        for i, sh in enumerate(shorts, start=1):
            st.append(build_short_audio(cfg, episode_id, sh, i, state_root))
        timing["shorts"] = st
        out_dir = Path(state_root) / "episodes" / episode_id / "audio"
        (out_dir / "timing.json").write_text(json.dumps(timing, indent=2), encoding="utf-8")
    return timing
