"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import type {
  HealthResponse,
  SubstrateAuditEvent,
  SubstrateManifestResponse,
  SubstrateResource,
} from "@/lib/api";

/**
 * Substrate-Ready Transition — `/substrate-ready`.
 *
 * Not a navigational page; only reachable from the guided intake flow
 * (Review → approve → redirect). If a visitor lands here out-of-flow
 * we fall back to an onboarding hint instead of pretending the demo
 * just completed.
 *
 * Three visual beats in sequence:
 *   1 · headline (`UniQ Substrate · ready`) materialises
 *   2 · live metrics from /health + a small preview table
 *   3 · three unlock cards reframing Analyst / FHIR / API as
 *       consequences of the substrate, not as the product itself
 */

export default function SubstrateReadyPage() {
  return (
    <Suspense fallback={<Shell />}>
      <SubstrateReadyInner />
    </Suspense>
  );
}

function Shell({ children }: { children?: React.ReactNode }) {
  return (
    <div className="room" data-screen-label="Substrate ready">
      <div className="substrate-ready">{children}</div>
    </div>
  );
}

async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch("/api/uniq/health");
  if (!res.ok) throw new Error(`health ${res.status}`);
  return res.json();
}

async function fetchManifest(): Promise<SubstrateManifestResponse> {
  const res = await fetch("/api/uniq/substrate/manifest");
  if (!res.ok) throw new Error(`manifest ${res.status}`);
  return res.json();
}

function SubstrateReadyInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const fromReview = searchParams?.get("from") === "review";

  const { data: health } = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    staleTime: 60_000,
  });
  const { data: manifest } = useQuery({
    queryKey: ["substrate-manifest"],
    queryFn: fetchManifest,
    staleTime: 60_000,
  });

  // Enforce the earned-transition contract. Direct visitors (dev
  // copy-paste, stray deep link, nav attempt) get redirected to
  // /start so the guided flow is the only way into this view. Using
  // `replace` keeps the browser history clean — no orphaned
  // /substrate-ready entry the user can "back" into.
  useEffect(() => {
    if (!fromReview) {
      router.replace("/start");
    }
  }, [fromReview, router]);

  // Render a minimal hint while the redirect is in flight so direct
  // visitors don't catch a flash of the substrate state.
  if (!fromReview) {
    return (
      <div className="substrate-ready__inner" style={{ justifyContent: "center", minHeight: "60vh" }}>
        <p className="t-meta" style={{ textAlign: "center" }}>
          Redirecting to the intake flow…
        </p>
      </div>
    );
  }

  const patients = health?.patients ?? 5374;
  const categories = health?.categories ?? 20;
  const mappings = health?.mapping_entries ?? 20;
  // Quality-check total is not in /health today; a pinned value keeps
  // the pitch-predictable story intact. The number matches what the
  // quality_report table actually has for this dataset.
  const qualityChecks = 1031;
  const repository = manifest ?? fallbackManifest;

  return (
    <Shell>
      <div className="substrate-ready__inner">
        <div className="substrate-ready__rule" aria-hidden="true" />

        <header className="substrate-ready__head">
          <h1 className="substrate-ready__title">
            UniQ Substrate · <em>ready</em>
          </h1>
          <p className="substrate-ready__sub">
            Approval does not create a report. It materializes a clinical repository.
          </p>
        </header>

        <section className="substrate-metrics" aria-label="Substrate metrics">
          <MetricTile label="Patients"        target={patients}      delay={0}   />
          <MetricTile label="Categories"      target={categories}    delay={80}  />
          <MetricTile label="Mappings"        target={mappings}      delay={160} suffix={`/${mappings}`} />
          <MetricTile label="Quality checks"  target={qualityChecks} delay={240} />
        </section>

        <RepositoryMap manifest={repository} />

        <section className="unlock-cards" aria-label="What you can do now">
          <UnlockCard
            title="Ask with AI"
            body="Pose clinical questions in natural language. Get validated artifacts back."
            cta="Step 3 · Ask the analyst"
            href="/analyst"
            delay={2100}
            onClick={() => router.push("/analyst")}
          />
          <UnlockCard
            title="Export as FHIR"
            body="Generate FHIR R4 bundles for any patient. Downstream-system ready."
            cta="See a bundle"
            href="/analyst?prompt=fhir"
            delay={2220}
          />
          <UnlockCard
            title="Build via API"
            body="Query every resource through a documented, read-only endpoint."
            cta="Platform APIs"
            href="/platform"
            delay={2340}
          />
        </section>

        <footer className="substrate-ready__foot">
          <span className="t-meta">Guided demo · step 2 of 4 complete</span>
          <Link href="/analyst" className="substrate-ready__skip">
            Continue to analyst →
          </Link>
        </footer>
      </div>
    </Shell>
  );
}

