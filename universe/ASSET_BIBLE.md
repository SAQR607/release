# ASSET BIBLE — art direction & asset inventory

> How every pixel is made (procedural PIL drawing — no third-party art),
> and the inventory the renderer + QC validate against.

## Art direction (binding style rules)
- **Flat vector-cartoon**: solid shapes with soft rounded silhouettes; no
  gradients except light glows and water ripples.
- **Outline**: consistent dark warm outline `#3A2A1E`, width 5px @1080p
  (scaled with sprite); eyes and props share it. Interior details (belly patch)
  use NO outline (colour-block edges only).
- **Faces**: large eyes (white + dark iris + single highlight dot), simple
  brows (2 strokes), mouth as one curve line or open shape. Never uncanny:
  eyes are 22% of head width, spaced 1.5 eye-widths apart.
- **Proportions**: heads ~40% of body height (cute juvenile read), rounded
  bellies, short limbs, big feet. Willowby (elder) has 35% head ratio.
- **Depth**: foreground grass/props overlap characters; characters never
  overlap behind mid-layer unless drawn into it.
- **Light**: one soft key from upper-left; shadow = single ellipse under
  character (`#3A2A1E` α0.15), no cast-shadow shapes.
- **Colour discipline**: 5-7 hues per frame; characters must contrast with
  background (test: silhouette readable at 8% zoom).

## Naming conventions (renderer + QC)
```
assets/characters/<char>/<state>.png          e.g. assets/characters/juni/idle.png
assets/locations/<loc>/<layer>.png            e.g. assets/locations/hollow_oak_village/sky.png
assets/props/<prop>.png                       e.g. assets/props/leaf_cap.png
assets/ui/thumbnail_frame.png
```
- Files are 24-bit RGBA PNGs; transparent margins trimmed.
- Everything is generated deterministically by `python -m app assets build`
  from code in `app/render/art/` (seeded, byte-reproducible).

## Sprite sizes (px @1080p baseline)
| character | base height | notes |
|---|---|---|
| juni | 470 | + tail 30% beyond body box |
| bramble | 540 | widest silhouette |
| marlow | 500 | horizontal variant for float pose |
| wren | 250 | flies — has `hover` state |
| willowby | 610 | tallest |
| fern | 520 | recurring |
| pipkin | 160 | recurring |

Location layers render at 2200×1400 (camera headroom for pans; composed frame
crops to 1920×1080 or 1080×1920).

## Inventory (must exist — QC checks manifest)

### Characters (states per CHARACTER_BIBLE table)
juni, bramble, marlow, wren, willowby (main) + fern, pipkin (recurring).
States: `idle walk run talk_closed talk_mid talk_open happy sad surprised
scared wave think sleep`; wren adds `hover`.

### Locations & layers
Per LOCATION_BIBLE (7 locations × 4-6 layers each).

### Props (20)
`leaf_cap, tool_belt, blue_pebble, amber_scarf, magnifier_leaf, rope_coil,
acorn_cup, satchel, lantern, map_scroll, whistle_berry, snack_basket,
umbrella_leaf, compass_stone, plank_boat, shell_bucket, twig_staff, book,
pocket_watch, pinecone_ball`

### FX / overlays
`glimmer_sparkle, rain_streak, ripple_ring, dust_motes, leaf_swirl,
lamp_glow, speech_pop` (used for short-form punch-ins), `endcard_wave`.

### Fallback rules (§13 / QC)
- Missing character state → renderer substitutes `idle` **and** records
  `asset_missing` in QC → QC FAILS (asset must be built; no silent quality
  loss in production).
- Missing location layer → render aborts with clear error (backgrounds are
  never approximated).
- Missing prop → scene-level WARN + visual placeholder circle (`#B45F4C`) —
  props may be omitted by the story if missing, characters may not.

## Thumbnail kit
- `thumb_bg_<mood>`: warm gradient plates (meadow, oak, stream, cave).
- Character headshots at 4 expressions (happy, surprised, curious, excited).
- Expression overlay: big open smile / raised brow.
- Rule: background + 1-2 heads + ≤5-word title text = final thumb (composited
  in `app/render/thumbnail.py`, never uploaded raw).

## Music & SFX (procedural synthesis — no external audio)
Synthesised with numpy → wav (deterministic seed per mood + episode id):

| mood | character |
|---|---|
| adventure | steady marimba-ish pulse + rising fifths |
| mystery | soft pad + slow bell arpeggio (Glimmer motif) |
| happy | bright pluck melody, major pentatonic |
| emotional | warm sine pads, slow |
| calm | low drone + gentle chimes |
| discovery | ascending motif + sparkle noise |

SFX: `pop, whoosh, soft_thud, splash, giggle_rim, chime, page_turn, footstep,
door_creak_gentle, sparkle` — all synthesised, all short (<1.2s).
Glimmer motif (mystery sparkle 4-note figure) recurs in arc episodes — audio
callback matching visual Glimmer.
