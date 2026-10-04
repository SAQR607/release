"""Art system tests: every manifest id builds, sizes correct, deterministic."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def test_manifest_ids_match_art_catalogues():
    man = json.loads((ROOT / "universe" / "manifest.json").read_text(encoding="utf-8"))
    from app.render.art.characters import SPECIES
    from app.render.art.locations import LOCATIONS
    from app.render.art.props import PROPS

    assert {c["id"] for c in man["characters"]} == set(SPECIES)
    assert {l["id"] for l in man["locations"]} == set(LOCATIONS)
    props = man["props"]
    ids = {p["id"] for p in props} if props and isinstance(props[0], dict) else set(props)
    assert ids == set(PROPS)


def test_every_character_state_and_expression():
    from app.render.art.characters import FACES, POSES, SPECIES, get_sprite

    for cid in SPECIES:
        for st in POSES:
            for expr in ("neutral",):
                sp = get_sprite(cid, st, expr, 0)
                assert sp.size == (600, 760)
                assert sp.getbbox() is not None
        for expr in FACES:
            assert get_sprite(cid, "idle", expr).getbbox() is not None


def test_walk_cycle_frames_differ():
    from app.render.art.characters import get_sprite

    frames = [bytes(get_sprite("juni", "walk", "neutral", i).tobytes()) for i in range(4)]
    assert len(set(frames)) == 4


def test_every_location_paints_all_tods():
    from app.render.art.locations import LOCATIONS, paint_location

    for loc in LOCATIONS:
        for tod in ("day", "night"):
            layers = paint_location(loc, tod)
            assert set(layers) == {"sky", "far", "mid", "near"}
            for im in layers.values():
                assert isinstance(im, Image.Image)
                assert im.size == (2200, 1400)


def test_every_prop_builds():
    from app.render.art.props import PROPS, get_prop

    for pid in PROPS:
        im = get_prop(pid)
        assert im.size == (256, 256)
        assert im.getbbox() is not None


def test_prop_determinism():
    from app.render.art.props import _BUILDERS

    for pid, builder in _BUILDERS.items():
        assert builder().tobytes() == builder().tobytes(), pid


def test_fx_smoke():
    from app.render.art.fx import FX, draw_fx

    img = Image.new("RGBA", (320, 180), (0, 0, 0, 0))
    for fx in FX:
        draw_fx(img, [fx], 1.25, seed=7)


def test_assets_build(tmp_path):
    from app.render.assets import build_all

    counts = build_all(tmp_path)
    assert counts["props"] == 20
    assert counts["locations"] == 112
    assert counts["characters"] == 231
    assert (tmp_path / "build.json").exists()
