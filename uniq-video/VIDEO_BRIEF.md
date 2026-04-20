# VIDEO BRIEF — UniQ Pitch Animation

## YOUR ROLE

You are a senior motion designer at a health-tech startup. Think Apple keynote meets
Y Combinator demo day. Your work is minimal, precise, and every frame has purpose.
Nothing decorative. Everything communicates.

## THE PRODUCT

UniQ — an AI engine that unifies fragmented healthcare questionnaire data.

The core story in one line:
**Fragmented data in. Unified, coded, interoperable healthcare data out.**

## THE NUMBERS (use these — they're real)

- 134,000 patient survey rows processed
- 4,553 question IDs in the raw data — fragmented, unusable
- The same question ("What is your blood pressure?") exists under 263 different IDs
- AI classified all questions in 1 API call → 26 clinical categories
- 416 answer variants normalized → 164 canonical labels
- "Normal blood pressure" was expressed in 9 different text variants (German + English + rewording)
- 99.9% of parsing is deterministic — AI only classifies, code does the rest
- Total cost: $0.10 for 134K rows
- 0 hardcoded rules — AI discovers categories from scratch
- Output: FHIR R4 with ICD-10, SNOMED CT, RxNorm, LOINC medical codes
- 5,374 patients, 8,835 treatments, 19 medications, 2 brands unified
- 1,010 quality alerts found that were invisible in the raw data
- Human-in-the-loop: AI proposes, medical team validates

## THE STORY ARC

1. **The chaos** — show the fragmentation problem. Make it feel overwhelming.
2. **The moment** — UniQ processes it. Clean. Fast. One call.
3. **The proof** — before vs after. Numbers that speak for themselves.
4. **The standard** — not custom labels. Real medical codes. FHIR R4. Production-grade.
5. **The close** — the product. The tagline.

## DESIGN DIRECTION

- Dark background (#0B0F1A)
- Primary accent: #00C9A7 (Wellster green)
- Typography: Inter, heavy weights for numbers, light for labels
- Motion: spring animations, staggered reveals, nothing sudden
- No stock footage. No illustrations. Just typography, numbers, and motion.
- Every element earns its place on screen

## CONTEXT

This is for a healthcare hackathon by Wellster Healthtech Group (Munich).
The jury scores: Solution Feasibility (12pts), Problem Identification (9pts),
Research Understanding (9pts), Innovation (6pts), Data Usage (6pts),
Presentation (6pts), Bonus for working demo (5pts). Total: 53 points.

## TECHNICAL

- Remotion (React-based video framework) is set up at this project root
- 1920x1080, 30fps
- The video has 6 scenes already built — improve, redesign, or rebuild as needed
- Existing scenes: Logo, Chaos, Engine, Proof, Standards, Close
- Use @remotion/transitions for scene transitions
- All animations via useCurrentFrame() + interpolate/spring — no CSS animations
