# LOCATION BIBLE — Fernwood Friends

> Seven canonical locations. Each maps to renderer layers (`manifest.json`).
> Palettes are binding; lighting variants are overlays (not separate art).

## 1. `hollow_oak_village` — Hollow Oak Village (hub)
- **What**: giant ancient oak with round doors in roots; mushroom-cap lamps;
  string of leaf-lanterns; village green with a signpost; stump tables.
- **Layers**: `sky`, `hills_far`, `oak_silhouette`, `village_ground`,
  `homes_mid`, `lamps_fg`, `grass_fg`.
- **Palette**: bark browns `#6B4A2E` `#8A6440`, door green `#4E7A4A`,
  grass `#6FA14C`, lamp glow `#FFD98A`, sky `#BFE3F2` (day).
- **Use**: establishing shots, greetings, errands, endings (friends wave here).
- **Variants**: day / dusk / night (glow overlay `#0B1026` α0.45).

## 2. `great_hollow` — The Great Hollow (clubhouse interior)
- **What**: inside the great oak; round map table, hanging lantern, rope-swing
  door, map pins, shelf of acorn cups, window round to outside.
- **Layers**: `wall_rings`, `window_glow`, `table_mid`, `props_fg`, `floor`.
- **Palette**: warm interior `#7A5433`, lantern `#FFC46B`, table `#A9743F`,
  map paper `#F2E3C2`.
- **Use**: planning scenes, rain days, map/story beats.

## 3. `whispering_stream` — Whispering Stream
- **What**: shallow stream over pebbles; three stepping stones (the third one
  hides the compass stone); reeds; overhanging willow branch; ripple layer.
- **Layers**: `sky`, `bank_far`, `water_mid` (animated ripples), `stones`,
  `reeds_fg`, `splash_sparkles`.
- **Palette**: water `#5B8FB9` `#7FB3D5`, stones `#9BA3A8`, reeds `#6B8F4E`,
  bank `#7D6547`.
- **Use**: Marlow scenes, discoveries, cool-down play.

## 4. `glimmer_meadow` — Glimmer Meadow (wonder site)
- **What**: tall grass waves, big flowers (5-petal shapes), flat-topped
  stones; at dusk the Glimmer lights drift upward.
- **Layers**: `sky`, `hill_far`, `grass_far`, `flowers_mid`,
  `glimmer_lights` (particle layer), `grass_fg`.
- **Palette**: meadow `#87B85A`, flowers `#F0A5C0` `#F6D66B` `#FFFFFF`,
  dusk sky `#F5B78C`→`#7A6FB0`.
- **Use**: wonder beats, map pattern EP03, pebble stacks EP09-10.

## 5. `willowbys_burrow` — Willowby's Burrow (interior)
- **What**: cozy den under the green; walls of books; round window with root
  lattice; armchair; tea table; hanging root lamp; stair-spiral.
- **Layers**: `walls`, `books_mid`, `window_root`, `chair_table`, `lamp_glow`,
  `clutter_fg`.
- **Palette**: earth `#8A6A48`, book spines mixed `#B45F4C` `#4E7A4A`
  `#C99A3B` `#4A6E8A`, lamp `#FFD98A`.
- **Use**: mentor scenes, book/lore crumb scenes.

## 6. `mossy_ravine` — Mossy Ravine & Old Root Bridge
- **What**: rocky cut with moss; bridge of two old roots + rope; vines;
  depth mist; a small waterfall feeding the stream.
- **Layers**: `cliff_far`, `mist_mid`, `bridge`, `vines`, `water_low`,
  `rocks_fg`.
- **Palette**: moss `#4F7A45`, rock `#77736C`, rope `#A98A5B`, mist `#DCE7EA`.
- **Use**: adventure beats, bridge rebuild EP11 — tension stays mild.

## 7. `glimmer_cave` — Glimmer Cave (season mystery)
- **What**: hillside root-lattice door; interior of glowing stone heart;
  concentric stone rings; light veins in walls; echo ripples when humming.
- **Layers**: `entrance_roots`, `cave_dark`, `stone_rings`,
  `light_veins` (pulsing), `heart_stone`, `sparks_fg`.
- **Palette**: cave `#2E3448`, veins `#7FE3D0`, heart `#FFF0B8`,
  rings `#565E7A`.
- **Use**: arc EP05, EP07, EP12-13. Always entered by the group.

## Global lighting overlay system
Instead of per-location day/night art, the renderer applies a tint + gradient
pass after composition:
| mood | tint | gradient |
|---|---|---|
| day | none | — |
| morning | `#FFF3D6` α0.18 | — |
| dusk | `#F5A96B` α0.25 | `#7A6FB0` top α0.3 |
| night | `#22304F` α0.45 | `#0B1026` top α0.4 |
| rain | `#7E8FA6` α0.22 | streak layer |
| glimmer | `#7FE3D0` α0.12 | sparkles on |

## Composition grammar (how scenes assemble)
1. Two characters minimum in frame (bible rule), positioned via
   `left/center/right/enter_from_exit_to` markers.
2. Eye-line: speakers face the camera-left/right partner.
3. Camera moves: `static`, `pan_l`, `pan_r`, `push_in`, `pull_out`, `drift`
   — slow (≤ 4% frame width per second).
4. Establishing shot before first interior change.
5. Transitions: `cut` (default), `fade` (scene change), `dissolve` (time
   passing), `wipe_leaves` (playful). No flashy effects.
