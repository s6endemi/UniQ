# Briefing · Martin · UniQ Strategic Positioning Update

_For tomorrow's call · ~25 minutes_

## What changed since we last spoke

Three weeks ago you told me: stop guessing the customer's use case — give
them the substrate, let them build on top. That unlocked the right shape,
but I kept describing UniQ in the wrong words. "AI Agent Infrastructure"
one day, "Data Cleaning Tool" the next. Both too narrow.

After research (Dandelion, Flatiron, Aily) and pressure-testing, the right
frame:

> **UniQ is the Clinical Truth Layer.**
> The layer between chaotic source data and any downstream
> consumer — analytics, FHIR partners, AI agents, regulators —
> turning raw input into clinician-signed, FHIR-native ground truth.
> Healthcare data, finally computable.

Your platform advice, sharpened: platform was the *shape*, the truth layer
is the *identity*. "Truth" is not marketing — it's the literal output of
HITL. "Layer" is universally understood (unlike "substrate", which I tried
first and ditched as too academic).

---

## Three reasons this is the right frame

**1 · It is what we objectively built.** HITL workflow, template-bound
artifacts, FHIR-native exports, handle-based agent loop — every architectural
choice produces clinician-signed ground truth, not a single consumer's view.
Calling us "AI Agent Infrastructure" is narrower than what's on `main`.

**2 · The category survives wave shifts.** AI agents are *timing*. The
clinical truth layer is *identity*. Whichever consumer wave hits next
(post-agent, embedded LLMs, vertical copilots) still needs structured,
governed, FHIR-ready clinical data. The category outlives the moment.

**3 · References are stronger upstream.** Flatiron ($1.9B, oncology)
proves the pattern. Dandelion (GLP-1 RWD library, $16M seed) proves the
modern segment is fundable. Aily ($80M Series B, Nov 2025) proves the
layer *above* us is fundable. **We are upstream of all three; none of them
solve our discovery problem.**

---

## Demo evolution since we last spoke

New `/analyst` artifact: `patient_record` — single-patient deep view
combining a multi-track timeline (BMI · medication · side effects ·
conditions · quality flags) with full audit-trail provenance per data
point and one-click FHIR export.

The lineage ribbon at the top reads:

> **169 raw fields → 1 unified record → 123/123 clinician-signed → 135 FHIR resources**

That single line communicates the truth-layer moat in 10 seconds, without
any clicking. It's the answer to the ImpactInfo dashboard claim — they
show patient data, we show patient data *plus the audited collapse of
chaos into clinical truth*. Different category.

---

## Pitch opening I want to test on you

> *"Every healthcare company in 2026 has the same goal: deploy AI on
> patient data. None succeeds. Not because the AI is bad — the AI is
> great. Because their data doesn't mean what its schema says it means.
> At Wellster, the question 'do you have diabetes?' lives under 67
> different IDs. We are the **Clinical Truth Layer** that gets past it.
> Discovered by AI. Signed by clinicians. Served in FHIR."*

---

## Three questions for you tomorrow

1. **Does "Clinical Truth Layer" land?** Or too abstract for the
   jury (Nico, you, the Digital Health investor)? If abstract, what
   concrete framing keeps the truth-layer identity but lands harder?

2. **Should I cut the Platform tab from the demo?** Recommend yes —
   saves ~25 s for the patient_record moment which is now the strongest
   visual we have. Or does keeping the Agents preview reinforce the
   multi-consumer story enough to justify the time?

3. **What will Nico ask that this positioning doesn't answer?** You
   know him better than I do. Flag the gap before he opens it on Friday.

---

_Full positioning doc with reference logic, moat analysis, customer
use-case map, and 3.5-minute pitch structure: `POSITIONING.md` at repo
root. This page is the conversation starter — read the long doc only
if you want depth before tomorrow._
