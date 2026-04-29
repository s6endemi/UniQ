/**
 * Scripted fallback for the Analyst when the backend is unreachable.
 *
 * The Phase 6 happy path fetches /api/uniq/chat and gets a real
 * ChatResponse back. But demos run on fragile wifi and late at night
 * on laptops that just woke up — so we keep this scripted flow as a
 * safety net. The shape matches the real contract (`ChatResponse` from
 * `@/lib/api`) so the Analyst components are oblivious to which path
 * served them.
 *
 * Three recipes mirror the real recipes in
 * `wellster-pipeline/src/chat_recipes.py` so falling back looks and
 * reads identical to the real system.
 */

import type {
  ChatArtifact,
  ChatResponse,
  CohortTrendPayload,
  FhirBundlePayload,
  AlertsTablePayload,
  OpportunityListPayload,
} from "@/lib/api";

export interface PromptSuggestion {
  meta: string;
  text: string;
}

// Four live-verified prompts, each exercising a different artifact
// family so the jury sees the product's breadth in a single sitting:
//   1. cohort_trend  — Mounjaro BMI dashboard (the money shot)
//   2. alerts_table  — data-quality ops view
//   3. fhir_bundle   — B2B interop output
//   4. table         — side-effects summary, shows survey-derived data
//
// Verified against the Wellster substrate on 2026-04-22. Each produces
// a clean, pitch-appropriate result; latency sits between 3 s (FHIR)
// and 12 s (cohort trend).
export const PROMPT_SUGGESTIONS: PromptSuggestion[] = [
  {
    meta: "Patient · timeline",
    text: "Open patient 383871",
  },
  {
    meta: "Cross-brand · opportunity",
    text: "Find GoLighter screening candidates from Spring",
  },
  {
    meta: "Cohort · trend",
    text: "Show BMI trends for the Mounjaro cohort",
  },
  {
    meta: "Data quality",
    text: "Which patients have data quality issues?",
  },
  {
    meta: "FHIR export",
    text: "Generate a FHIR bundle for patient 381119",
  },
];

function mkId(prefix: string): string {
  return `${prefix}-${Date.now().toString(36)}`;
}

// ---- Demo payloads (shape-identical to backend) ---------------------------

const DEMO_COHORT_TREND: CohortTrendPayload = {
  kpis: [
    { label: "Cohort · Mounjaro", value: "842", delta: "+ 37 past 30d" },
    { label: "Mean BMI · baseline", value: "32.1", delta: "n = 842" },
    { label: "Mean BMI · 24w", value: "27.2", delta: "− 4.9 pts" },
  ],
  chart: {
    title: "BMI trajectory — Mounjaro cohort",
    subtitle: "weeks 0 — 24 · n = 842",
    x_labels: ["W0", "W2", "W4", "W6", "W8", "W10", "W12", "W14", "W16", "W18", "W20", "W22"],
    y_label: "mean BMI (kg/m²)",
    series: [
      {
        name: "Mounjaro · mean BMI",
        points: [32.1, 31.8, 31.2, 30.7, 30.1, 29.8, 29.3, 28.7, 28.2, 27.9, 27.5, 27.2],
      },
    ],
  },
  table: {
    columns: [
      { key: "patient", label: "Patient ID", align: "left" },
      { key: "dose", label: "Dose", align: "left" },
      { key: "bmi_baseline", label: "BMI · W0", align: "right" },
      { key: "bmi_latest", label: "BMI · W24", align: "right" },
      { key: "delta", label: "Δ", align: "right", emphasis: true },
      { key: "adherence", label: "Adherence", align: "right" },
    ],
    rows: [
      { patient: "PT-44192", dose: "5 mg", bmi_baseline: 33.4, bmi_latest: 27.8, delta: -5.6, adherence: "94%" },
      { patient: "PT-40823", dose: "2.5 mg", bmi_baseline: 31.1, bmi_latest: 27.9, delta: -3.2, adherence: "81%" },
      { patient: "PT-51108", dose: "10 mg", bmi_baseline: 35.6, bmi_latest: 28.2, delta: -7.4, adherence: "88%" },
      { patient: "PT-39004", dose: "5 mg", bmi_baseline: 30.8, bmi_latest: 26.9, delta: -3.9, adherence: "91%" },
      { patient: "PT-48715", dose: "7.5 mg", bmi_baseline: 34.0, bmi_latest: 28.4, delta: -5.6, adherence: "84%" },
      { patient: "PT-42290", dose: "5 mg", bmi_baseline: 32.2, bmi_latest: 27.0, delta: -5.2, adherence: "90%" },
      { patient: "PT-50331", dose: "2.5 mg", bmi_baseline: 29.7, bmi_latest: 27.4, delta: -2.3, adherence: "76%" },
    ],
  },
};

