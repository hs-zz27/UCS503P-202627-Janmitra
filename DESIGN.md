---
name: Janmitra
description: Government help, in your own words. A voice-first guide to India's central schemes.
colors:
  ink: "#000000"
  disc: "#0d0d10"
  chip-ground: "#0b0b0e"
  ring-1: "#8b2cf5"
  ring-2: "#2f6bff"
  ring-3: "#16c46a"
  ring-4: "#f2b705"
  ring-5: "#f0255c"
  text: "#ffffff"
  text-soft: "#d9d1ee"
typography:
  display:
    fontFamily: "Anek Latin, ui-sans-serif, system-ui, sans-serif"
    fontSize: "clamp(2.6rem, 10vmin, 6rem)"
    fontWeight: 800
    lineHeight: 0.9
    letterSpacing: "-0.035em"
  headline:
    fontFamily: "Anek Latin, ui-sans-serif, system-ui, sans-serif"
    fontSize: "clamp(1.9rem, 5vw, 4.25rem)"
    fontWeight: 700
    lineHeight: 1.06
    letterSpacing: "-0.025em"
  title:
    fontFamily: "Anek Latin, ui-sans-serif, system-ui, sans-serif"
    fontSize: "clamp(1.25rem, 2.6vw, 1.9rem)"
    fontWeight: 650
    lineHeight: 1.15
    letterSpacing: "-0.02em"
  body:
    fontFamily: "Anek Latin, ui-sans-serif, system-ui, sans-serif"
    fontSize: "clamp(0.85rem, 1.9vmin, 1.2rem)"
    fontWeight: 500
    lineHeight: 1.3
  label:
    fontFamily: "Anek Latin, ui-sans-serif, system-ui, sans-serif"
    fontSize: "clamp(0.68rem, 1.35vmin, 0.92rem)"
    fontWeight: 600
    lineHeight: 1
    letterSpacing: "0.01em"
rounded:
  pill: "999px"
  circle: "50%"
spacing:
  ring-r0: "21vmin"
  ring-band: "6.4vmin"
  ring-gap: "4.2vmin"
  edge-inset: "12px"
components:
  button-primary:
    backgroundColor: "{colors.text}"
    textColor: "{colors.ink}"
    rounded: "{rounded.pill}"
    padding: "0.85em 1.45em"
  ring-chip:
    backgroundColor: "{colors.chip-ground}"
    textColor: "{colors.text}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: "0.45em 0.85em"
  scroll-cue:
    backgroundColor: "{colors.chip-ground}"
    textColor: "{colors.text-soft}"
    rounded: "{rounded.pill}"
    padding: "0.4em 0.75em 0.4em 0.9em"
  centre-disc:
    backgroundColor: "{colors.disc}"
    rounded: "{rounded.circle}"
    size: "42vmin"
---

# Design System: Janmitra

## Overview

**Creative North Star: "The Catalogue Made Visible"**

Janmitra's world is a black ground holding five concentric rings of saturated colour, one ring per scheme category, each carrying the real schemes it contains. The rings are the content, not decoration: the published catalogue drawn as a target the visitor can see whole in one viewport and then enter. A dark centre disc holds the wordmark; everything else is white type set heavy in Anek Latin, an Indian multi-script superfamily, so Latin, Devanagari and Gurmukhi share one voice.

Depth comes from flight, not from stacked surfaces. A scroll-scrubbed stage flies the viewer into the rings, outer rings opening faster as in a tunnel, until the dark centre fills the screen and three short statements rise inside it one at a time. The page then releases into an embedded phone that actually places the call. Density is low and type is large, honouring readers with low literacy and low-end phones.

The landing world and the call screen are two systems on one page. The call screen is an embedded device surface: a deliberate iOS in-call imitation with its own native tokens, which the landing world frames but never restyles.

**Key Characteristics:**
- Black ground, five saturated ring hues, white heavy type.
- Each ring is a scheme category; its schemes ride it as dark pills.
- One signature motion: scroll-scrubbed flight into the rings; nothing moves on its own.
- Pills everywhere a shape is needed; circles for the rings and disc; no rectangles with corners.
- Without JavaScript or with reduced motion, the same content reads as plain stacked sections.

