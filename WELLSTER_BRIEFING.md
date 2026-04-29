# Briefing · Wellster Conversation
_For Irena Medlin & Maria Chernevich_
_Sender: Eren Demir · UniQ_
_Last updated: 2026-04-25_

---

## Why this conversation

Martin (Spira Labs) suggested we connect. UniQ has been working with the
hackathon dataset (134K rows · 5,374 patients · GoLighter + Spring · Q1 2025
through Mar 2026) for 8 weeks. That's about **0.27% of Wellster's full
patient population** of ~2M and ~60M anonymised data points — a small
slice, but enough to surface insights and prove the architecture works at
your scale. We've built something we think your team can activate inside
30 days. This page is the conversation starter — not a sales pitch. We
want to learn what you actually need before we make commitments.

---

## What we built — in one sentence

> **UniQ is the Clinical Truth Layer.** Your fragmented questionnaire data
> becomes one continuously-updated, clinician-signed, FHIR-native record per
> patient — usable today by analytics, tomorrow by your AI agents, always
> by ePA.

What's live on `main`, demoable in five minutes:

- **Pipeline**: 134K raw rows → 20 clinical categories → unified substrate
  (no hardcoded schemas, AI discovers structure)
- **Clinician sign-off**: every semantic decision passes through HITL
  review with persistent audit trail per data point
- **FHIR R4 export**: per-patient bundles with LOINC, ICD-10, RxNorm,
  SNOMED codes — ePA-ready out of the box
- **Live analyst**: natural-language queries against the substrate that
  return validated chart / table / patient-record / FHIR-bundle artifacts
- **Every event traceable**: raw source field → normalised category →
  standard code → which clinician approved it on which day

---

## What we found in your data — four things you can use

After 8 weeks operating on the hackathon slice, four patterns surfaced
that look like real Wellster value — not generic platform talk.

### 1 · Cross-brand cross-sell opportunity (immediate revenue)

**The substrate sees Spring and GoLighter as one patient population.**
4,557 Spring patients (sexual health), 835 GoLighter patients (obesity), 18
patients active in both. **4,901 patients reported BMI** at intake — but
Wellster only has ~835 of them in the GLP-1 funnel.

→ **Spring patients with BMI > 27 who are NOT on any GoLighter product** is
a cross-sell list Wellster could activate this quarter. The substrate
generates this list in seconds.

> *Demo prompt*: "Show me Spring patients with BMI over 27 who are not on
> GLP-1 — sorted by tenure for outreach prioritisation."

This is one query. The same substrate answers any cross-brand cohort
question your team can phrase in plain language.

### 2 · ePA / FHIR compliance, day one (regulatory floor)

ePA mandates have been live since January 2026 with sanctions (up to 2 %
billing deduction). Most telehealth platforms are 12–18 months from
compliance. We export every patient's record as FHIR R4 with full
LOINC / ICD-10 / RxNorm / SNOMED codes — ready to submit, signed off by
clinicians, audit-trail-backed per data point.

> *Demo*: open patient PT-383871 → click "Export FHIR" → get a 135-resource
> Bundle in two seconds.

### 3 · GDNG activation — turning compliance into revenue (regulatory ceiling)

The German Health Data Use Act (Gesundheitsdatennutzungsgesetz, 2024) was
written explicitly to **enable** secondary use of anonymised health data
for precision medicine, RWD partnerships, and AI training — provided the
data is structured, clinician-validated, and audit-trail-backed.

Most telehealth platforms cannot activate GDNG today because their data
fails the structural prerequisites. **UniQ is the operational answer to
GDNG**: HITL workflow + FHIR-native + full provenance per data point.

→ Wellster's 60M+ data point treasure becomes a **monetisable asset**
under GDNG — pharma RWD partnerships, precision-medicine collaborations,
AI-training licensing — without the 12-month compliance build that most
competitors face.

### 4 · Operational quality signal (operational hygiene)

The substrate's quality_report surfaces operational issues your clinical
ops team would otherwise miss. From our hackathon slice:
- **819 undocumented medication switches** (patient changed Rx without
  recorded justification)
- **147 BMI gaps** (>112 days between measurements on active patients)
- **34 BMI spikes** (>5-point change between consecutive measurements)

Each comes with the patient ID, treatment ID, and full audit context. This
isn't a separate tool — it's a query against the substrate. Scaled to your
2M patient base, conservative estimate: 30,000+ findings that would
otherwise stay invisible.

---

## What's honest about where we are

To respect your time: a clean inventory of what's real vs. roadmap.

**Live and proven on the hackathon slice today**:
- All four use cases above (cross-sell, FHIR, GDNG-prep, quality)
- Multi-brand substrate (GoLighter + Spring unified)
- AI analyst with 14/16 eval score on canonical questions
- Single-patient deep view with audit-trail provenance per event
- FHIR export end-to-end with full standards-coding

**Architecture proven, scale-portable**:
- Pipeline runs on Pandas + DuckDB; tested 12K → 23K → 134K rows with
  zero code changes
- Linear scaling to your 60M+ data points is a data-volume question,
  not an architecture question
- Incremental classification means new survey versions add minutes,
  not weeks