const fallbackManifest: SubstrateManifestResponse = {
  version: "v1",
  headline: "Approval does not create a report. It materializes a clinical repository.",
  audit_events: [
    {
      label: "BMI_MEASUREMENT signed into substrate",
      detail: "LOINC 39156-5 attached · now queryable and FHIR-ready",
      status: "approved",
    },
  ],
  relationships: [
    "bmi_timeline",
    "medication_history",
    "treatment_episodes",
    "quality_report",
    "survey_unified",
    "fhir_bundle",
  ].map((name) => ({
    from_resource: name,
    to_resource: "patients",
    key: "user_id",
    label: "joins by user_id",
  })),
  resources: [
    {
      name: "patients",
      label: "Patients",
      row_count: 5374,
      primary_key: "user_id",
      foreign_keys: [],
      sample_fields: ["gender", "current_age", "current_medication", "latest_bmi"],
      status: "signed",
      api_hooks: ["GET /v1/patients", "GET /v1/patients/{id}"],
    },
    {
      name: "bmi_timeline",
      label: "BMI Timeline",
      row_count: 5705,
      primary_key: "user_id + date",
      foreign_keys: [{ target_resource: "patients", key: "user_id", label: "patient identity" }],
      sample_fields: ["date", "height_cm", "weight_kg", "bmi"],
      status: "queryable",
      api_hooks: ["GET /v1/observations?type=bmi"],
    },
    {
      name: "medication_history",
      label: "Medication History",
      row_count: 8835,
      primary_key: "user_id + started",
      foreign_keys: [{ target_resource: "patients", key: "user_id", label: "patient identity" }],
      sample_fields: ["product", "dosage", "started", "ended"],
      status: "queryable",
      api_hooks: ["GET /v1/patients/{id}/medications"],
    },
    {
      name: "treatment_episodes",
      label: "Treatment Episodes",
      row_count: 8835,
      primary_key: "treatment_id",
      foreign_keys: [{ target_resource: "patients", key: "user_id", label: "patient identity" }],
      sample_fields: ["product", "brand", "start_date", "latest_date"],
      status: "queryable",
      api_hooks: ["GET /v1/treatments/{id}"],
    },
    {
      name: "quality_report",
      label: "Quality Report",
      row_count: 1031,
      primary_key: "check_type + user_id",
      foreign_keys: [{ target_resource: "patients", key: "user_id", label: "patient identity" }],
      sample_fields: ["severity", "check_type", "description"],
      status: "monitored",
      api_hooks: ["GET /v1/quality/flags"],
    },
    {
      name: "survey_unified",
      label: "Survey Events",
      row_count: 133996,
      primary_key: "surrogate_key",
      foreign_keys: [{ target_resource: "patients", key: "user_id", label: "patient identity" }],
      sample_fields: ["clinical_category", "answer_canonical", "created_at"],
      status: "signed",
      api_hooks: ["GET /v1/patients/{id}/events"],
    },
    {
      name: "semantic_mapping",
      label: "Semantic Mapping",
      row_count: 20,
      primary_key: "clinical_category",
      foreign_keys: [],
      sample_fields: ["fhir_resource_type", "codes", "review_status"],
      status: "signed",
      api_hooks: ["GET /v1/mapping", "PATCH /v1/mapping/{category}"],
    },
    {
      name: "fhir_bundle",
      label: "FHIR Bundle",
      row_count: 5374,
      primary_key: "user_id",
      foreign_keys: [{ target_resource: "patients", key: "user_id", label: "patient identity" }],
      sample_fields: ["Patient", "Observation", "MedicationStatement"],
      status: "exportable",
      api_hooks: ["GET /v1/export/{id}/fhir"],
    },
  ],
};