## Colors

A black field carrying five full-saturation ring hues, with white type and one violet-tinted secondary.

### Primary
- **Ring Violet** (ring-1): the innermost ring, Pensions. It is the ring that stays: capped just short of the frame corners during the flight, it frames the three statements.
- **Signal Blue** (ring-2): second ring, Insurance.
- **Field Green** (ring-3): third ring, Loans. Also marks the third statement's key phrase ("in your own words").
- **Saffron** (ring-4): fourth ring, Grants. Also the browser-surface accent: text selection, the focus ring, and the first statement's key phrase.
- **Rose** (ring-5): outermost ring, Banking and rural employment. Marks the second statement's key phrase.

### Neutral
- **Ink** (ink): the page ground, the stage, and the call section. Pure black so the ring glow reads.
- **Centre Disc** (disc): the dark disc at the ring centre that holds the wordmark; a hair lighter than ink, with a 1px inset white edge at 6% alpha.
- **Chip Ground** (chip-ground): the fill of every scheme pill and the scroll cue.
- **White** (text): all primary type, and the fill of the primary action.
- **Lavender Mist** (text-soft): tagline, language line, scroll cue, footer. A white tinted toward the violet ring, never a grey.

### Named Rules
**The Ring Order Rule.** The five hues always appear in the same order, inner to outer: violet, blue, green, saffron, rose. A hue names its category; do not reassign it.

**The Borrowed Accent Rule.** Accents in type are borrowed from the rings, never introduced. A statement's key phrase takes one ring hue; selection and focus take saffron.

## Typography

**Display Font:** Anek Latin (variable, 100-800, self-hosted), with ui-sans-serif, system-ui fallback
**Script Faces:** Anek Devanagari and Anek Gurmukhi, applied by `:lang(hi)` and `:lang(pa)`, falling back to Anek Latin

**Character:** One family carries every role, from an 800-weight wordmark to 400-weight footer copy. Weights 500 to 800 do the work; tight negative tracking on the large sizes.

### Hierarchy
- **Display** (800, clamp(2.6rem, 10vmin, 6rem), 0.9): the wordmark in the centre disc only.
- **Headline** (700, clamp(1.9rem, 5vw, 4.25rem), 1.06): the three scroll statements, centred, max 22ch, balanced.
- **Title** (650, clamp(1.25rem, 2.6vw, 1.9rem), 1.15): the line introducing the phone.
- **Body** (500, clamp(0.85rem, 1.9vmin, 1.2rem), 1.3): the tagline, max 24ch. The language line runs 500 at clamp(1rem, 1.8vw, 1.3rem), 1.4; footer copy 400 at 0.92rem, 1.55, max 65ch.
- **Label** (600, clamp(0.68rem, 1.35vmin, 0.92rem), 1): scheme names on the rings. The primary action runs 650 at clamp(1rem, 1.6vw, 1.125rem).

### Named Rules
**The Own Script Rule.** Text in Hindi or Punjabi carries its `lang` attribute and renders in Anek's own Devanagari or Gurmukhi cut, so every language shares one family. Language names inside a sentence step up to white at 650.

## Layout

The landing is one full-viewport stage. The ring centre sits high, at 45% of the viewport height (`--cy`), horizontally centred; the wordmark and tagline sit on that centre, and the primary action plus scroll cue sit at bottom centre, clamp(1.25rem, 5vh, 3rem) from the edge.

Ring geometry is measured in vmin so the target scales with the shorter side: centre-disc radius 21 (`--r0`), band width 6.4 (`--band`), gap 4.2 (`--gap`). Ring k (0 inner to 4 outer) has inner radius r0 + gap + k(band + gap). At desktop the outer rings crop at the viewport edges; that crop is intended. The stage's logic reads the same four values from `GEOMETRY` in `code/frontend/lib/landing-story.ts`; `code/frontend/tests/landing-story.test.ts` fails if they drift from `landing.css`, so change both together.

