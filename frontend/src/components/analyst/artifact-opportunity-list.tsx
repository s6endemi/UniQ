"use client";

import { useMemo } from "react";
import type {
  ActivationFilterStep,
  OpportunityListPayload,
  ScreeningCandidate,
  TrendDirection,
} from "@/lib/api";
import { ArtifactKpis } from "./artifact-kpis";

/**
 * Opportunity-list artifact renderer (cross-brand screening candidates).
 *
 * Layout from top to bottom:
 *   1. Headline + methodology     (the "we found a cohort" claim + trust line)
 *   2. Activation funnel          (4 horizontal bars showing source → target
 *                                  cohort cascade — the unique visual that
 *                                  makes this NOT just a fancy table)
 *   3. KPI strip                  (cohort total, BMI-eligible, target-naive,
 *                                  high-priority count)
 *   4. Ranked candidate table     (20 rows, priority badge + reason chip
 *                                  per row, BMI trend arrow)
 *   5. Compliance footer          (export + the operations-owns-decision
 *                                  reminder — clinically defensive framing)
 *
 * The artifact deliberately omits revenue figures. The truth layer
 * surfaces the cohort; the customer's clinical / outreach team owns
 * the valuation and the consent decision. Anything more would erode
 * the clinical credibility that the substrate earns.
 */

const TREND_GLYPH: Record<TrendDirection, string> = {
  down: "↓",
  up: "↑",
  stable: "→",
  unknown: "·",
};

const TREND_LABEL: Record<TrendDirection, string> = {
  down: "trending down",
  up: "trending up",
  stable: "stable",
  unknown: "single measurement",
};

export function ArtifactOpportunityList({
  payload,
}: {
  payload: OpportunityListPayload;
}) {
  const handleExport = () => {
    const blob = new Blob([JSON.stringify(payload, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `screening-${payload.source_brand}-to-${payload.target_brand}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="opportunity">
      {/* ---- Headline + methodology ---- */}
      <header className="opportunity__head">
        <h3 className="opportunity__headline">{payload.headline}</h3>
        <p className="opportunity__methodology">{payload.methodology}</p>
      </header>

      <ArtifactKpis kpis={payload.kpis} />

      {/* ---- Activation funnel ---- */}
      <ActivationFunnel steps={payload.activation_path} />

      {/* ---- Ranked candidate table ---- */}
      <CandidateTable
        candidates={payload.candidates}
        totalCount={payload.total_candidates}
      />

      {/* ---- Compliance footer ---- */}
      <footer className="opportunity__footer">
        <button
          type="button"
          className="opportunity__export"
          onClick={handleExport}
        >
          Export candidate list (JSON)
        </button>
        <p className="opportunity__compliance">
          Outreach decisions and patient consent remain with Wellster
          Operations. UniQ surfaces the cohort; the action belongs to
          the clinical team.
        </p>
      </footer>
    </div>
  );
}

// ---------------------------------------------------------------------
// Activation funnel
// ---------------------------------------------------------------------

function ActivationFunnel({ steps }: { steps: ActivationFilterStep[] }) {
  const maxCount = useMemo(
    () => Math.max(1, ...steps.map((s) => s.count)),
    [steps],
  );

  return (
    <section className="funnel" aria-label="Activation path from source cohort to candidates">
      <div className="funnel__head">
        <span className="t-eyebrow">Activation path</span>
        <span className="t-meta">
          source cohort → clinical filter → exclusion → review window
        </span>
      </div>
      <ol className="funnel__steps">
        {steps.map((step, i) => {
          const widthPct = Math.max(8, Math.round((step.count / maxCount) * 100));
          const isFinal = i === steps.length - 1;
          return (
            <li
              key={step.label}
              className={`funnel__step ${isFinal ? "funnel__step--final" : ""}`}
            >
              <div className="funnel__step-meta">
                <span className="funnel__step-num">{String(i + 1).padStart(2, "0")}</span>
                <div className="funnel__step-label">
                  <span className="funnel__step-name">{step.label}</span>
                  {step.description && (
                    <span className="funnel__step-desc">{step.description}</span>
                  )}
                </div>
                <span className="funnel__step-count">{step.count.toLocaleString()}</span>
              </div>
              <div className="funnel__step-bar-wrap">
                <div
                  className="funnel__step-bar"
                  style={{ width: `${widthPct}%` }}
                  aria-hidden
                />
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

// ---------------------------------------------------------------------
// Candidate table
// ---------------------------------------------------------------------

function CandidateTable({
  candidates,
  totalCount,
}: {
  candidates: ScreeningCandidate[];
  totalCount: number;
}) {
  if (candidates.length === 0) {
    return (
      <section className="opportunity__candidates">
        <div className="opportunity__candidates-empty">
          <span className="t-meta">No candidates matched this filter.</span>
        </div>
      </section>
    );
  }

  return (
    <section className="opportunity__candidates">
      <div className="opportunity__candidates-head">
        <span className="t-eyebrow">Candidate cohort</span>
        <span className="t-meta">
          showing {candidates.length.toLocaleString()} of{" "}
          {totalCount.toLocaleString()} · ranked by clinical priority
        </span>
      </div>
      <ol className="opp-row-list">
        {candidates.map((c, i) => (
          <CandidateRow key={c.user_id} candidate={c} index={i + 1} />
        ))}
      </ol>
    </section>
  );
}

function CandidateRow({
  candidate,
  index,
}: {
  candidate: ScreeningCandidate;
  index: number;
}) {
  const bmiLabel = candidate.latest_bmi !== null
    ? candidate.latest_bmi.toFixed(1)
    : "—";
  const trendGlyph = TREND_GLYPH[candidate.bmi_trend];
  const trendLabel = TREND_LABEL[candidate.bmi_trend];
  const ageGender = [
    candidate.age ? `${candidate.age}y` : null,
    candidate.gender || null,
  ]
    .filter(Boolean)
    .join(" · ");
  const inactive =
    candidate.days_since_activity !== null
      ? `${candidate.days_since_activity}d ago`
      : "—";

  return (
    <li
      className="opp-row"
      data-priority={candidate.priority}
    >
      <span className="opp-row__idx">{String(index).padStart(2, "0")}</span>
      <div className="opp-row__id">
        <span className="opp-row__patient">{candidate.label}</span>
        <span className="opp-row__demo">{ageGender || "—"}</span>
      </div>
      <div className="opp-row__bmi">
        <span className="opp-row__bmi-value">{bmiLabel}</span>
        <span
          className={`opp-row__bmi-trend opp-row__bmi-trend--${candidate.bmi_trend}`}
          title={trendLabel}
        >
          {trendGlyph}
        </span>
      </div>
      <div className="opp-row__treatment">
        {candidate.current_treatment ? (
          <>
            <span className="opp-row__treatment-name">{candidate.current_treatment}</span>
            {candidate.current_dosage && (
              <span className="opp-row__treatment-dose">{candidate.current_dosage}</span>
            )}
          </>
        ) : (
          <span className="opp-row__treatment-name">—</span>
        )}
      </div>
      <div className="opp-row__activity">
        <span className="t-meta">last seen</span>
        <span className="opp-row__activity-value">{inactive}</span>
      </div>
      <div className="opp-row__reason">{candidate.reason_summary}</div>
      <span
        className={`opp-row__priority opp-row__priority--${candidate.priority}`}
      >
        {candidate.priority}
      </span>
    </li>
  );
}