// Per-resource consumer hints. Lives in the frontend (not the backend
// manifest) because it describes which UI surfaces and downstream
// integrations consume each resource — that is rendering knowledge,
// not substrate truth. Keeps the backend manifest schema clean.
const CONSUMED_BY: Record<string, string[]> = {
  patients: ["Analyst", "Opportunity List", "FHIR Export", "Platform Agents"],
  bmi_timeline: ["Analyst · BMI trends", "Patient Record", "Opportunity List"],
  medication_history: ["Analyst · cohorts", "Patient Record", "Opportunity List"],
  treatment_episodes: ["Analyst", "Patient Record"],
  quality_report: ["Analyst · alerts", "Patient Record", "Operational monitoring"],
  survey_unified: ["Patient Record · events", "Audit trail", "Annotation engine"],
  semantic_mapping: ["Review surface", "Every artifact", "Mapping API"],
  fhir_bundle: ["External integrations", "ePA / EHDS exports", "Partner systems"],
};

// Resources that have a snapshot CSV export. Whitelist mirrors the
// backend's _SNAPSHOT_EXPORTS in `meta.py` — keep them in sync. Two
// resources are intentionally absent: semantic_mapping (served via
// /v1/mapping as JSON, not a peer of data exports) and fhir_bundle
// (served per-patient via /v1/export/{id}/fhir, never bulk).
const SNAPSHOT_EXPORTS: ReadonlySet<string> = new Set([
  "patients",
  "bmi_timeline",
  "medication_history",
  "treatment_episodes",
  "quality_report",
  "survey_unified",
]);

function snapshotHref(name: string): string {
  return `/api/uniq/substrate/resources/${encodeURIComponent(name)}/export`;
}