Scheme pills sit upright on the middle of their band at fixed angles (0deg is top, clockwise), with one angle set for landscape and another for portrait, recorded per scheme in `RINGS` in `code/frontend/lib/landing-story.ts`. The angles are solved against measured pill sizes, not spaced evenly: every pill keeps at least 12px from every other pill, from the wordmark-plus-tagline block, and from the hero action, inside the viewport, checked on phones from 360x740 to 430x932 and screens from 1024x768 to 1440x900. Portrait angles are deliberately asymmetric so pills on neighbouring rings never stack into a vertical ladder. After layout and font load, a script (`placeChips` in `Landing.tsx`, applying `chipCentre` and `chipHidden` from the lib) hides any pill that would cross an 8px viewport inset, overlap the hero action's box plus 12px, or overlap the wordmark block plus 12px. Pills are never moved to fit; they are kept or hidden.

The ring stack paints in three layers: all five bands, then the centre disc, then all five name layers. Each name layer carries `.ring-names` plus its ring's `.ring-zoom-k` class, so it shares that ring's scale through the flight, yet always paints above every band. Rings 2 to 5 share opacity with their names; ring 1's name layer (`.ring-names.ring-zoom-1`) takes its own opacity, `--names1-o`, so its names can leave while the violet band stays as the rim.

### Named Rules
**The Names-Above-Bands Rule.** Scheme names never share a stacking layer with ring bands. Bands render first, then the disc, then every ring's names, so a name that spills past its own band is never covered by an outer band. A new ring or name goes into the matching layer, never inside its band's element.

**The Solved Angle Rule.** A new scheme name gets an angle solved against its measured size and the 12px clearances above, in both orientations. Never space names evenly by count, and never rely on the hide script as the placement method; it is a safety net.

With JavaScript and full motion, the story is a 500vh track holding a sticky 100dvh stage. Without JavaScript, or under `prefers-reduced-motion: reduce`, the rings and hero render as one viewport and the three statements follow as ordinary stacked sections with clamp(5rem, 24dvh, 13rem) vertical padding.

The phone section is a centred column at min-height 100dvh, a 12px side gutter, the intro line above the device.

## Elevation & Depth

The landing world is flat in surfaces and deep in space. Depth comes from the ring glow and from the scroll flight, not from layered cards.

### Shadow Vocabulary
- **Ring glow** (`box-shadow: 0 0 calc(band * 0.55vmin) <ring hue at 38%>, inset 0 0 calc(band * 0.45vmin) <ring hue at 30%>`): every ring band, tinted by its own hue.
- **Disc edge** (`box-shadow: inset 0 0 0 1px rgba(255,255,255,0.06)`): the centre disc only.
- **Action lift** (`box-shadow: 0 10px 28px rgba(0,0,0,0.5), 0 2px 6px rgba(0,0,0,0.4)`; hover `0 16px 36px rgba(0,0,0,0.55), 0 3px 8px rgba(0,0,0,0.4)`): the white primary action, so it floats above the rings it overlaps.

### Named Rules
**The Self-Lit Ring Rule.** A ring glows only in its own colour. No neutral glows, no glow on type.

## Shapes

Two shapes: the circle and the pill. Rings and the centre disc are true circles (50%); every interactive or labelling element (primary action, scheme pills, scroll cue) is a full pill (999px). Pill borders are 1px: the ring hue at 70% for scheme pills, white at 14% for the scroll cue. Nothing on the landing has a squared or slightly-rounded corner.

## Components

### Buttons
The single primary action, "Talk to Janmitra", is the only white solid on the page.
- **Shape:** full pill (999px).
- **Primary:** white fill, black text, 650 weight, phone icon (Lucide, 1.1em) leading, padding 0.85em 1.45em.
- **Hover / Focus:** lifts 2px with the deeper shadow over 220ms, cubic-bezier(0.16, 1, 0.3, 1); focus shows a 3px saffron outline at 4px offset. Reduced motion drops the transition.
- **Behaviour:** an in-page link to the phone section (`#call`).