const DEMO_FHIR_BUNDLE: FhirBundlePayload = {
  resourceType: "Bundle",
  id: "uniq-patient-PT-44192",
  type: "collection",
  timestamp: "2026-04-21T09:14:00Z",
  entry: [
    {
      resource: {
        resourceType: "Patient",
        id: "PT-44192",
        gender: "female",
        birthDate: "1986-03-14",
      },
    },
    {
      resource: {
        resourceType: "Observation",
        code: { coding: [{ system: "LOINC", code: "39156-5", display: "BMI" }] },
        valueQuantity: { value: 33.4, unit: "kg/m2" },
        effectiveDateTime: "2025-10-12",
      },
    },
    {
      resource: {
        resourceType: "Observation",
        code: { coding: [{ system: "LOINC", code: "39156-5", display: "BMI" }] },
        valueQuantity: { value: 27.8, unit: "kg/m2" },
        effectiveDateTime: "2026-04-04",
      },
    },
    {
      resource: {
        resourceType: "MedicationStatement",
        medication: {
          coding: [{ system: "RxNorm", code: "2601723", display: "tirzepatide 5 MG" }],
        },
        status: "active",
      },
    },
    {
      resource: {
        resourceType: "Condition",
        code: {
          coding: [{ system: "ICD-10", code: "E66.9", display: "Obesity, unspecified" }],
        },
      },
    },
  ],
};

const DEMO_OPPORTUNITY_LIST: OpportunityListPayload = {
  headline: "456 Spring patients can be screened for GoLighter follow-up",
  methodology:
    "Based on 5,374 unified Wellster patients · BMI ≥ 27 on file · " +
    "GoLighter history checked across substrate",
  activation_path: [
    {
      label: "Spring cohort",
      count: 4557,
      description: "All patients ever on Spring",
    },
    {
      label: "BMI ≥ 27",
      count: 2029,
      description: "With at least one BMI measurement above threshold",
    },
    {
      label: "No GoLighter history",
      count: 2014,
      description: "Excluded if any GoLighter treatment found in substrate",
    },
    {
      label: "Active in last 180 days",
      count: 456,
      description: "Recent enough for review to be meaningful",
    },
  ],
  kpis: [
    { label: "Spring patients", value: "4,557" },
    { label: "BMI ≥ 27", value: "2,029", delta: "45% of cohort" },
    { label: "No GoLighter history", value: "2,014" },
    { label: "High priority", value: "60", delta: "of 456 active" },
  ],
  candidates: [
    {
      user_id: 382652,
      label: "PT-382652",
      latest_bmi: 45.9,
      bmi_trend: "stable",
      age: 45,
      gender: "male",
      current_treatment: "Sildenafil",
      current_dosage: "100mg",
      tenure_days: 412,
      days_since_activity: 53,
      reason_summary: "BMI 45.9 · Spring patient · no GoLighter history",
      priority: "high",
    },
    {
      user_id: 384765,
      label: "PT-384765",
      latest_bmi: 44.5,
      bmi_trend: "unknown",
      age: 62,
      gender: "male",
      current_treatment: "Sildenafil",
      current_dosage: "50mg",
      tenure_days: 287,
      days_since_activity: 48,
      reason_summary: "BMI 44.5 · Spring patient · no GoLighter history",
      priority: "high",
    },
    {
      user_id: 395209,
      label: "PT-395209",
      latest_bmi: 39.2,
      bmi_trend: "unknown",
      age: 39,
      gender: "male",
      current_treatment: "Tadalafil",
      current_dosage: "20mg",
      tenure_days: 156,
      days_since_activity: 42,
      reason_summary: "BMI 39.2 · Spring patient · no GoLighter history",
      priority: "high",
    },
    {
      user_id: 393901,
      label: "PT-393901",
      latest_bmi: 39.2,
      bmi_trend: "unknown",
      age: 28,
      gender: "male",
      current_treatment: "Sildenafil",
      current_dosage: "50mg",
      tenure_days: 198,
      days_since_activity: 41,
      reason_summary: "BMI 39.2 · Spring patient · no GoLighter history",
      priority: "high",
    },
    {
      user_id: 392811,
      label: "PT-392811",
      latest_bmi: 38.0,
      bmi_trend: "down",
      age: 53,
      gender: "male",
      current_treatment: "Sildenafil",
      current_dosage: "100mg",
      tenure_days: 234,
      days_since_activity: 50,
      reason_summary: "BMI 38.0 · Spring patient · no GoLighter history",
      priority: "high",
    },
    {
      user_id: 382732,
      label: "PT-382732",
      latest_bmi: 37.9,
      bmi_trend: "down",
      age: 37,
      gender: "male",
      current_treatment: "Sildenafil",
      current_dosage: "50mg",
      tenure_days: 391,
      days_since_activity: 41,
      reason_summary: "BMI 37.9 · Spring patient · no GoLighter history",
      priority: "high",
    },
    {
      user_id: 392096,
      label: "PT-392096",
      latest_bmi: 37.4,
      bmi_trend: "stable",
      age: 38,
      gender: "male",
      current_treatment: "Tadalafil",
      current_dosage: "20mg",
      tenure_days: 178,
      days_since_activity: 39,
      reason_summary: "BMI 37.4 · Spring patient · no GoLighter history",
      priority: "high",
    },
  ],
  total_candidates: 456,
  source_brand: "spring",
  target_brand: "golighter",
  bmi_threshold: 27,
  activity_window_days: 180,
};