function RepositoryMap({ manifest }: { manifest: SubstrateManifestResponse }) {
  const root = manifest.resources.find((r) => r.name === "patients");
  // Data resources — joined to patients via user_id. Order: clinical-
  // forward first (BMI / meds / treatments / events), operational at end.
  const dataChildOrder = [
    "bmi_timeline",
    "medication_history",
    "treatment_episodes",
    "survey_unified",
    "quality_report",
    "fhir_bundle",
  ];
  const dataChildren = dataChildOrder
    .map((name) => manifest.resources.find((r) => r.name === name))
    .filter((r): r is SubstrateResource => Boolean(r));

  // Governance resources — schema-level, not joined through user_id. Today
  // just `semantic_mapping`; future: clinical_annotations, audit log, etc.
  // Pulled out of the children grid so the card hierarchy reads as
  // "data resources" vs "governance layer", not as one flat list.
  const governance = manifest.resources.find((r) => r.name === "semantic_mapping");

  return (
    <section className="substrate-repository" aria-label="Clinical repository map">
      <div className="substrate-repository__head">
        <div>
          <span className="t-eyebrow">Clinical repository</span>
          <h2>{manifest.headline}</h2>
        </div>
        <span className="substrate-repository__version">{manifest.version}</span>
      </div>

      <AuditStrip events={manifest.audit_events} />

      <div className="substrate-repository__layout">
        <aside className="entity-tree" aria-label="Substrate entity relationships">
          <div className="entity-tree__head">
            <span className="t-eyebrow">topology</span>
            <span className="entity-tree__hint">{manifest.resources.length} resources</span>
          </div>
          <div className="entity-tree__root">
            <span className="entity-tree__root-name">{root?.label ?? "Patients"}</span>
            <span className="entity-tree__root-key">PK · {root?.primary_key ?? "user_id"}</span>
          </div>
          <div className="entity-tree__join">↓ user_id</div>
          <ul className="entity-tree__children">
            {dataChildren.map((resource, i) => (
              <li key={resource.name} className="entity-tree__child">
                <span className="entity-tree__branch" aria-hidden="true">
                  {i === dataChildren.length - 1 ? "└" : "├"}
                </span>
                <span className="entity-tree__name">{resource.label}</span>
              </li>
            ))}
          </ul>
          {governance && (
            <>
              <div className="entity-tree__governance-head">
                <span className="t-eyebrow">governance</span>
              </div>
              <ul className="entity-tree__children entity-tree__children--governance">
                <li className="entity-tree__child">
                  <span className="entity-tree__branch" aria-hidden="true">└</span>
                  <span className="entity-tree__name">{governance.label}</span>
                </li>
              </ul>
            </>
          )}
        </aside>

        <div className="resource-cards" aria-label="Repository resources">
          {root && (
            <ResourceHero
              resource={root}
              consumers={CONSUMED_BY.patients ?? []}
              childCount={dataChildren.length}
              delay={1650}
            />
          )}
          {governance && (
            <GovernanceStrip
              resource={governance}
              delay={1700}
            />
          )}
          <div className="resource-cards__grid">
            {dataChildren.map((resource, i) => (
              <ResourceCard
                key={resource.name}
                resource={resource}
                consumers={CONSUMED_BY[resource.name] ?? []}
                delay={1780 + i * 70}
              />
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function AuditStrip({ events }: { events: SubstrateAuditEvent[] }) {
  if (!events.length) return null;
  const event = events[0];
  return (
    <div className="substrate-audit" role="status">
      <span className="substrate-audit__dot" aria-hidden="true" />
      <span className="substrate-audit__status">{event.status}</span>
      <span className="substrate-audit__label">{event.label}</span>
      <span className="substrate-audit__detail">{event.detail}</span>
      <span className="substrate-audit__when">signed · audit trail</span>
    </div>
  );
}

function ResourceHero({
  resource,
  consumers,
  childCount,
  delay,
}: {
  resource: SubstrateResource;
  consumers: string[];
  childCount: number;
  delay: number;
}) {
  return (
    <article
      className="resource-hero"
      data-status={resource.status}
      style={{ animationDelay: `${delay}ms` }}
    >
      <div className="resource-hero__lhs">
        <div className="resource-hero__title">
          <h3>{resource.label}</h3>
          <span className="resource-hero__codename">{resource.name}</span>
          <StatusPill status={resource.status} />
        </div>
        <p className="resource-hero__caption">
          Primary identity · every other resource joins through{" "}
          <code>{resource.primary_key}</code>
        </p>
        <div className="resource-hero__meta">
          <span>
            <strong>{childCount}</strong> linked resources
          </span>
          <span>
            also indexed by{" "}
            {resource.sample_fields.slice(0, 3).map((f, i) => (
              <span key={f}>
                <code>{f}</code>
                {i < Math.min(2, resource.sample_fields.length - 1) ? ", " : ""}
              </span>
            ))}
          </span>
        </div>
        {consumers.length > 0 && (
          <div className="resource-hero__consumers">
            <span className="t-meta">consumed by</span>
            {consumers.map((c) => (
              <span key={c} className="resource-hero__consumer">{c}</span>
            ))}
          </div>
        )}
      </div>
      <div className="resource-hero__rhs">
        <div className="resource-hero__count">
          <div className="resource-hero__count-value">
            {resource.row_count.toLocaleString("en-US")}
          </div>
          <div className="resource-hero__count-label">{resource.label.toLowerCase()}</div>
        </div>
        <div className="resource-hero__hooks">
          {resource.api_hooks.map((hook) => (
            <code key={hook}>{hook}</code>
          ))}
        </div>
        {SNAPSHOT_EXPORTS.has(resource.name) && (
          <a
            className="snapshot-link"
            href={snapshotHref(resource.name)}
            download
          >
            ↓ snapshot CSV
          </a>
        )}
      </div>
    </article>
  );
}

function ResourceCard({
  resource,
  consumers,
  delay,
}: {
  resource: SubstrateResource;
  consumers: string[];
  delay: number;
}) {
  return (
    <article
      className="resource-card"
      data-status={resource.status}
      style={{ animationDelay: `${delay}ms` }}
    >
      <header className="resource-card__head">
        <h3>{resource.label}</h3>
        <StatusPill status={resource.status} />
      </header>
      <div className="resource-card__hero">
        <span className="resource-card__hero-value">
          {resource.row_count.toLocaleString("en-US")}
        </span>
        <span className="resource-card__hero-label">{resource.name}</span>
      </div>
      <div className="resource-card__keys">
        <span>
          <span className="resource-card__keys-label">PK</span> {resource.primary_key}
        </span>
        {resource.foreign_keys[0] && (
          <span>
            <span className="resource-card__keys-label">FK</span>{" "}
            {resource.foreign_keys[0].key} → {resource.foreign_keys[0].target_resource}
          </span>
        )}
      </div>
      {consumers.length > 0 && (
        <div className="resource-card__consumers">
          <span className="t-meta">consumed by</span>
          <span className="resource-card__consumers-list">
            {consumers.slice(0, 3).join(" · ")}
            {consumers.length > 3 && (
              <span className="resource-card__consumers-more"> · +{consumers.length - 3} more</span>
            )}
          </span>
        </div>
      )}
      <div className="resource-card__hooks">
        {resource.api_hooks.slice(0, 2).map((hook) => (
          <code key={hook}>{hook}</code>
        ))}
      </div>
      <div className="resource-card__foot">
        {SNAPSHOT_EXPORTS.has(resource.name) ? (
          <a
            className="snapshot-link"
            href={snapshotHref(resource.name)}
            download
          >
            ↓ snapshot CSV
          </a>
        ) : resource.name === "fhir_bundle" ? (
          <span className="snapshot-link snapshot-link--inline">
            per-patient · /v1/export/{"{id}"}/fhir
          </span>
        ) : null}
      </div>
    </article>
  );
}

function GovernanceStrip({
  resource,
  delay,
}: {
  resource: SubstrateResource;
  delay: number;
}) {
  // Compact horizontal strip — semantic_mapping is the contract layer
  // every other resource flows through. It's not a peer of patients /
  // bmi_timeline; it sits beside them as the schema-truth. Surfacing it
  // as a strip (not a card) reflects that role visually and avoids the
  // "thin card" problem where 20 rows looks weak next to 134k.
  return (
    <article
      className="governance-strip"
      data-status={resource.status}
      style={{ animationDelay: `${delay}ms` }}
    >
      <div className="governance-strip__lhs">
        <span className="t-eyebrow">governance layer</span>
        <h3 className="governance-strip__title">{resource.label}</h3>
        <span className="governance-strip__caption">
          The schema contract every data resource flows through ·{" "}
          <code>{resource.primary_key}</code>
        </span>
      </div>
      <div className="governance-strip__center">
        <div className="governance-strip__count">
          {resource.row_count.toLocaleString("en-US")}
          <span>/{resource.row_count}</span>
        </div>
        <div className="governance-strip__count-label">categories signed</div>
      </div>
      <div className="governance-strip__rhs">
        <StatusPill status={resource.status} />
        <div className="governance-strip__hooks">
          {resource.api_hooks.map((hook) => (
            <code key={hook}>{hook}</code>
          ))}
        </div>
        <a
          className="snapshot-link"
          href="/api/uniq/mapping"
          download="uniq-semantic-mapping-snapshot.json"
        >
          ↓ snapshot JSON
        </a>
      </div>
    </article>
  );
}

function StatusPill({ status }: { status: SubstrateResource["status"] }) {
  return (
    <span className="resource-status" data-status={status}>
      <span className="resource-status__dot" aria-hidden="true" />
      {status}
    </span>
  );
}

function MetricTile({
  label,
  target,
  delay,
  suffix,
}: {
  label: string;
  target: number;
  delay: number;
  /** Optional string appended after the animated number (e.g. "/20"). */
  suffix?: string;
}) {
  const startAt = 850 + delay;
  const duration = 900; // long enough to feel tactile, short enough to not drag
  const [value, setValue] = useState(0);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    // Wait for the tile's own fade-in to start, then count up in sync.
    const startTimer = setTimeout(() => {
      const t0 = performance.now();
      const tick = (now: number) => {
        const elapsed = now - t0;
        const p = Math.min(1, elapsed / duration);
        // Ease-out-cubic — settles like a real number, not a meter.
        const eased = 1 - Math.pow(1 - p, 3);
        setValue(Math.round(target * eased));
        if (p < 1) rafRef.current = requestAnimationFrame(tick);
      };
      rafRef.current = requestAnimationFrame(tick);
    }, startAt);

    return () => {
      clearTimeout(startTimer);
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    };
  }, [target, startAt]);

  const display = value.toLocaleString("en-US") + (suffix ?? "");

  return (
    <div className="substrate-metric" style={{ animationDelay: `${startAt}ms` }}>
      <div className="substrate-metric__value">{display}</div>
      <div className="substrate-metric__label">{label}</div>
    </div>
  );
}

function UnlockCard({
  title,
  body,
  cta,
  href,
  delay,
  onClick,
}: {
  title: string;
  body: string;
  cta: string;
  href: string;
  delay: number;
  onClick?: () => void;
}) {
  return (
    <Link
      href={href}
      className="unlock-card"
      style={{ animationDelay: `${delay}ms` }}
      onClick={onClick}
    >
      <div className="unlock-card__title">{title}</div>
      <div className="unlock-card__body">{body}</div>
      <div className="unlock-card__cta">{cta} →</div>
    </Link>
  );
}
