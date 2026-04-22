"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

/**
 * Platform surface — `/platform`.
 *
 * The pitch's closing beat: "the analyst is one application; here are
 * the endpoints anyone else can build on top of". Three real API
 * samples with live "Run" buttons that hit the BFF and pretty-print
 * the response inline.
 *
 * Deliberately minimal — no Swagger, no OpenAPI tree. For a pitch,
 * three well-chosen examples communicate "you have a platform" far
 * better than a 400-line auto-generated spec.
 */

interface EndpointDef {
  id: string;
  method: "GET" | "POST";
  path: string;
  title: string;
  sub: string;
  /** cURL shown in the code block */
  curl: string;
  /**
   * Actually invoke via the BFF. Returns whatever JSON the live API
   * gives back, which we pretty-print below.
   */
  run: () => Promise<unknown>;
}

const ENDPOINTS: EndpointDef[] = [
  {
    id: "mapping",
    method: "GET",
    path: "/v1/mapping",
    title: "Semantic mapping",
    sub: "Every discovered category with its FHIR resource and code.",
    curl: `curl https://api.uniq.health/v1/mapping \\
  -H "Authorization: Bearer $UNIQ_TOKEN"`,
    run: async () => {
      const res = await fetch("/api/uniq/mapping");
      if (!res.ok) throw new Error(`${res.status}`);
      const body = await res.json();
      // Trim to first 3 entries for readable response preview.
      return Array.isArray(body) ? body.slice(0, 3) : body;
    },
  },
  {
    id: "fhir",
    method: "GET",
    path: "/v1/export/{user_id}/fhir",
    title: "Patient FHIR bundle",
    sub: "A full FHIR R4 bundle — patient, observations, medications.",
    curl: `curl https://api.uniq.health/v1/export/381119/fhir \\
  -H "Authorization: Bearer $UNIQ_TOKEN"`,
    run: async () => {
      const res = await fetch("/api/uniq/export/381119/fhir");
      if (!res.ok) throw new Error(`${res.status}`);
      const bundle = await res.json();
      // Trim entry list so the preview stays scannable.
      if (bundle?.entry && Array.isArray(bundle.entry)) {
        return {
          ...bundle,
          entry: bundle.entry.slice(0, 3),
          _note: `${bundle.entry.length} total entries — showing first 3`,
        };
      }
      return bundle;
    },
  },
  {
    id: "chat",
    method: "POST",
    path: "/v1/chat",
    title: "Analyst chat",
    sub: "Natural-language question → validated artifact + prose.",
    curl: `curl https://api.uniq.health/v1/chat \\
  -H "Authorization: Bearer $UNIQ_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{"message": "How many female patients do we have?"}'`,
    run: async () => {
      const res = await fetch("/api/uniq/chat", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ message: "How many female patients do we have?" }),
      });
      if (!res.ok) throw new Error(`${res.status}`);
      const body = (await res.json()) as {
        steps?: string[];
        reply?: string;
        trace?: { artifact_kind?: string; sql?: string[] };
        artifact?: { kind?: string; title?: string };
      };
      // Surface the interesting fields, not the whole payload.
      return {
        reply: body.reply,
        artifact: body.artifact
          ? { kind: body.artifact.kind, title: body.artifact.title }
          : null,
        trace: {
          artifact_kind: body.trace?.artifact_kind,
          sql_queries: body.trace?.sql?.length ?? 0,
        },
      };
    },
  },
];

type RunState =
  | { kind: "idle" }
  | { kind: "running" }
  | { kind: "ok"; response: unknown; ms: number }
  | { kind: "error"; message: string; ms: number };

export default function PlatformPage() {
  return (
    <Suspense fallback={<PlatformShell />}>
      <PlatformInner />
    </Suspense>
  );
}

function PlatformShell() {
  return (
    <div className="room" data-screen-label="Platform">
      <div className="platform" />
    </div>
  );
}

type View = "api" | "agents";

function PlatformInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const view: View = searchParams?.get("view") === "agents" ? "agents" : "api";

  const setView = (v: View) => {
    const params = new URLSearchParams(searchParams?.toString() ?? "");
    if (v === "api") params.delete("view");
    else params.set("view", v);
    const qs = params.toString();
    router.replace(`/platform${qs ? `?${qs}` : ""}`, { scroll: false });
  };

  return (
    <div className="room" data-screen-label="Platform">
      <div className="platform">
        <header className="platform__head">
          <h1 className="platform__title">
            Build on <em>UniQ</em>
          </h1>
          <p className="platform__sub">
            UniQ is a trusted clinical data substrate with human sign-off,
            FHIR interoperability, and developer APIs. The analyst is the
            first app built on it — you can build your own.
          </p>
        </header>

        <nav className="platform__tabs" role="tablist" aria-label="Platform surface">
          <button
            role="tab"
            aria-selected={view === "api"}
            className="platform__tab"
            onClick={() => setView("api")}
          >
            API
          </button>
          <button
            role="tab"
            aria-selected={view === "agents"}
            className="platform__tab"
            onClick={() => setView("agents")}
          >
            Agents
            <span className="platform__tab-badge">preview</span>
          </button>
        </nav>

        {view === "api" ? <ApiView /> : <AgentsView />}
      </div>
    </div>
  );
}

function ApiView() {
  return (
    <>
      {/* ─── Auth + versioning strip ──────────────────────────── */}
        <section className="platform__strip" aria-label="API conventions">
          <div className="platform__strip-item">
            <span className="platform__strip-label">Auth</span>
            <span className="platform__strip-value">
              <code>Authorization: Bearer &lt;token&gt;</code>
            </span>
          </div>
          <div className="platform__strip-item">
            <span className="platform__strip-label">Base</span>
            <span className="platform__strip-value">
              <code>https://api.uniq.health/v1</code>
            </span>
          </div>
          <div className="platform__strip-item">
            <span className="platform__strip-label">Writes</span>
            <span className="platform__strip-value">
              read-only by default · writes gated by clinician review
            </span>
          </div>
        </section>

        {/* ─── Resource map ─────────────────────────────────────── */}
        <section className="platform__resources" aria-label="Resource map">
          <div className="platform__section-head">
            <h2 className="platform__section-title">Resources</h2>
            <span className="platform__section-sub">
              Primitives and packaged services grouped by domain
            </span>
          </div>
          <div className="resource-map">
            <div className="resource-map__column">
              <div className="resource-map__column-label">Available now</div>
              <ul className="resource-map__list">
                <ResourceItem
                  name="Mappings"
                  detail="semantic vocabulary"
                  paths={["GET /v1/mapping", "GET /v1/mapping/{category}"]}
                  live
                />
                <ResourceItem
                  name="Patients"
                  detail="demographics · BMI · medication history"
                  paths={["GET /v1/patients/{id}"]}
                  live
                />
                <ResourceItem
                  name="FHIR export"
                  detail="R4 bundles per patient"
                  paths={["GET /v1/export/{id}/fhir"]}
                  live
                />
                <ResourceItem
                  name="Analyst"
                  detail="natural-language queries → validated artifacts"
                  paths={["POST /v1/chat"]}
                  live
                />
              </ul>
            </div>
            <div className="resource-map__column">
              <div className="resource-map__column-label">Next</div>
              <ul className="resource-map__list">
                <ResourceItem
                  name="Observations"
                  detail="BMI timeline · vitals · labs"
                  paths={["GET /v1/patients/{id}/observations"]}
                />
                <ResourceItem
                  name="Cohorts"
                  detail="define and query patient groups"
                  paths={["POST /v1/cohorts", "GET /v1/cohorts/{id}/members"]}
                />
                <ResourceItem
                  name="Async ingest"
                  detail="upload pipelines · job status"
                  paths={["POST /v1/ingest/jobs"]}
                />
                <ResourceItem
                  name="Webhooks"
                  detail={[
                    "mapping.approved",
                    "ingest.completed",
                    "quality.flagged",
                  ].join(" · ")}
                  paths={["POST /v1/webhooks"]}
                />
              </ul>
            </div>
          </div>
        </section>

        {/* ─── Live examples (kept from proof-of-platform v1) ────── */}
        <section className="platform__examples" aria-label="Live examples">
          <div className="platform__section-head">
            <h2 className="platform__section-title">Try it live</h2>
            <span className="platform__section-sub">
              These three calls hit the substrate in real time
            </span>
          </div>
          <div className="platform__grid">
            {ENDPOINTS.map((ep) => (
              <EndpointCard key={ep.id} ep={ep} />
            ))}
          </div>
        </section>

        {/* ─── What teams build ─────────────────────────────────── */}
        <section className="platform__usecases" aria-label="Use cases">
          <div className="platform__section-head">
            <h2 className="platform__section-title">What teams build on UniQ</h2>
          </div>
          <div className="usecase-grid">
            <UseCaseCard
              title="Cohort analytics"
              body="Patient groups defined, tracked, and exported for clinical-research workflows."
              uses="Cohorts · Observations · FHIR export"
            />
            <UseCaseCard
              title="In-EHR timelines"
              body="Embedded patient timelines inside Epic / Cerner / custom EHRs via FHIR bundles."
              uses="Patients · FHIR export · Webhooks"
            />
            <UseCaseCard
              title="Custom clinical copilots"
              body="Domain-specific assistants for weight management, diabetes, or trial screening."
              uses="Analyst · Mappings · Python SDK"
            />
          </div>
        </section>

        <footer className="platform__foot">
          <span className="t-meta">
            All endpoints are read-only in this preview. Writes go through
            the clinician review flow and require an authenticated sign-off.
            SDKs for Python and TypeScript are in active development.
          </span>
        </footer>
    </>
  );
}

