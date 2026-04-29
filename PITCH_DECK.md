# UniQ — Pitch Deck Outline

_For Spira Labs pitch night · target 3:30 minutes · 5 slides + close_
_Last updated: 2026-04-25_
_Companion to: `POSITIONING.md` (full strategy) · `MARTIN_BRIEFING.md` · `WELLSTER_BRIEFING.md`_

---

## How to use this document

This is the **slide-by-slide breakdown** of the live pitch. Each slide
has:
- **Visual**: what's on screen
- **Spoken (the line)**: word-for-word what you say
- **Time budget**: target seconds
- **Demo action** (where applicable): what you click live
- **Why this slide exists**: which juror it's primarily for, what
  pitfall it avoids

Total target: **3 minutes 30 seconds** + 30s contingency.

Audience model:
- **Nico (Wellster CEO)** — wants concrete, demoable, Wellster-relevant
- **Martin (Spira Labs)** — wants strategic clarity, his platform
  advice evolved
- **Third juror (Digital Health expert)** — wants category creation,
  defensibility, market sizing

---

## Slide 0 · Title (5 s, optional cold-start)

**Visual**:
```
                        UniQ
            The Clinical Truth Layer

       Discovered by AI · Signed by clinicians · Served in FHIR
```

**Spoken**: *"UniQ — the Clinical Truth Layer for healthcare."*

**Why exists**: anchors the category name from word one. If the title
slide gets skipped, no harm done.

---

## Slide 1 · Open · The wall every healthcare AI hits (35 s)

**Visual**: A single question shown three different ways:

```
  question_id 109015 · "Hast Du Diabetes?"        · answer: "Nein"
  question_id 4723   · "Hast du Diabetes?"        · answer: "Ja"
  question_id 140196 · "Bestehen Vorerkrankungen…"· answer: "Diabetes"
```
Below in red: *"3 question IDs · 3 answer formats · same clinical fact."*

**Spoken**:
> *"Every healthcare company in 2026 has the same goal: deploy AI on
> patient data. None succeeds. Not because the AI is bad — the AI is
> great. Because their data does not mean what its schema says it means.
> At Wellster, the question 'do you have diabetes' lives under 67
> different IDs. That is the wall every healthcare AI runs into."*

**Time**: 30 s talk + 5 s pause for the visual to land.

**Why exists**:
- Concrete, visceral, instantly understandable
- Names Wellster (Nico hears his company)
- Frames problem as STRUCTURAL, not technical (sets up substrate
  positioning)
- Avoids the "vague healthcare data is messy" yawn

---

## Slide 2 · Problem deep-dive · The collapse number (30 s)

**Visual**: Three numbers in a flow:
```
   134,000 raw rows  →  238 unique questions  →  26 categories
                                                       │
                                                       ▼
                                          structurally impossible
                                          for a data team to maintain
```

**Spoken**:
> *"Manual coding takes weeks. Costs millions. Breaks the moment a
> survey changes. Wellster's full population — 2 million patients,
> 60 million data points — would take a 15-person data team six months
> just to map once. Then the next survey update breaks it."*

**Time**: 25 s talk + 5 s pause.

**Why exists**:
- Reinforces it's not a tooling problem, it's a structural one
- Quantifies (data-team cost > tooling cost)
- Mentions Wellster scale (Nico hears commitment to scale)
- Creates demand for the next slide

---

## Slide 3 · Solution + live demo · The Clinical Truth Layer (90 s)

**Visual** (then transition to live screen):
```
                  ┌─────────────────────────────┐
                  │                             │
                  │   UniQ Truth Layer          │
                  │                             │
                  │   • Discovered (AI)         │
                  │   • Signed (HITL)           │
                  │   • FHIR-native             │
                  │                             │
                  └─────────────┬───────────────┘
                                │
              Raw data ─────────┘─────────→  any consumer
              (any source)                    (analytics, AI, FHIR, regulators)
```

**Spoken (intro, 15 s)**:
> *"UniQ is the Clinical Truth Layer. Discovered by AI. Signed by
> clinicians. Served in FHIR. Watch the substrate become a repository
> and then power two different consumers."*

**Demo sequence (75 s, live in browser)**:

| Time | Surface | What you click | What you say |
|---|---|---|---|
| 0–10 s | `/start` | Click "Run intake" | *"AI discovers the structure — 134K rows, 26 clinical categories, two API calls."* |
| 10–25 s | `/review` | Click Approve on the BMI pivot | *"A clinician signs off on every semantic decision. This is what makes it deployable in production."* |
| 25–40 s | `/substrate-ready` | Let repository map materialise | *"Approval does not create a report. It materializes a clinical repository: patients linked to BMI timeline, medications, quality flags, survey events, mappings and FHIR bundles — all keyed, signed and queryable."* |
| 40–55 s | `/analyst` | Type "Open patient 383871" | *"This is one consumer of that repository: one patient's full clinical timeline. BMI down four points, dose escalated 2.5 to 5 mg, side effects logged, every event signed by a clinician."* |
| 55–65 s | (still patient_record) | Click any BMI dot, then FHIR export | *"Click any data point: raw source field, normalised category, LOINC code, clinician sign-off. One click exports the FHIR Bundle."* |
| 65–75 s | `/analyst` | Type "Find GoLighter screening candidates from Spring" | *"Second consumer, same repository: 456 active Spring patients with BMI ≥ 27 and no GoLighter history — an operational cohort Wellster can review this quarter."* |

**Why exists**:
- This is the SHOW slide — the wow. Everything before sets up, this delivers.
- The repository map prevents UniQ from reading as a single-use analyst app
- patient_record and opportunity_list become two consumers of one truth layer
- Lineage ribbon (169 → 1 → 123/123 → 135) is the moat in 10 seconds
- Audit-trail click is the moment that differentiates from any dashboard
- FHIR export answers "is this real?" with a downloaded file

---

## Slide 4 · Reference companies · Trust floor (30 s)

**Visual**:
```
LAYER ABOVE:        Aily Labs               $80M Series B (Nov 2025)
                    AI Decision Intelligence on enterprise data

LAYER ABOVE:        Flatiron Health         $1.9B exit to Roche (2018)
                    Curated oncology RWD for pharma

LAYER ABOVE:        Dandelion Health        $16M Seed (2024)
                    Multimodal RWD library for research

           ────────────────────────────────────
                      UniQ Truth Layer
              upstream of all three · clinical
              ground truth for the AI era
           ────────────────────────────────────
```

**Spoken**:
> *"Flatiron proved this pattern is worth $1.9B for oncology — collapse
> fragmented clinical data into trusted records, sell to pharma.
> Dandelion proves the segment is fundable in 2024+ with $16M seed and
> a GLP-1 library. Aily proves the AI-on-structured-data layer above us
> is worth $80M Series B in six months. We are upstream of all three —
> the clinical truth layer that makes their patterns possible for
> telehealth, in the AI era."*

**Time**: 30 s.

**Why exists**:
- Trust floor (third juror needs comp anchoring)
- Differentiation framed as upstream, not aspirational
- Multiple comps prevent "but this is just X" pushback

---

## Slide 5 · Why now · Four forces converging (25 s)

**Visual**:
```
   ┌─────────────────────────┬─────────────────────────┐
   │   AI WAVE               │   ePA / EHDS / CURES    │
   │   needs ground truth    │   FHIR is regulatory    │
   │   (else: liability)     │   floor (else: penalty) │
   ├─────────────────────────┼─────────────────────────┤
   │   GDNG                  │   GLP-1 EXPLOSION       │
   │   enables data USE for  │   manual coding         │
   │   precision medicine    │   structurally fails    │
   │   (positive!)           │   (else: cost)          │
   └─────────────────────────┴─────────────────────────┘
```

**Spoken**:
> *"Four forces in the same window. AI agents need clinician-validated
> data or they're a liability. ePA and EHDS made FHIR a regulatory
> floor. GDNG — Germany's Health Data Use Act — actively enables data
> monetisation for precision medicine, but only if the data is
> structured and audit-trail-backed. And the GLP-1 explosion makes
> manual coding structurally unscalable. This is the eighteen-month
> window. Whoever is the trusted truth layer at scale by 2027 defines
> the category."*

**Time**: 25 s.

**Why exists**:
- GDNG is unique to us (no other startup pitches this — positive
  regulatory framing instead of compliance-burden whining)
- "Eighteen-month window" creates urgency
- "Defines the category" makes the bet feel category-creating

---

## Slide 6 · Close · The opportunity (25 s)

**Visual**:
```
                      One truth layer.
                      Infinite consumers.

           Wellster proof point — live, signed, FHIR.
           Onboarding 5 days. Operation autonomous.

                      What will you build on it?
```

**Spoken**:
> *"We don't ask you to commit to a use case we don't understand. We
> make your data computable. Your team builds anything on top —
> analytics, FHIR exports, AI agents, partner APIs, GDNG-activated
> RWD. Setup is five days, operation is autonomous. Wellster is the
> first proof. We're inviting the next telehealth player to be the
> second."*

