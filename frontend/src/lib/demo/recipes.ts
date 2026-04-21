/**
 * Demo recipes for the Analyst.
 *
 * Until Phase 6 wires the real DuckDB-backed agent, the Analyst runs a
 * scripted flow: user types a question, a pre-written plan of steps
 * plays, a pre-written reply gets typed, and one of the two demo
 * artifacts below materialises. The matcher is keyword-based — only
 * "fhir/bundle/PT-*" routes to the FHIR artifact, everything else
 * lands on the dashboard.
 *
 * Phase 6 swaps `matchRecipe` for a backend call. The artifact shapes
 * (DashboardPayload / FhirPayload) are the contract the real agent
 * has to populate — that's why they live here as separate types
 * rather than inside the UI components.
 */

export type ArtifactKind = "dashboard" | "fhir";

export interface ArtifactDescriptor {
  id: string;
  kind: ArtifactKind;
  title: string;
  subtitle: string;
}

export interface PromptSuggestion {
  meta: string;
  text: string;
}

export interface DemoRecipe {
  steps: string[];
  reply: string;
  artifact: ArtifactDescriptor;
}

// The eight prompt chips shown in the empty state. First two are the
// canonical pitch prompts (cohort dashboard and FHIR export); the rest
// expand the surface so the jury believes the range.
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

function buildDashboardArtifact(): ArtifactDescriptor {
  return {
    id: `dash-${Date.now()}`,
    kind: "dashboard",
    title: "Mounjaro cohort · BMI trajectory",
    subtitle: "Dashboard · n = 842 · window 24w",
  };
}

function buildFhirArtifact(): ArtifactDescriptor {
  return {
    id: `fhir-${Date.now()}`,
    kind: "fhir",
    title: "FHIR Bundle · PT-44192",
    subtitle: "Bundle · 5 resources · 1.8 kB",
  };
}

function routeKind(query: string): ArtifactKind {
  const s = query.toLowerCase();
  if (s.includes("fhir") || s.includes("bundle") || s.includes("pt-")) {
    return "fhir";
  }
  return "dashboard";
}

const FHIR_STEPS = [
  "Resolve patient identifier · PT-44192",
  "Query FHIR substrate · Patient, Observation, MedicationStatement, Condition",
  "Assemble Bundle · type=collection",
  "Validate against FHIR R4 schema",
];

const DASHBOARD_STEPS = [
  "Resolve cohort · patients with rx_tirzepatide = true",
  "Pull BMI observations · LOINC 39156-5 · weeks 0 – 24",
  "Compute mean trajectory and adherence deltas",
  "Render dashboard with top-7 patient table",
];

const FHIR_REPLY =
  "Assembled a 5-resource FHIR bundle for PT-44192 — Patient, two BMI " +
  "Observations (W0, W24), MedicationStatement (tirzepatide 5 mg) and the " +
  "obesity Condition. Opening it in the canvas.";

const DASHBOARD_REPLY =
  "Built a 24-week BMI trajectory for the Mounjaro cohort (n = 842). Mean " +
  "fell from 32.1 to 27.2 kg/m² — a 4.9-point drop. Adherence is 86%, soft " +
  "downward week-on-week. Table below ranks the top-seven responders. " +
  "Dashboard is open on the right.";

/** Match a free-form query to the demo recipe that should respond. */
export function matchRecipe(query: string): DemoRecipe {
  const kind = routeKind(query);
  if (kind === "fhir") {
    return {
      steps: FHIR_STEPS,
      reply: FHIR_REPLY,
      artifact: buildFhirArtifact(),
    };
  }
  return {
    steps: DASHBOARD_STEPS,
    reply: DASHBOARD_REPLY,
    artifact: buildDashboardArtifact(),
  };
}

// Payloads that the renderers bind to. Hardcoded for the demo; Phase 6
// populates these from query results.

export interface DashboardKpi {
  label: string;
  value: string;
  delta: string;
  deltaDirection?: "up" | "down";
}

export interface DashboardCohortRow {
  patient: string;
  dose: string;
  bmiBaseline: number;
  bmiLatest: number;
  delta: number;
  adherence: string;
}

export interface DashboardPayload {
  kpis: DashboardKpi[];
  trajectoryPoints: number[]; // BMI per week, length 12 (W0..W22 by 2)
  cohortTable: DashboardCohortRow[];
}

export const DEMO_DASHBOARD: DashboardPayload = {
  kpis: [
    { label: "Cohort · Mounjaro", value: "842", delta: "+ 37 past 30d" },
    { label: "Mean BMI · baseline", value: "32.1", delta: "n = 842" },
    { label: "Mean BMI · 24w", value: "27.2", delta: "− 4.9 pts" },
    {
      label: "Adherence",
      value: "86%",
      delta: "− 2 pts WoW",
      deltaDirection: "down",
    },
  ],
  trajectoryPoints: [
    32.1, 31.8, 31.2, 30.7, 30.1, 29.8, 29.3, 28.7, 28.2, 27.9, 27.5, 27.2,
  ],
  cohortTable: [
    { patient: "PT-44192", dose: "5 mg", bmiBaseline: 33.4, bmiLatest: 27.8, delta: -5.6, adherence: "94%" },
    { patient: "PT-40823", dose: "2.5 mg", bmiBaseline: 31.1, bmiLatest: 27.9, delta: -3.2, adherence: "81%" },
    { patient: "PT-51108", dose: "10 mg", bmiBaseline: 35.6, bmiLatest: 28.2, delta: -7.4, adherence: "88%" },
    { patient: "PT-39004", dose: "5 mg", bmiBaseline: 30.8, bmiLatest: 26.9, delta: -3.9, adherence: "91%" },
    { patient: "PT-48715", dose: "7.5 mg", bmiBaseline: 34.0, bmiLatest: 28.4, delta: -5.6, adherence: "84%" },
    { patient: "PT-42290", dose: "5 mg", bmiBaseline: 32.2, bmiLatest: 27.0, delta: -5.2, adherence: "90%" },
    { patient: "PT-50331", dose: "2.5 mg", bmiBaseline: 29.7, bmiLatest: 27.4, delta: -2.3, adherence: "76%" },
  ],
};

export interface FhirBundlePayload {
  resourceType: "Bundle";
  id: string;
  type: string;
  timestamp: string;
  entry: Array<{ resource: Record<string, unknown> }>;
}

export const DEMO_FHIR_BUNDLE: FhirBundlePayload = {
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
        code: {
          coding: [{ system: "LOINC", code: "39156-5", display: "BMI" }],
        },
        valueQuantity: { value: 33.4, unit: "kg/m2" },
        effectiveDateTime: "2025-10-12",
      },
    },
    {
      resource: {
        resourceType: "Observation",
        code: {
          coding: [{ system: "LOINC", code: "39156-5", display: "BMI" }],
        },
        valueQuantity: { value: 27.8, unit: "kg/m2" },
        effectiveDateTime: "2026-04-04",
      },
    },
    {
      resource: {
        resourceType: "MedicationStatement",
        medication: {
          coding: [
            {
              system: "RxNorm",
              code: "2601723",
              display: "tirzepatide 5 MG",
            },
          ],
        },
        status: "active",
      },
    },
    {
      resource: {
        resourceType: "Condition",
        code: {
          coding: [
            {
              system: "ICD-10",
              code: "E66.9",
              display: "Obesity, unspecified",
            },
          ],
        },
      },
    },
  ],
};