// ─── Agents tab ──────────────────────────────────────────────

const ALL_RESOURCES = [
  "patients",
  "mappings",
  "fhir_export",
  "observations",
  "medications",
  "quality_flags",
] as const;

const ALL_TOOLS = [
  "execute_sql",
  "sample_rows",
  "build_fhir_bundle",
  "present_cohort_trend",
  "present_alerts_table",
  "present_table",
  "present_fhir_bundle",
] as const;

const ALL_ARTIFACTS = [
  "cohort_trend",
  "alerts_table",
  "table",
  "fhir_bundle",
] as const;

const REVIEW_POLICIES = [
  "read_only",
  "gated",
  "clinician_signoff",
  "patient_facing",
] as const;

type Resource = (typeof ALL_RESOURCES)[number];
type Tool = (typeof ALL_TOOLS)[number];
type Artifact = (typeof ALL_ARTIFACTS)[number];
type ReviewPolicy = (typeof REVIEW_POLICIES)[number];

interface AgentConfig {
  name: string;
  instruction: string;
  resources: Resource[];
  tools: Tool[];
  artifacts: Artifact[];
  review_policy: ReviewPolicy;
}

interface BlueprintDef {
  id: string;
  title: string;
  pitch: string;
  config: AgentConfig;
}

const BLUEPRINTS: BlueprintDef[] = [
  {
    id: "analyst",
    title: "UniQ Analyst",
    pitch: "The built-in, general-purpose clinical analyst. Shipped with the platform — every other blueprint is a fork.",
    config: {
      name: "uniq_analyst",
      instruction:
        "You are the UniQ Analyst — a clinical data agent grounded in a validated substrate with clinician-reviewed mappings.",
      resources: ["patients", "mappings", "fhir_export"],
      tools: [
        "execute_sql",
        "sample_rows",
        "build_fhir_bundle",
        "present_cohort_trend",
        "present_alerts_table",
        "present_table",
        "present_fhir_bundle",
      ],
      artifacts: ["cohort_trend", "alerts_table", "table", "fhir_bundle"],
      review_policy: "read_only",
    },
  },
  {
    id: "weight_loss",
    title: "Weight-loss coach",
    pitch: "Patient-facing copilot for GLP-1 programmes. Answers BMI-trajectory questions, flags plateau weeks, surfaces adherence gaps.",
    config: {
      name: "weight_loss_coach",
      instruction:
        "You are a supportive weight-loss coach focused on BMI trajectory and medication adherence.",
      resources: ["patients", "observations", "medications"],
      tools: ["execute_sql", "present_cohort_trend", "present_table"],
      artifacts: ["cohort_trend", "table"],
      review_policy: "patient_facing",
    },
  },
  {
    id: "trial_recruiter",
    title: "Trial recruiter",
    pitch: "Cohort-eligibility screening for clinical trials. Builds candidate lists from inclusion/exclusion criteria against the substrate.",
    config: {
      name: "trial_recruiter",
      instruction:
        "You identify patients eligible for a given trial from inclusion/exclusion criteria.",
      resources: ["patients", "observations", "medications", "mappings"],
      tools: ["execute_sql", "present_table", "build_fhir_bundle"],
      artifacts: ["table", "fhir_bundle"],
      review_policy: "gated",
    },
  },
  {
    id: "care_pathway",
    title: "Care-pathway optimizer",
    pitch: "Flags deviations from clinical protocol, surfaces missing reviews, suggests next-step escalations. Used by care-management teams.",
    config: {
      name: "care_pathway_optimizer",
      instruction:
        "You monitor care-pathway adherence and surface protocol deviations.",
      resources: ["patients", "observations", "quality_flags"],
      tools: ["execute_sql", "present_alerts_table", "present_table"],
      artifacts: ["alerts_table", "table"],
      review_policy: "clinician_signoff",
    },
  },
];