**Roadmap (Phase 2, not yet built)**:
- MySummer onboarding (your 3rd brand isn't in the dataset we received)
- Multi-modal input: clinical notes, PDFs, lab values, wearables
- Direct clinician-contribution interface (write annotations, upload notes)
- Webhook/streaming for real-time substrate updates

**Not in scope, ever** (this is your moat, not ours):
- Customer-facing dashboards (you build those)
- Specific AI agents (your team or partners build them)
- Brand-specific clinical workflows (your clinicians own these)

---

## How a 30 / 60 / 90 day pilot could look

Not a commitment from you yet — sketching what we'd propose if you say
"yes". The shape is what every successful B2B data platform follows:
**human-led onboarding (days), AI-augmented operation (continuous)**.

### Days 0–7 — Onboarding (human-led, ~5 days of effort total)

Day 1–2 (4h pro Tag, joint session):
- We sit down with your data team
- Walk through your data sources (Spring, GoLighter, MySummer if available)
- Identify quirks: language switches, brand-specific surveys, schema
  versions, ePA-relevante Felder
- Sketch loader configuration

Day 3–5:
- Run pipeline on a recent Wellster export (or read-only DB connection)
- Categories discovered, FHIR resources + medical codes proposed
- Your clinical lead reviews mappings via `/review` UI (~2h total)
- First production substrate built

Day 5–7:
- FHIR export validation with your compliance team
- Integration touchpoint definition (where does substrate output flow?)
- 5 hand-picked patients walked through end-to-end

### Days 7–30 — First use cases live

- **Cross-sell list** activated (Spring BMI > 27 → GoLighter outreach
  funnel). Run weekly, review conversion in week 4.
- **FHIR export sample** validated with compliance team for ePA submission.
- **One clinical analytics question** answered by /analyst that your team
  needs answered weekly (you choose which).
- ~30 min/month of HITL time for new patterns the AI surfaces.

### Days 30–60 — Operation (continuous, AI-augmented)

- Substrate maintains itself. New surveys → AI classifies incrementally
  → only genuinely new patterns escalate to HITL (typically 2–5/month).
- Your team queries via /analyst, exports FHIR on demand, runs the
  cross-sell job on a schedule.
- We sit in monthly check-in (60 min) to review what's working.

### Days 60–90 — Decide together

- Did UniQ deliver what we said?
- Quantify: time saved on coding · revenue unlocked from cross-sell ·
  compliance-readiness gained · GDNG-activation potential
- Either: scope production engagement (pricing, infra, contract, MySummer
  onboarding)
- Or: walk away clean — you keep the substrate snapshot, we keep the
  cross-customer learnings (anonymised, GDPR-safe)

---

## What we'd need from you

For the pilot to be meaningful, three things:

1. **Data access** — read-only export of the same shape as the hackathon
   dataset. Plus MySummer if you can include it.
2. **One clinical reviewer** — ≤4 hours total over 30 days for HITL
   sign-off on the discovered category mappings.
3. **One sponsor on your side** — to align with whichever stakeholder
   needs to see "yes this is worth scaling".

We don't need: dedicated engineering time, infrastructure changes on your
end, integration with your existing systems (we can run side-by-side).

---

## What we'd love to learn from you

Honestly more important than what we've built. Five questions for the
first call:

1. **What's the use case Wellster would most want to activate first?**
   (analytics, compliance, cross-sell, AI experimentation, something else?)
2. **Where does data integration usually break for you internally?**
   (we want to know what NOT to do)
3. **Who actually consumes patient-level data today, and how?**
   (clinicians? analysts? compliance? customer-success?)
4. **What's the bar for "this is production-ready" at Wellster?**
   (compliance, security review, infra requirements?)
5. **What's the worst version of "another vendor pitch" you've sat
   through, and what made it bad?** (we want to not be that)

---

## What we built since the hackathon

For context, in case it's useful before our call:

- 6 live surfaces (`/`, `/start`, `/review`, `/substrate-ready`, `/analyst`,
  `/platform`) — the guided demo runs end-to-end in 3.5 minutes
- v2 unified Sonnet agent with handle-based artifact contract
- New patient-record artifact: identity header + KPIs + BMI hero chart
  with WHO baseline reference + 4-track event timeline + audit trail
  panel + FHIR export
- New screening-candidates artifact: Spring → GoLighter cohort funnel
  (BMI ≥ 27, no GoLighter history, active in last 180 days), yielding
  456 active candidates and 60 high-priority review cases
- New substrate repository map: patients hub, six linked resources,
  semantic-mapping governance layer, API hooks, and audit provenance
- 17/3/0 mapping review state (17 clinical categories approved, 3 upload
  workflows rejected, 0 pending)
- 3,731+ FHIR R4 resources exportable from current substrate

We can demo any of these live. Or send loom recordings if you prefer
async first.

---

## Logistics

**Suggested first call**: 30 minutes. Async screen-share intro to UniQ
(10 min), Q&A on Wellster's actual world (20 min). Goal: decide
whether a 30-day pilot makes sense.

**Timing**: any week starting 2026-04-28. The Spira Labs pitch night is
in late April — happy to wait until that's behind us if you'd rather
schedule for week of 2026-05-05.

**Format**: Google Meet / Teams / in-person Munich, your call.

**Reply to**: erendemir10022@gmail.com

---

_Looking forward to learning what your real world looks like. — Eren_