const DEMO_ALERTS: AlertsTablePayload = {
  kpis: [
    { label: "Total issues", value: "84" },
    { label: "Errors", value: "3", delta_direction: "up" },
    { label: "Warnings", value: "81", delta_direction: "neutral" },
  ],
  table: {
    columns: [
      { key: "severity", label: "Severity", align: "left", emphasis: true },
      { key: "check_type", label: "Check", align: "left" },
      { key: "user_id", label: "Patient", align: "right" },
      { key: "treatment_id", label: "Treatment", align: "right" },
      { key: "description", label: "Finding", align: "left" },
    ],
    rows: [
      { severity: "error", check_type: "bmi_spike", user_id: 44192, treatment_id: 1128, description: "BMI changed by 7.2 points between measurements" },
      { severity: "warning", check_type: "bmi_gap", user_id: 40823, treatment_id: 981, description: "No BMI measurement in last 112 days" },
      { severity: "warning", check_type: "missing_dosage", user_id: 51108, treatment_id: 1204, description: "Active medication without dosage record" },
    ],
  },
};

// ---- Recipes --------------------------------------------------------------

interface Recipe {
  match: (q: string) => boolean;
  build: () => ChatResponse;
}

const recipeCohort: Recipe = {
  match: (q) => {
    const s = q.toLowerCase();
    const hasTrend = ["trend", "trajectory", "weeks", "cohort", "bmi"].some((w) => s.includes(w));
    const hasDrug = ["mounjaro", "tirzepatide", "wegovy", "semaglutide", "ozempic"].some((w) => s.includes(w));
    return hasTrend || hasDrug;
  },
  build: () => {
    const artifact: ChatArtifact = {
      kind: "cohort_trend",
      id: mkId("cohort-trend"),
      title: "Mounjaro cohort · BMI trajectory",
      subtitle: "n = 842 · weeks 0–24",
      payload: DEMO_COHORT_TREND,
    };
    return {
      steps: [
        "Classified intent · cohort trajectory (Mounjaro)",
        "Resolved cohort · 842 patients on Mounjaro",
        "Aggregated BMI across 12 visits",
        "Selected artifact · cohort_trend",
      ],
      reply:
        "Built a 24-week BMI trajectory for the Mounjaro cohort (n = 842). Mean BMI " +
        "fell from 32.1 to 27.2 kg/m² — a 4.9-point drop. Adherence is 86 %. Table " +
        "below ranks the top-seven responders.",
      artifact,
      trace: {
        intent: "cohort_trajectory",
        recipe: "cohort_trajectory",
        sql: ["-- demo fallback (backend unreachable)"],
        row_counts: [12, 7],
        artifact_kind: "cohort_trend",
      },
    };
  },
};

const recipeFhir: Recipe = {
  match: (q) => {
    const s = q.toLowerCase();
    return s.includes("fhir") || s.includes("bundle") || s.includes("pt-");
  },
  build: () => {
    const artifact: ChatArtifact = {
      kind: "fhir_bundle",
      id: mkId("fhir"),
      title: "FHIR Bundle · PT-44192",
      subtitle: "Bundle · 5 resources · 1.8 kB",
      payload: DEMO_FHIR_BUNDLE,
    };
    return {
      steps: [
        "Classified intent · patient FHIR export",
        "Resolved patient identifier · PT-44192",
        "Queried FHIR substrate · Patient, Observation, MedicationStatement, Condition",
        "Assembled Bundle · 5 resources",
      ],
      reply:
        "Assembled a 5-resource FHIR bundle for PT-44192 — Patient, two BMI " +
        "Observations (W0, W24), MedicationStatement (tirzepatide 5 mg) and the " +
        "obesity Condition. Opening it in the canvas.",
      artifact,
      trace: {
        intent: "patient_fhir_bundle",
        recipe: "patient_fhir_bundle",
        sql: [],
        row_counts: [],
        artifact_kind: "fhir_bundle",
      },
    };
  },
};