function configToJson(c: AgentConfig): string {
  return JSON.stringify(
    {
      name: c.name,
      resources: c.resources,
      tools: c.tools,
      artifacts: c.artifacts,
      review_policy: c.review_policy,
      instruction: c.instruction,
    },
    null,
    2,
  );
}

function toggleIn<T extends string>(set: readonly T[], item: T): T[] {
  return set.includes(item)
    ? set.filter((x) => x !== item)
    : [...set, item];
}

function AgentsView() {
  const [presetId, setPresetId] = useState<string>("analyst");
  const [config, setConfig] = useState<AgentConfig>(BLUEPRINTS[0].config);

  const applyPreset = (id: string) => {
    const bp = BLUEPRINTS.find((b) => b.id === id);
    if (!bp) return;
    setPresetId(id);
    setConfig(bp.config);
  };

  const toggleResource = (r: Resource) =>
    setConfig((c) => ({ ...c, resources: toggleIn(c.resources, r) }));
  const toggleTool = (t: Tool) =>
    setConfig((c) => ({ ...c, tools: toggleIn(c.tools, t) }));
  const toggleArtifact = (a: Artifact) =>
    setConfig((c) => ({ ...c, artifacts: toggleIn(c.artifacts, a) }));
  const setPolicy = (p: ReviewPolicy) =>
    setConfig((c) => ({ ...c, review_policy: p }));

  return (
    <>
      {/* Hero with preview badge */}
      <section className="agents__hero" aria-label="Agents introduction">
        <div className="agents__hero-body">
          <div className="agents__hero-label">Agents · Preview</div>
          <h2 className="agents__hero-title">
            Custom clinical agents <em>on shared substrate</em>
          </h2>
          <p className="agents__hero-sub">
            Configurable agents with validated tools, template-bound outputs,
            and clinician sign-off gates. Every agent inherits the same
            substrate and the same guardrails — the difference is the
            intent.
          </p>
        </div>
        <div className="agents__hero-cta">
          <span className="agents__cta-label">Configuration API preview</span>
          <span className="agents__cta-meta">
            Partner for early access — today only via our team.
          </span>
        </div>
      </section>

      {/* Interactive configurator: preset chips → toggleable spec ↔ live JSON */}
      <section className="agents__configurator" aria-label="Agent configurator">
        <div className="platform__section-head">
          <h2 className="platform__section-title">
            Configure an agent
          </h2>
          <span className="platform__section-sub">
            Start from a blueprint · toggle to scope · read the spec live
          </span>
        </div>

        <div className="preset-row" role="tablist" aria-label="Blueprint presets">
          {BLUEPRINTS.map((bp) => (
            <button
              key={bp.id}
              role="tab"
              aria-selected={presetId === bp.id}
              className="preset-chip"
              onClick={() => applyPreset(bp.id)}
            >
              <span className="preset-chip__title">{bp.title}</span>
              <span className="preset-chip__pitch">{PRESET_ONE_LINER[bp.id]}</span>
            </button>
          ))}
        </div>

        <div className="configurator">
          <div className="configurator__form">
            <ConfigSection label="Resources" description="Substrate primitives the agent can read">
              <div className="pill-row">
                {ALL_RESOURCES.map((r) => (
                  <PillToggle
                    key={r}
                    label={r}
                    active={config.resources.includes(r)}
                    onClick={() => toggleResource(r)}
                  />
                ))}
              </div>
            </ConfigSection>

            <ConfigSection label="Tools" description="Validated callables — backend guards every arg">
              <div className="pill-row">
                {ALL_TOOLS.map((t) => (
                  <PillToggle
                    key={t}
                    label={t}
                    active={config.tools.includes(t)}
                    onClick={() => toggleTool(t)}
                  />
                ))}
              </div>
            </ConfigSection>

            <ConfigSection label="Artifacts" description="Allowed output templates — Pydantic-validated">
              <div className="pill-row">
                {ALL_ARTIFACTS.map((a) => (
                  <PillToggle
                    key={a}
                    label={a}
                    active={config.artifacts.includes(a)}
                    onClick={() => toggleArtifact(a)}
                  />
                ))}
              </div>
            </ConfigSection>

            <ConfigSection label="Review policy" description="Gating for state-changing actions">
              <div className="policy-row" role="radiogroup">
                {REVIEW_POLICIES.map((p) => (
                  <button
                    key={p}
                    role="radio"
                    aria-checked={config.review_policy === p}
                    className="policy-pill"
                    onClick={() => setPolicy(p)}
                  >
                    {p}
                  </button>
                ))}
              </div>
            </ConfigSection>

            <ConfigSection label="Instruction" description="System-prompt fragment that shapes the agent's voice">
              <div className="instruction-block">{config.instruction}</div>
            </ConfigSection>
          </div>

          <div className="configurator__spec">
            <div className="configurator__spec-head">
              <span>{config.name}.json</span>
              <span className="configurator__spec-meta">live preview</span>
            </div>
            <pre className="configurator__spec-code">{configToJson(config)}</pre>
          </div>
        </div>

        <div className="configurator__foot">
          <span className="t-meta">
            This is a preview of the configuration shape — no live deploy.
            Pydantic-validated spec feeds the same Claude tool-loop the
            UniQ Analyst runs on.
          </span>
        </div>
      </section>

      <footer className="platform__foot">
        <span className="t-meta">
          Every agent runs on the same validated substrate and inherits the
          same tool-guards, artifact templates, and review policies. The
          configuration API is in preview — early-access partners get
          hands-on support from our team.
        </span>
      </footer>
    </>
  );
}