**Time**: 25 s.

**Why exists**:
- Closes with Martin's "you build, we enable" framing (he hears his
  advice evolved)
- "Setup 5 days, operation autonomous" answers "how do I deploy this"
  unspoken question
- Open invitation, not a hard ask — fits pitch-night format

---

## Total timing check

| Slide | Target | Cumulative |
|---|---|---|
| 0 · Title (optional) | 5 s | 0:05 |
| 1 · Problem · the wall | 35 s | 0:40 |
| 2 · Problem deep-dive | 30 s | 1:10 |
| 3 · Solution + demo | 90 s | 2:40 |
| 4 · References | 30 s | 3:10 |
| 5 · Why now (4 forces) | 25 s | 3:35 |
| 6 · Close | 25 s | 4:00 |

→ **4:00 if everything tight.** The repository map earns the extra 15s
because it prevents the demo from reading as a one-off analyst workflow.
If the room is strict on time, cut Slide 4 to one sentence and keep the
repository + patient_record + screening-candidates sequence intact.

---

## What we deliberately CUT from older drafts

- **Story page Lattice animation** (15 s, too slow, no information density)
- **Platform Agents-tab interactive configurator** (25 s, too distracted
  from the patient_record moment)
- **Old first-rows Substrate-Ready preview** — replaced by a repository
  map with resources, FK labels, API hooks and audit provenance

These cuts keep the product proof focused: repository first, then two
consumers of that repository (`patient_record` and `opportunity_list`).

---

## Q&A preparation — likely jury questions and answers

| Likely question | Short answer | Why it's good |
|---|---|---|
| *"Why aren't you building the AI agent yourselves?"* | "Because we'd be one specific consumer of our own substrate. Stay upstream is the discipline." | Reinforces strategic clarity |
| *"How is this different from Flatiron?"* | "Flatiron is a data marketplace selling to pharma. We're an infrastructure layer the data owners themselves use. Different buyer, different layer, different market." | Pre-rehearsed comp-defense |
| *"Couldn't Wellster's data team build this themselves?"* | "Two to four months of engineering for the first run, plus rebuild every survey update. We do it in seconds, governed, FHIR-exportable, no engineering cost." | Quantified moat |
| *"What about MySummer (your 3rd brand)?"* | "Wasn't in the hackathon dataset. The architecture handles it as soon as we get access — incremental classification, no refactor." | Honest, not defensive |
| *"Where does it run? On-prem? Cloud?"* | "Both. Substrate is portable Python + DuckDB. Customers can run it in their own VPC, our hosted environment, or hybrid. MedGemma fallback for full on-prem." | Answers infra concern |
| *"What's your business model?"* | "Setup fee + tiered subscription based on patient volume / API usage / FHIR resources exported. White-glove onboarding, autonomous operation." | Concrete, not hand-wavy |
| *"How is this not just another data integration tool?"* | "Integration tools assume schemas exist. We discover them. AI mapping + clinician HITL + FHIR-native output is not a feature any integration tool has." | Category clarity |
| *"GDNG — really, will telehealth companies pay for this?"* | "60M Wellster data points, anonymised, structured, GDNG-compliant — that's a pharma-licensable RWD asset they can't build today. Compliance enables revenue, not just avoids penalty." | Reframes regulatory as positive |

---

## Killer soundbites (drop into Q&A or follow-up)

- *"AI is timing. Clinical truth is identity."*
- *"Healthcare AI fails on data, not models. We fix the data."*
- *"FHIR is now law. Most platforms are 12 months from ready. We make
  any data FHIR-ready in weeks."*
- *"169 raw fields, one trusted record, every event clinician-signed,
  135 FHIR resources — in seconds."*
- *"Flatiron unified oncology for pharma. We unify telehealth for
  everyone — for analytics, agents, exports, GDNG-RWD."*
- *"Setup five days, operation autonomous. That's the business model."*

---

## What success looks like at pitch end

- Nico thinks: *"I want to be the proof point. Let's pilot Monday."*
- Martin thinks: *"They evolved my platform advice into a real category.
  Sharper than I expected."*
- Third juror thinks: *"This is the AI-era data infrastructure play I've
  been waiting to see in healthcare."*

If we're somewhere on the spectrum from "want to keep talking" to "want
to invest" with each of them, the pitch worked.

---

_Living artifact. Update after pitch night with what landed and what didn't._
