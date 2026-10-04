# CHARACTER BIBLE — Fernwood Friends

> Canonical cast. Palette hex values are binding — the renderer draws from them.
> Scale = sprite height in px at 1080p baseline (renderer scales per scene).

## Main cast (always available to every episode)

### 1. Juniper "Juni" — red squirrel
- **Role**: the spark — initiator, runner, first-to-volunteer.
- **Personality**: brave to a fault; rushes in, learns patience; generous; hates
  being called small; keeps every promise.
- **Arc seed**: wants to be "Fernwood's fastest finder" (not fastest runner).
- **Design**: russet body `#D96A2B`, cream belly/face `#FFE8C8`, dark cocoa
  eyes/nose/paws `#4A2C1A`; enormous bushy tail with cream tip; wears a
  **leaf cap** (pointed green `#5C8A3A` leaf folded like a cap).
- **Signature gag**: the leaf cap flies off whenever she sprints — someone
  always brings it back.
- **Voice**: `af_heart` (bright, quick).
- **Mannerisms**: talks with tail swishes; sits on high things; taps her chin
  twice before an idea.
- **Fear line (never cross)**: not cruel, only clumsy-fast.

### 2. Bramble — European badger
- **Role**: the builder — tools, plans, measurements.
- **Personality**: careful, methodical, mild worrier; bravest when someone
  needs building; dry humour; always carries the right tool.
- **Design**: slate-grey body `#8A8F98`, black-and-white striped face
  (two dark `#2E2E33` stripes over the eyes on white `#F4F3EE` muzzle), stocky
  frame, short clawed paws; **tool belt** of twig-tools with a measuring stick.
- **Catchphrase**: "Measure twice, dig once."
- **Voice**: `am_michael` (warm, unhurried).
- **Mannerisms**: adjusts belt before speaking; hums while working; taps foot
  when thinking.

### 3. Marlow — river otter
- **Role**: the heart-joker — humour, storytelling, water scenes.
- **Personality**: playful, loyal, big laugher; turns worry into jokes (never
  mocking); best swimmer; snack enthusiast.
- **Design**: chocolate-brown body `#7A4A2B`, cream belly/muzzle `#F7E3C3`,
  whisker dots, streamlined tail; carries a **smooth blue pebble** `#5B8FB9`.
- **Catchphrase**: "Snack first, plan second!"
- **Running gag**: loses the blue pebble in the water — found again later
  (episodes end with pebble recovered or replaced kindly).
- **Voice**: `am_fenrir` (playful, resonant).
- **Mannerisms**: floats on his back when thinking; claps once before a joke.

### 4. Wren — house wren
- **Role**: the observer-navigator — notices, maps, sings directions.
- **Personality**: tiniest but boldest; curious, precise, keeps notes in her
  head; sings short "map songs"; honest to a fault.
- **Design**: warm brown `#9C6B3F` wings/back, cream chest `#F2DEB8`, cocked
  tail (wren trait), round bright eye; wears the **amber scarf** `#E9973A`.
- **Signature prop**: the amber scarf (lost-and-found callback in EP09).
- **Voice**: `af_nicole` (clear, light).
- **Mannerisms**: head-tilt before an observation; wings folded like pockets;
  lands on shoulders of friends.

### 5. Willowby — old hare (mentor)
- **Role**: the guide — asks questions, shares stories, never gives orders.
- **Personality**: gentle wisdom, forgetful on purpose (makes friends think),
  loves tea and maps; validates feelings first, then invites investigation.
- **Design**: dust-brown `#B08D6A` with cream chest, long ears (one flopped
  tip), green waistcoat `#4E7A4A`, round silver spectacles `#C9CDD1`.
- **Voice**: `am_adam` (calm elder).
- **Mannerisms**: polishes spectacles when pondering; sips tea mid-sentence;
  says "Hmm" exactly three times before a good question.

## Recurring characters (used sparingly)
- **Fern** — shy white-tailed fawn, `#E8D3B0` coat with white spots; builds
  pebble stacks to say thank-you (arc role EP09-13). Voice reuse: `af_nicole`
  slower variant (pitch-shifted in render).
- **Pipkin** — tiny field mouse `#9E9A93` with cream belly; whisper-quick,
  counts everything; Juni's neighbour. Voice: `af_heart` pitched up.
- **Cricket Choir** — background only (no dialogue): dark green `#3E5E3A`
  silhouettes with glow dots for night scenes.

## Character sprite states (renderer contract)
Every main character is drawn in these states (parameterised poses, one PNG
each or generated on the fly):

| state | notes |
|---|---|
| idle | breathing bob, neutral |
| walk | 4-frame cycle |
| run | 4-frame cycle, lean forward |
| talk_closed / talk_mid / talk_open | mouth variants for lip-flap |
| happy | arms/tail up, smile |
| sad | drooped ears/arms, small frown |
| surprised | wide eyes, raised brows |
| scared | subtle: eyes wide, body tucked (never horror) |
| wave | one arm up greeting |
| think | one paw to chin |
| sleep | curled/eyes closed (end cards) |

Expressions combine (eyebrows × mouth) overlays on top of the state body.

## Dialogue voice mapping (config `voices`)
| character | kokoro voice | tone direction |
|---|---|---|
| narrator | `af_bella` | warm storyteller, unhurried |
| Juni | `af_heart` | quick, bright |
| Bramble | `am_michael` | steady, warm |
| Marlow | `am_fenrir` | playful bounce |
| Wren | `af_nicole` | clear, light |
| Willowby | `am_adam` | calm elder |
| Fern / Pipkin | derived (pitch ±) | softer / quicker |

## Relationships (for LLM consistency)
- Juni ↔ Bramble: rusher vs. builder — affectionate friction, mutual respect.
- Juni ↔ Wren: co-explorers; Wren tempers Juni's leaps with observation.
- Marlow ↔ everyone: comic relief with genuine loyalty.
- Willowby ↔ all: mentor to the group; shares credit always.
- Fern ↔ Juni: quiet kindness — Fern's thanks inspire Juni's best act.
- No rivalries, no bullying, no exclusion (any tension resolves kindly).

## Casting rules for new episodes
1. Minimum 2 main characters on screen per scene (never a lone monologue > 30s
   without narrator).
2. Willowby appears only when the story needs a question — not to solve it.
3. Season-arc crumbs are carried by Juni/Wren observing; Fern only where arc.
4. New species/characters require a manifest update + bible entry first.