### Chips
- **Scheme pill:** chip-ground fill, white 600 label, 1px border of its ring hue at 70%, no wrapping. Lives in its ring's name layer above all bands (see Layout). Decorative (`aria-hidden`); the same catalogue is listed for screen readers in a visually hidden list. Each scheme in `RINGS` carries its catalogue slug and each ring its catalogue categories; the test enforces that every published scheme appears exactly once, on the ring for its category.
- **Scroll cue:** chip-ground fill, lavender text at 0.82rem, chevron trailing, hidden from assistive tech.

### Browser surface
- `color-scheme: dark`; scrollbar thumb #34343a on ink; selection is saffron with black text; focus ring 3px saffron, 4px offset.

### Ring Stage (signature)
The scroll-scrubbed flight. Progress p (0 to 1 across the 500vh track) drives custom properties each animation frame. `storyFrame` in `code/frontend/lib/landing-story.ts` computes every value below (timeline windows in `FLIGHT` and `BEATS`, the cap in `ring1Cap`); `Landing.tsx` only writes them to the DOM:
- **Flight** (p 0.02 to 0.32): each ring scales by exp(fly x (1.85 + 0.28i)), so outer rings open faster; the centre disc scales by exp(fly x 1.75) and fades out between p 0.08 and 0.20. Exponential scale reads as constant speed.
- **The capped ring:** the violet ring scales by exp(fly x 2.13) but stops at 0.9 of the distance to the far frame corner, dims to 70% (`--ring1-o`, p 0.20 to 0.30), and stays as the frame for the statements. Its names fade on the ring's own progress toward its cap, not on a fixed scroll range: toCap = ln(ring-1 scale) / ln(cap), and `--names1-o` = 1 - ramp(toCap, 0.6, 0.9). They are gone before the band settles at the frame edge on every viewport shape (a fixed range left them about 27% visible at the cap on square viewports), so no name pill is ever cut while the rim holds at its capped scale; the test asserts zero names opacity at the cap across viewport shapes. The outer four rings fade out between p 0.24 and 0.34.
- **Hero exit** (p 0.02 to 0.12): the wordmark block fades and grows to 1.35x about the ring centre, then is hidden.
- **Statements:** three beats share one grid cell, entering with exponential ease-out from 2.5rem below and 10px blur, leaving upward with 6px blur. Windows: 0.22-0.30 in / 0.46-0.53 out; 0.53-0.61 / 0.72-0.79; 0.79-0.87 in and stays.
- Nothing spins or animates without scroll.

### Embedded Call Device (separate native-imitation system)
The phone at the end of the page is an iOS in-call screen with its own tokens in `globals.css`: SF/system font stack, iOS green and red call controls, iOS labels and fills, a steel-edged bezel, every measurement in iOS points times `--u`. Its rules are native fidelity, not the landing world. The landing touches it in two places only: the stage drops its own min-height and padding inside the call section, and `--u` is capped by `(100dvh - 15rem) / 836` and `(100vw - 24px) / 399` so the intro line fits above the phone.

## Do's and Don'ts

### Do:
- **Do** keep the five ring hues in their fixed order, inner violet to outer rose, one per scheme category.
- **Do** put real scheme names on the rings, upright, at landscape and portrait angles solved for 12px clearance from each other, the wordmark and the action, and hide any that still clip or collide rather than nudging them.
- **Do** set all landing type in Anek Latin at weights 500 to 800, with script text in Anek's Devanagari or Gurmukhi cut via `lang`.
- **Do** tint secondary text toward the violet ring (Lavender Mist), and borrow accent colours only from the rings.
- **Do** drive motion from scroll position, and give no-JS and reduced-motion visitors the same content as stacked sections.
- **Do** keep the call device's iOS tokens inside the device; frame it from landing.css with only stage and `--u` overrides.

### Don't:
- **Don't** add autonomous ring spin, looping animation, or motion that runs without scroll.
- **Don't** introduce grey secondary text or a sixth accent hue.
- **Don't** use squared or slightly-rounded corners on the landing; shapes are circles and pills.
- **Don't** bring the SF font stack or iOS colours out of the call device into the landing world.
- **Don't** place more than one white solid action in a viewport; the white pill is the primary action.