const PRESET_ONE_LINER: Record<string, string> = {
  analyst: "General-purpose clinical analyst",
  weight_loss: "Patient-facing GLP-1 copilot",
  trial_recruiter: "Cohort-eligibility screening",
  care_pathway: "Protocol-deviation alerts",
};

function ConfigSection({
  label,
  description,
  children,
}: {
  label: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <div className="config-section">
      <div className="config-section__head">
        <span className="config-section__label">{label}</span>
        <span className="config-section__desc">{description}</span>
      </div>
      {children}
    </div>
  );
}

function PillToggle({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className="pill"
      data-active={active ? "true" : "false"}
      onClick={onClick}
    >
      <span className="pill__dot" aria-hidden="true" />
      <span className="pill__label">{label}</span>
    </button>
  );
}


function ResourceItem({
  name,
  detail,
  paths,
  live,
}: {
  name: string;
  detail: string;
  paths: string[];
  live?: boolean;
}) {
  return (
    <li className="resource-item" data-live={live ? "true" : "false"}>
      <div className="resource-item__head">
        <span className="resource-item__dot" aria-hidden="true" />
        <span className="resource-item__name">{name}</span>
        <span className="resource-item__state">
          {live ? "live" : "planned"}
        </span>
      </div>
      <div className="resource-item__detail">{detail}</div>
      <div className="resource-item__paths">
        {paths.map((p) => (
          <code key={p}>{p}</code>
        ))}
      </div>
    </li>
  );
}

function UseCaseCard({
  title,
  body,
  uses,
}: {
  title: string;
  body: string;
  uses: string;
}) {
  return (
    <article className="usecase-card">
      <div className="usecase-card__title">{title}</div>
      <div className="usecase-card__body">{body}</div>
      <div className="usecase-card__uses">
        <span className="usecase-card__uses-label">Uses</span> {uses}
      </div>
    </article>
  );
}

function EndpointCard({ ep }: { ep: EndpointDef }) {
  const [state, setState] = useState<RunState>({ kind: "idle" });

  const run = async () => {
    setState({ kind: "running" });
    const start = performance.now();
    try {
      const response = await ep.run();
      setState({
        kind: "ok",
        response,
        ms: Math.round(performance.now() - start),
      });
    } catch (err) {
      setState({
        kind: "error",
        message: err instanceof Error ? err.message : String(err),
        ms: Math.round(performance.now() - start),
      });
    }
  };

  return (
    <article className="endpoint-card">
      <div className="endpoint-card__meta">
        <span className={`endpoint-card__method endpoint-card__method--${ep.method.toLowerCase()}`}>
          {ep.method}
        </span>
        <span className="endpoint-card__path">{ep.path}</span>
      </div>
      <div className="endpoint-card__title">{ep.title}</div>
      <div className="endpoint-card__sub">{ep.sub}</div>

      <pre className="endpoint-card__snippet">{ep.curl}</pre>

      <div className="endpoint-card__run-row">
        <button
          type="button"
          className="endpoint-card__run"
          onClick={run}
          disabled={state.kind === "running"}
        >
          {state.kind === "running" ? "Running…" : "Run live →"}
        </button>
        {state.kind === "ok" && (
          <span className="endpoint-card__status endpoint-card__status--ok">
            200 · {state.ms} ms
          </span>
        )}
        {state.kind === "error" && (
          <span className="endpoint-card__status endpoint-card__status--err">
            error · {state.message}
          </span>
        )}
      </div>

      {state.kind === "ok" && (
        <pre className="endpoint-card__response">
          {JSON.stringify(state.response, null, 2)}
        </pre>
      )}
    </article>
  );
}