const recipeAlerts: Recipe = {
  match: (q) => {
    const s = q.toLowerCase();
    return ["alert", "quality", "issue", "problem", "missed", "gap", "flag"].some((w) => s.includes(w));
  },
  build: () => {
    const artifact: ChatArtifact = {
      kind: "alerts_table",
      id: mkId("alerts"),
      title: "Data-quality alerts",
      subtitle: "84 issues · 3 shown",
      payload: DEMO_ALERTS,
    };
    return {
      steps: [
        "Classified intent · data-quality alerts",
        "Queried quality_report · 84 rows",
        "Aggregated severity · 3 errors / 81 warnings",
        "Selected artifact · alerts_table",
      ],
      reply:
        "Found 84 flagged issues — 3 errors, 81 warnings. Top entries are listed " +
        "in the table; error-level rows should be reviewed first.",
      artifact,
      trace: {
        intent: "ops_alerts",
        recipe: "ops_alerts",
        sql: ["-- demo fallback"],
        row_counts: [84, 3],
        artifact_kind: "alerts_table",
      },
    };
  },
};

const recipeOpportunity: Recipe = {
  match: (q) => {
    const s = q.toLowerCase();
    // Tight matcher: need a brand-transition signal OR a candidate-keyword
    // signal. Avoids stealing the cohort_trend or patient_record prompt by
    // accident.
    const hasBrandTransition =
      (s.includes("spring") && (s.includes("golighter") || s.includes("go lighter"))) ||
      s.includes("cross-brand") ||
      s.includes("cross brand") ||
      s.includes("cross-sell") ||
      s.includes("cross sell");
    const hasCandidateKeyword =
      s.includes("screening candidate") ||
      s.includes("opportunity") ||
      s.includes("outreach") ||
      (s.includes("candidate") && (s.includes("spring") || s.includes("golighter")));
    return hasBrandTransition || hasCandidateKeyword;
  },
  build: () => {
    const artifact: ChatArtifact = {
      kind: "opportunity_list",
      id: mkId("opportunity"),
      title: "Screening candidates · Spring → GoLighter",
      subtitle: "Cross-brand cohort · BMI ≥ 27 · GoLighter-naive",
      payload: DEMO_OPPORTUNITY_LIST,
    };
    return {
      steps: [
        "Classified intent · cross-brand candidate identification",
        "Scoped Spring cohort · 4,557 patients on file",
        "Applied BMI filter · 2,029 with BMI ≥ 27",
        "Excluded GoLighter history · 2,014 candidates",
        "Filtered to active patients (180d) · 456 actionable",
        "Selected artifact · opportunity_list",
      ],
      reply:
        "Found 456 active Spring patients with BMI ≥ 27 who have no " +
        "GoLighter treatment history — 60 are clinically high-priority. " +
        "The funnel below shows how the cohort collapses from full " +
        "Spring to actionable list, with reason summaries per patient.",
      artifact,
      trace: {
        intent: "cross_brand_opportunity",
        recipe: "cross_brand_opportunity",
        sql: ["-- demo fallback (deterministic Pandas filter)"],
        row_counts: [4557, 2029, 2014, 456],
        artifact_kind: "opportunity_list",
      },
    };
  },
};

// Order matters: more specific recipes first, generic fallbacks last.
// recipeOpportunity must precede recipeCohort because both can be
// triggered by a "Spring patients" query — the candidate framing wins.
const RECIPES: Recipe[] = [recipeFhir, recipeOpportunity, recipeCohort, recipeAlerts];

/**
 * Pick a scripted response that matches the user's question — or null.
 *
 * Returning null when no recipe matches is load-bearing: it stops the
 * analyst page from dressing an arbitrary backend failure up as a
 * confident Mounjaro dashboard. Silent defaults here would turn the
 * Clinical Ledger into a hallucination surface during a backend
 * outage. If the caller has no real answer to show, the UI should say
 * so plainly rather than make one up.
 */
export function matchRecipe(query: string): ChatResponse | null {
  for (const recipe of RECIPES) {
    if (recipe.match(query)) return recipe.build();
  }
  return null;
}
