# UniQ Frontend — Design Rationale

_Clinical Ledger: warm paper, ink, one-signal colour._

A short note on why the frontend looks and moves the way it does, adapted
from the original design bundle produced at claude.ai/design and updated
for our Next.js 16 + React 19 implementation.

## The core idea

Healthcare UI typically lands in one of two traps: cold blue hospital-
software or startup-purple AI-gradient. Both read as generic. UniQ's
language is **warm paper + ink** — a substrate that feels like a medical
record, a lab notebook, a ledger in a clinician's hand. Trustworthy,
deliberate, restrained. The AI is present, but it signs in ink, not neon.

## Type

- **Newsreader** (display, humanist serif) — carries the headlines and
  the "voice" moments. Italics are used as accent, never decoration.
- **IBM Plex Sans** (body) — engineered, medical-archival feel, excellent
  legibility at projector scale.
- **IBM Plex Mono** (metadata, codes, timestamps) — signals "this is
  data" without shouting.

Three fonts, each with a clear job. No Inter, no Fraunces, no Instrument
Serif — all over-indexed in the AI-startup canon. Loaded via `next/font`
in `src/app/layout.tsx`; exposed to CSS as `--font-newsreader`,
`--font-plex-sans`, `--font-plex-mono`.

## Colour

One warm paper tone (`#F4EFE6` in the warm variant, `#F4F2EF` in the
mono default), one ink (`#1A1814` / `#111110`), one signal that doubles
for approval. Ochre for pending. Muted brick for rejection. That's it.
All saturations deliberately muted; WCAG AA throughout.

Each surface has a _slightly_ different paper tone — Story `#F4F2EF`,
Review `#EFEDE9`, Analyst `#F7F5F2`. The shift is below conscious
detection but reinforces the "different room" feeling during
navigation. Applied by `src/components/nav.tsx` via
`document.documentElement.style.setProperty('--paper', tone)` on
pathname change, and faded by `html { transition: background-color }`.

## Motion

Motion exists to **signal intelligence**, not to entertain.

- **Room transitions** — handled by React's `<ViewTransition>` component
  in `src/components/page-transition.tsx` and powered by the browser's
  native View Transitions API (requires `experimental.viewTransition: true`
  in `next.config.ts`). The browser snapshots the old page, atomically
  swaps to the new tree, then cross-fades between snapshots via
  `::view-transition-old(root)` / `::view-transition-new(root)` tuned
  in `globals.css`. React is not re-rendering during the animation, so
  there's no "double-animate" flicker — a problem we hit with Framer's
  AnimatePresence before switching.
- **Hero lattice** — eighteen raw source-field chips drift at shallow
  angles, then snap into a five-bucket FHIR lattice on a 5.5s auto-cycle
  on `/`. Manual Raw / Structured toggle included. This is the one
  moment of "visual drama" the brief called for — and it doubles as a
  literal explanation of the product.
- **Approval stamp** — approving a mapping slams a slightly-rotated
  ink-stamp impression onto the row, with `mix-blend-mode: multiply`
  so it sits _on_ the paper. Reject uses brick, override uses ochre.
  The element is kept in the DOM at all times; the `.is-visible` class
  toggles to trigger the transition. `@starting-style` covers the
  first paint so freshly-mounted rows also animate cleanly instead of
  snapping to final state.
- **Thinking steps** — the Analyst streams plan steps with a spinner
  that becomes a checkmark, then types the reply character-by-character,
  then the artifact materialises in a right-side canvas (CSS grid
  `grid-template-columns` animation). Perplexity / Gemini DNA, but
  dressed in the Ledger's typography.

`prefers-reduced-motion` is respected globally — all animation
durations collapse to ~1ms for users who prefer no motion.

## Information density

Hairline rules, monospace eyebrows, measured margins. The review list
has five columns (index, category + source, FHIR target + code,
confidence, actions) and never flinches from showing full LOINC /
RxNorm / ICD-10 / SNOMED codes — clinicians want to see them.
Confidence is both a numeric readout and a hairline bar, coloured
by tier.

## The three surfaces

