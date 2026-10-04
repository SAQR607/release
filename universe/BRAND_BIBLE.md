# BRAND BIBLE — Fernwood Friends

> Channel identity, public copy, thumbnails, and compliance rules.

## Identity
- **Name**: Fernwood Friends
- **Tagline**: Small friends. Big wonder.
- **Repo name suggestion**: `fernwood-friends` (user picks when creating repo)
- **Logo concept**: rounded wordmark "Fernwood" over "Friends" with a small
  oak-leaf dotting the "i"; colours from brand palette; readable at 32px.
- **Banner concept**: village oak silhouette at golden hour, five friend
  silhouettes on the hill (left third), clear space right for logo.
- **Intro style** (longs): 1.5s leaf-flutter wipe + logo, no loud stinger.

## Brand palette
| role | hex |
|---|---|
| leaf green (primary) | `#5C8A3A` |
| warm amber (accent) | `#E9973A` |
| sky blue | `#7FB3D5` |
| bark brown | `#6B4A2E` |
| cream (paper) | `#FFF3DD` |
| night indigo | `#2E3448` |
| text ink | `#3A2A1E` |

## Voice (all public copy)
- Warm, curious, gently funny; speaks TO children (short lines), never babyish.
- Never: exclamation stacks, "OMG", engagement bait ("comment if...", "don't
  forget to subscribe!!"), countdown fake-outs, scary words.
- Allowed in description: what happens, who's in it, what kids will feel/learn.

## Title formulas
- Long: `<Curiosity phrase> | Fernwood Friends S1E04` (≤ 70 chars)
  - e.g. "Who Left the Pebble Stack? | Fernwood Friends S1E09"
- Short: `<Punchy moment>` (≤ 40 chars) — e.g. "Marlow's Snack First Rule"
- Never reuse a published title verbatim.

## Description template (long, ≤ 500 chars)
```
<One kid-facing sentence about the story's moment.>

Fernwood Friends — gentle animated woodland adventures for ages 4-8.
<One sentence on the learning spine, framed as feeling.>

New long stories Monday, Wednesday & Friday. Shorts Tuesday, Thursday & Saturday.
```
No links. No hashtags in description body (tags field only).

## Tag baseline (longs)
`kids stories`, `animated stories for kids`, `wholesome kids video`,
`friends adventures`, `ages 4-8` + `woodland animals`, `preschool stories`,
`kids animation` + up to 7 episode-specific tags.
Shorts add: `kids shorts`, `cartoon shorts for kids`.

## Thumbnail rules
1. Background: one location plate at chosen mood (never plain colour).
2. 1–2 character heads at max emotion (happy/surprised/curious), large —
   faces ≥ 30% of thumbnail height.
3. Text ≤ 5 words, brand ink colour with cream outline, bottom or top third.
4. Contrast test: silhouette readable at 10% zoom; not more than 3 hues.
5. Never: crossed arms, tears, scary faces, arrows, fake screenshots.

## Playlists (created in channel setup)
- `S1 — The Glimmer Question`
- `Shorts — Fernwood`
- `Season 1 Best Moments` (filled later manually)

## Made-for-Kids compliance (binding)
- All videos uploaded with `madeForKids: true` via API (kids category 24,
  audience setting also set in Studio during setup).
- No external links anywhere (description, cards, end screens).
- No engagement bait, no comments solicitation, no livestreams.
- No personal data collection; titles/thumbnails child-appropriate.
- Comments left as YouTube default for kids content (disabled by platform).

## Season/episode numbering
- `S1E01…S1E13` for season 1 arc episodes; shorts labeled `S1E04 Short 1/2`
  in their titles' series suffix only when it fits the 40-char limit.
- Upload order follows the schedule; episodes are pre-generated but published
  only on their slot (never binge-dump).

## Social/monitoring copy (Telegram)
- Publish message: `PUBLISHED <S1E04> "<title>"\n<long|short> <id> — <hh:mm UTC>`
- Failure message: `RED ALERT production` + episode/stage/error/attempts.
- No markdown injection; text only.
