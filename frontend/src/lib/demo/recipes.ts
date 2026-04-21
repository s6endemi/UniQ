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
} from "@/lib/api";

export interface PromptSuggestion {
  meta: string;
  text: string;
}

export const PROMPT_SUGGESTIONS: PromptSuggestion[] = [
  {
    meta: "Cohort · trend",
    text: "Show BMI trends for Mounjaro patients over the past 24 weeks",
  },
  {
    meta: "Adherence",
    text: "Which patients have missed more than two weekly doses?",
  },
  {
    meta: "FHIR export",
    text: "Generate a FHIR bundle for patient PT-44192",
  },
  {
    meta: "Cross-cohort",
    text: "Compare HbA1c change between Ozempic and Mounjaro",
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

const RECIPES: Recipe[] = [recipeFhir, recipeCohort, recipeAlerts];

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
