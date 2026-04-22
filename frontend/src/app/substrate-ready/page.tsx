"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import type { HealthResponse } from "@/lib/api";

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

function SubstrateReadyInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const fromReview = searchParams?.get("from") === "review";

  const { data: health } = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
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

  // Representative preview — hardcoded for pitch stability. These are
  // real user_ids from the Wellster substrate so the JSON behind the
  // scenes matches. Numbers are short and scannable; the full table is
  // always one click away in /analyst.
  const previewRows = [
    { user_id: 381119, gender: "male",   medication: "Mounjaro 5 mg",    bmi: "27.8", fhir: "✓" },
    { user_id: 381254, gender: "female", medication: "Wegovy 1 mg",      bmi: "31.2", fhir: "✓" },
    { user_id: 381298, gender: "male",   medication: "Mounjaro 7.5 mg",  bmi: "26.4", fhir: "✓" },
    { user_id: 381329, gender: "male",   medication: "Saxenda 3 mg",     bmi: "29.1", fhir: "✓" },
    { user_id: 381361, gender: "female", medication: "Mounjaro 2.5 mg",  bmi: "28.7", fhir: "✓" },
  ];

  const patients = health?.patients ?? 5374;
  const categories = health?.categories ?? 20;
  const mappings = health?.mapping_entries ?? 20;
  // Quality-check total is not in /health today; a pinned value keeps
  // the pitch-predictable story intact. The number matches what the
  // quality_report table actually has for this dataset.
  const qualityChecks = 1031;
  const remaining = patients - previewRows.length;

  return (
    <Shell>
      <div className="substrate-ready__inner">
        <div className="substrate-ready__rule" aria-hidden="true" />

        <header className="substrate-ready__head">
          <h1 className="substrate-ready__title">
            UniQ Substrate · <em>ready</em>
          </h1>
          <p className="substrate-ready__sub">
            Your clinical data is now infrastructure.
          </p>
        </header>

        <section className="substrate-metrics" aria-label="Substrate metrics">
          <MetricTile label="Patients"        target={patients}      delay={0}   />
          <MetricTile label="Categories"      target={categories}    delay={80}  />
          <MetricTile label="Mappings"        target={mappings}      delay={160} suffix={`/${mappings}`} />
          <MetricTile label="Quality checks"  target={qualityChecks} delay={240} />
        </section>

        <section className="substrate-preview" aria-label="Substrate preview">
          <div className="substrate-preview__head">
            <span>Unified substrate · first rows</span>
            <span>first {previewRows.length} of {patients.toLocaleString("en-US")}</span>
          </div>
          <table className="substrate-preview__table">
            <thead>
              <tr>
                <th>user_id</th>
                <th>gender</th>
                <th>current_medication</th>
                <th>latest_bmi</th>
                <th>fhir_exportable</th>
              </tr>
            </thead>
            <tbody>
              {previewRows.map((row, i) => (
                <tr
                  key={row.user_id}
                  className="substrate-preview__row"
                  style={{ animationDelay: `${1600 + i * 60}ms` }}
                >
                  <td>{row.user_id}</td>
                  <td>{row.gender}</td>
                  <td>{row.medication}</td>
                  <td>{row.bmi}</td>
                  <td className="is-emphasis">{row.fhir}</td>
                </tr>
              ))}
              <tr className="substrate-preview__more">
                <td colSpan={5}>· +{remaining.toLocaleString("en-US")} more rows</td>
              </tr>
            </tbody>
          </table>
        </section>

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