- **`/` Story** — editorial landing. One claim ("Healthcare data
  arrives as chaos. We ship it as structure."), one live lattice,
  four-pillar pipeline, four-stat strip, two pathway cards into the
  functional surfaces, footer.
- **`/review`** — twenty AI-proposed semantic mappings across three
  confidence tiers, keyboard-first (`A` / `O` / `R` / `↑↓` / `Esc`),
  with the stamp effect, inline override editor, progress meter, and
  a filter rail. Reads from `/api/uniq/mapping` via BFF, writes via
  `PATCH /api/uniq/mapping/{category}`. Reviewer decisions persist in
  `semantic_mapping.json` and survive pipeline re-runs.
- **`/analyst`** — conversational left, artifact canvas right. The
  layout grows into a two-pane view when an artifact is opened, and
  can be collapsed back to full-width chat. Two artifact kinds for
  now — a BMI-trajectory dashboard with KPI strip, SVG line chart and
  cohort table, and a FHIR R4 bundle viewer with view/JSON tabs.
  Phase 6 replaces the scripted thinking/typing with a real SQL-agent
  backend.

## Navigation

The nav at the top is the only shared chrome. Three rooms in a pill,
brand mark on the left (two overlapping circles — Plex ink + signal
wash — a quiet visual rhyme with the chat avatar), pipeline-live
status dot on the right. Keyboard shortcuts `1` / `2` / `3` jump
between rooms; shortcuts are suppressed when the user is typing
inside an input or textarea.

## What we deliberately didn't do

- No gradient bars, no glassmorphism, no purple, no cyan, no emoji.
- No hand-drawn SVG iconography. Iconic moments use type + ruled
  geometry (the brand mark, the approval stamp, the bucket rows).
- No dashboards with twelve widgets. The Analyst renders **one**
  artifact at a time, large, and invites inspection.
- No always-on sidebar. Navigation is three quiet words in a pill.
- No Tweaks panel (the prototype shipped palette / density / motion
  toggles as a design-exploration tool; we committed to the mono
  palette + normal density + alive motion combination and dropped
  the runtime control).

## Implementation notes

- **Stack**: Next.js 16 App Router, React 19, Tailwind 4, Motion,
  TanStack Query, `next/font`. Real styling lives in
  `src/app/globals.css` as hand-rolled CSS using design tokens
  (Tailwind utilities are available but mostly unused — Clinical
  Ledger is a design language, not a utility system).
- **BFF layer**: Browser never talks to FastAPI directly. All calls
  go through Next.js Route Handlers under `src/app/api/uniq/*`,
  which call the typed FastAPI client in `src/lib/api.ts` server-side.
  Keeps URL, auth, and streaming concerns centralised and avoids
  CORS dictating architecture.
- **BFF paths**: `/api/uniq/{health,schema,categories,mapping,
  mapping/[category],patients/[id],export/[id]/fhir,chat}`.
- **State**: TanStack Query for server state (mapping list +
  optimistic cache updates on PATCH). Per-page local state via
  `useState` / `useReducer`. No global store.
- **Paper grain**: `body::before` carries three layered radial
  gradients at different sizes + `mix-blend-mode: multiply` to
  give the paper a non-digital feel at rest. Cheap, static, GPU-
  friendly.

## Next moves

If the design keeps getting pushed:

- Wire Analyst to the real `/api/uniq/chat` endpoint (Phase 6) and
  stream tokens from the SQL agent rather than typing them client-side.
- Per-row override history in Review — ledger metaphor extends
  naturally, each decision is a signed entry.
- Dark mode as a deliberate "night-shift" theme, not an inversion —
  deep ink paper, warm amber signal.
- Cinematic Replay on `/` — a choreographed intro sequence that shows
  real pipeline data flowing through the five stages, ending at the
  live KPI strip. Would replace the current static hero for returning
  visitors while keeping the lattice for first-time attention.
- Workbench / sandbox — interactive recipe composition surface where
  a flow of source → transform → AI → output nodes can be assembled,
  run, and exported as a reusable API pipeline. Still under design;
  options being weighed are a standalone `/workbench` route vs. a
  second pane inside `/analyst` ("decompose this artifact into a
  flow I can save").
