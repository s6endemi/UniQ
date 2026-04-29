"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type {
  ClinicalAnnotation,
  ClinicalAnnotationCreate,
  PatientEvent,
  PatientEventTrack,
  PatientMedicationSegment,
  PatientRecordPayload,
} from "@/lib/api";
import { ArtifactKpis } from "./artifact-kpis";

/**
 * Patient-record artifact renderer.
 *
 * Layout from top to bottom:
 *   1. Identity header     (PT-id + brand + demographics + status chip)
 *   2. KPI strip           (tenure, BMI delta, treatments, events)
 *   3. BMI hero chart      (line + area fill + start/end annotations
 *                           + WHO normal-BMI baseline reference +
 *                           weight-category transition chip)
 *   4. Treatment timeline  (4 compact tracks: medication bars with
 *                           dose labels + side-effect/condition/
 *                           quality markers, shared time axis)
 *   5. Audit-trail panel   (per-event provenance: source field →
 *                           normalised category → standard code →
 *                           HITL review status)
 *   6. Substrate footer    (collapsed-source-fields metric, FHIR
 *                           resource count, dose-progression list)
 *
 * Implementation notes for the design language:
 *
 * - All event markers (BMI dots, timeline dots) are HTML overlays
 *   positioned absolutely on top of the SVG canvas. SVG circles get
 *   visibly distorted into ovals when the parent uses
 *   preserveAspectRatio="none" (the X scale and Y scale are
 *   different) — vector-effect=non-scaling-stroke fixes lines, not
 *   circles. HTML dots stay perfectly round at any container size,
 *   which matters for the pitch demo where the panel is resized.
 *
 * - Empty tracks ("Quality flags · 0") render an explicit "all clear"
 *   placeholder rather than blank space, so the absence of findings
 *   reads as a positive signal, not a missing feature.
 *
 * - When the user selects an event near the top of the chart, the
 *   audit-trail panel is well below the fold; we smooth-scroll it
 *   into view so the click → provenance reveal stays continuous.
 */

const EVENT_TRACK_ORDER: PatientEventTrack[] = [
  "medication",
  "side_effect",
  "condition",
  "quality",
  "annotation",
];

// Annotations sit at the bottom of the timeline, beneath the audited
// data tracks. Visually this reads as "the foundation layer where
// clinicians add their own context back" — the living-substrate beat
// Martin asked for, rendered as a peer track rather than a side panel.

const TRACK_LABEL: Record<PatientEventTrack, string> = {
  bmi: "BMI",
  medication: "Medication",
  side_effect: "Side effects",
  condition: "Conditions",
  quality: "Quality flags",
  survey: "Survey",
  annotation: "Clinician notes",
};

const TRACK_HINT: Record<PatientEventTrack, string> = {
  bmi: "LOINC 39156-5 · vital signs",
  medication: "RxNorm + ATC · prescription history",
  side_effect: "SIDE_EFFECT_REPORT · self-reported",
  condition: "Medical history + cardio profile",
  quality: "Substrate operational checks",
  survey: "Survey-derived event",
  annotation: "Living substrate · clinician write-back",
};

const TRACK_EMPTY_COPY: Record<PatientEventTrack, string> = {
  bmi: "no measurements",
  medication: "no prescriptions",
  side_effect: "no findings reported",
  condition: "no conditions on file",
  quality: "all clear · no flags raised",
  survey: "no survey events",
  annotation: "no clinician notes yet",
};

// Track Y centres in the event-timeline SVG (viewBox height = 104).
// Five tracks, evenly spaced: 12, 32, 52, 72, 92 with lane height 18.
// ViewBox grew from 84 → 104 when annotation became the 5th lane.
const EVENT_TRACK_Y: Record<PatientEventTrack, number> = {
  bmi: 0,
  medication: 12,
  side_effect: 32,
  condition: 52,
  quality: 72,
  survey: 52,
  annotation: 92,
};

const TIMELINE_VIEWBOX_HEIGHT = 104;

const NORMAL_BMI = 25; // WHO normal-range upper bound

interface HoverState {
  eventId: string;
  xPct: number;
  yPct: number;
  inBmiChart: boolean;
}

export function ArtifactPatientRecord({
  payload,
}: {
  payload: PatientRecordPayload;
}) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [hoverState, setHoverState] = useState<HoverState | null>(null);
  const [hiddenTracks, setHiddenTracks] = useState<Set<PatientEventTrack>>(
    () => new Set(),
  );
  const detailRef = useRef<HTMLElement | null>(null);

  const { header, kpis, medications, bmi_series } = payload;

  // Locally-added annotations during this session. Merged into the
  // backend-shipped events so the timeline picks them up immediately
  // (no manifest re-fetch required for the inline write to feel real).
  // Persistence still happens server-side via POST; on a cold reload
  // the same notes come back through the patient_record builder.
  const [localAnnotations, setLocalAnnotations] = useState<PatientEvent[]>([]);
  const events = useMemo(
    () =>
      [...payload.events, ...localAnnotations].sort((a, b) =>
        a.timestamp.localeCompare(b.timestamp),
      ),
    [payload.events, localAnnotations],
  );

  // ---- Time projection -------------------------------------------------
  const { tStart, tSpan, monthLabels } = useMemo(() => {
    const allTimes = events
      .map((e) => Date.parse(e.timestamp))
      .filter((n) => Number.isFinite(n));
    if (allTimes.length === 0) {
      return { tStart: 0, tSpan: 1, monthLabels: [] as MonthLabel[] };
    }
    const min = Math.min(...allTimes);
    const max = Math.max(...allTimes);
    const span = Math.max(max - min, 1);
    return {
      tStart: min,
      tSpan: span,
      monthLabels: buildMonthLabels(min, max),
    };
  }, [events]);

  const projectX = (iso: string): number => {
    const t = Date.parse(iso);
    if (!Number.isFinite(t) || tSpan === 0) return 0;
    return ((t - tStart) / tSpan) * 100;
  };

  // ---- BMI chart geometry ---------------------------------------------
  const bmi = useMemo(() => {
    if (bmi_series.length === 0) return null;
    const points = bmi_series
      .map((p) => ({
        date: p.date,
        v: p.value,
        x: projectX(p.date),
      }))
      .filter((p) => Number.isFinite(p.x))
      .sort((a, b) => a.x - b.x);
    if (points.length === 0) return null;

    const values = points.map((p) => p.v);
    const dataMin = Math.min(...values);
    const dataMax = Math.max(...values);
    const yMin = Math.min(dataMin, NORMAL_BMI) - 1.5;
    const yMax = Math.max(dataMax, NORMAL_BMI) + 1.5;
    const ySpan = Math.max(yMax - yMin, 0.5);

    const top = 6;
    const bottom = 54;
    const usable = bottom - top;
    const projectY = (v: number) => bottom - ((v - yMin) / ySpan) * usable;

    const coords = points.map((p) => [p.x, projectY(p.v)] as [number, number]);
    const linePath = coords
      .map(([x, y], i) => (i === 0 ? `M ${x} ${y}` : `L ${x} ${y}`))
      .join(" ");
    const lastX = coords[coords.length - 1][0];
    const firstX = coords[0][0];
    const areaPath = `${linePath} L ${lastX} ${bottom} L ${firstX} ${bottom} Z`;
    const baselineY = projectY(NORMAL_BMI);

    return {
      points,
      coords: coords.map(([x, y]) => ({
        xPct: x,
        yPct: ((y - 0) / 60) * 100,
      })),
      svgCoords: coords,
      linePath,
      areaPath,
      baselineYPct: ((baselineY - 0) / 60) * 100,
      yRange: { min: yMin, max: yMax },
      first: {
        value: points[0].v,
        xPct: firstX,
        yPct: ((coords[0][1] - 0) / 60) * 100,
      },
      last: {
        value: points[points.length - 1].v,
        xPct: lastX,
        yPct: ((coords[coords.length - 1][1] - 0) / 60) * 100,
      },
    };
    // projectX is a stable closure over (tStart, tSpan)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bmi_series, tStart, tSpan]);

  const visibleEvents = events.filter((e) => !hiddenTracks.has(e.track));

  const selected = selectedId
    ? events.find((e) => e.id === selectedId) ?? null
    : null;

  // Auto-scroll the audit panel into view when an event is selected.
  // Without this, clicking a dot at the top of the chart leaves the
  // user wondering where the audit trail went — it's far below the
  // fold. Smooth scroll keeps the demo continuous.
  useEffect(() => {
    if (!selectedId || !detailRef.current) return;
    detailRef.current.scrollIntoView({
      behavior: "smooth",
      block: "nearest",
    });
  }, [selectedId]);

  const toggleTrack = (track: PatientEventTrack) => {
    setHiddenTracks((prev) => {
      const next = new Set(prev);
      if (next.has(track)) next.delete(track);
      else next.add(track);
      return next;
    });
  };

  const hoverEvent = hoverState
    ? events.find((e) => e.id === hoverState.eventId) ?? null
    : null;

  const medSpans = useMemo(() => collapseMedSpans(medications), [medications]);

  const eventCounts = useMemo(() => {
    const out: Record<PatientEventTrack, number> = {
      bmi: 0,
      medication: 0,
      side_effect: 0,
      condition: 0,
      quality: 0,
      survey: 0,
      annotation: 0,
    };
    for (const e of events) out[e.track] += 1;
    return out;
  }, [events]);

  // Clinical category interpretation derived from BMI thresholds (WHO).
  // This is a pure data derivation — no LLM-generated clinical advice.
  const bmiCategoryShift = useMemo(() => {
    if (!bmi) return null;
    const startCat = bmiCategory(bmi.first.value);
    const endCat = bmiCategory(bmi.last.value);
    if (startCat === endCat) {
      return { sustained: true, label: startCat };
    }
    return { sustained: false, from: startCat, to: endCat };
  }, [bmi]);

  return (
    <div className="patient-record">
      {/* ---- Identity header ---- */}
      <header className="patient-record__head">
        <div className="patient-record__identity">
          <div className="patient-record__id">{header.label}</div>
          <div className="patient-record__demo">
            <span className="patient-record__demo-cell">
              <span className="t-meta">Brand</span>
              <span>{header.brand ?? "—"}</span>
            </span>
            <span className="patient-record__demo-cell">
              <span className="t-meta">Gender</span>
              <span>{header.gender || "—"}</span>
            </span>
            <span className="patient-record__demo-cell">
              <span className="t-meta">Age</span>
              <span>{header.current_age || "—"}</span>
            </span>
            <span className="patient-record__demo-cell">
              <span className="t-meta">Current Rx</span>
              <span>
                {header.current_medication
                  ? `${header.current_medication}${
                      header.current_dosage ? " · " + header.current_dosage : ""
                    }`
                  : "—"}
              </span>
            </span>
          </div>
        </div>
        <div className={`patient-record__status patient-record__status--${header.status}`}>
          <span className="patient-record__status-dot" aria-hidden />
          {header.status === "active" ? "active treatment" : "inactive"}
        </div>
      </header>

      <ArtifactKpis kpis={kpis} />

      {/* ---- Substrate lineage ribbon ----
          Upfront visible story: N raw fields → 1 unified record →
          every event signed → FHIR-exportable. Without this, the
          artifact reads as "another patient dashboard" until the
          user clicks a dot. Pitch insurance. */}
      <SubstrateLineage payload={payload} />

      {/* ---- BMI hero chart ---- */}
      <section className="patient-record__bmi-hero">
        <div className="patient-record__section-head">
          <div>
            <div className="patient-record__section-eyebrow">
              BMI trajectory · LOINC 39156-5
            </div>
            <h3 className="patient-record__section-title">
              {bmi
                ? `${bmi.first.value.toFixed(1)} → ${bmi.last.value.toFixed(1)} kg/m²`
                : "BMI unavailable"}
            </h3>
          </div>
          <div className="patient-record__section-side">
            {bmi && (
              <span className="t-meta patient-record__section-meta">
                {bmi.points.length} measurements ·{" "}
                {(bmi.last.value - bmi.first.value > 0 ? "+" : "") +
                  (bmi.last.value - bmi.first.value).toFixed(1)}{" "}
                kg/m²
              </span>
            )}
            {bmiCategoryShift && (
              <span
                className={`patient-record__category-chip ${
                  bmiCategoryShift.sustained
                    ? "patient-record__category-chip--sustained"
                    : "patient-record__category-chip--shift"
                }`}
                title="WHO BMI category"
              >
                {bmiCategoryShift.sustained ? (
                  <>
                    <span className="patient-record__category-chip-mark" aria-hidden />
                    {bmiCategoryShift.label}
                  </>
                ) : (
                  <>
                    <span className="patient-record__category-chip-mark" aria-hidden />
                    {bmiCategoryShift.from}
                    <span className="patient-record__category-chip-arrow"> → </span>
                    <strong>{bmiCategoryShift.to}</strong>
                  </>
                )}
              </span>
            )}
          </div>
        </div>

        <div
          className="patient-record__bmi-canvas"
          onMouseLeave={() => setHoverState((h) => (h?.inBmiChart ? null : h))}
        >
          {bmi ? (
            <>
              {/* Y-axis: only min and max values for visual quietness. */}
              <div className="patient-record__bmi-yaxis">
                <span
                  className="patient-record__bmi-ytick patient-record__bmi-ytick--top"
                >
                  {(bmi.yRange.max - 1).toFixed(1)}
                </span>
                <span
                  className="patient-record__bmi-ytick patient-record__bmi-ytick--bottom"
                >
                  {(bmi.yRange.min + 1).toFixed(1)}
                </span>
              </div>

              {/* SVG: lines + paths only (these stretch fine).
                  Dots and markers are HTML overlays for crisp circles. */}
              <svg
                className="patient-record__bmi-svg"
                viewBox="0 0 100 60"
                preserveAspectRatio="none"
                aria-hidden
              >
                {[15, 30, 45].map((y) => (
                  <line
                    key={y}
                    x1={0}
                    x2={100}
                    y1={y}
                    y2={y}
                    stroke="var(--rule-soft)"
                    strokeWidth={0.15}
                    vectorEffect="non-scaling-stroke"
                  />
                ))}
                {/* WHO normal-BMI baseline reference */}
                <line
                  x1={0}
                  x2={100}
                  y1={(bmi.baselineYPct / 100) * 60}
                  y2={(bmi.baselineYPct / 100) * 60}
                  stroke="var(--signal)"
                  strokeWidth={0.35}
                  strokeDasharray="1.5 1"
                  opacity={0.6}
                  vectorEffect="non-scaling-stroke"
                />

                <path d={bmi.areaPath} fill="var(--signal-wash)" opacity={0.8} />

                <path
                  d={bmi.linePath}
                  fill="none"
                  stroke="var(--signal-ink)"
                  strokeWidth={1.2}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  vectorEffect="non-scaling-stroke"
                />
              </svg>

              {/* HTML dot overlay — guaranteed perfect circles */}
              <div className="patient-record__bmi-dots">
                {bmi.coords.map((p, i) => {
                  const id = `bmi-${i}`;
                  const isSelected = selectedId === id;
                  const isHover = hoverState?.eventId === id;
                  return (
                    <button
                      key={id}
                      type="button"
                      className={`patient-record__dot patient-record__dot--bmi ${
                        isSelected ? "is-selected" : ""
                      } ${isHover ? "is-hover" : ""}`}
                      style={{ left: `${p.xPct}%`, top: `${p.yPct}%` }}
                      onClick={() => setSelectedId(id)}
                      onMouseEnter={() =>
                        setHoverState({
                          eventId: id,
                          xPct: p.xPct,
                          yPct: p.yPct,
                          inBmiChart: true,
                        })
                      }
                      aria-label={`BMI ${bmi.points[i].v.toFixed(2)} on ${bmi.points[i].date.slice(0, 10)}`}
                    />
                  );
                })}
              </div>

              {/* Direct annotations — placed below the line so they don't
                  collide with the Y-axis tick labels at the left edge. */}
              <div
                className="patient-record__bmi-annotation patient-record__bmi-annotation--first"
                style={{ left: `${bmi.first.xPct}%`, top: `${bmi.first.yPct}%` }}
              >
                <span className="patient-record__bmi-annotation-tag">
                  Baseline
                </span>
                <span className="patient-record__bmi-annotation-value">
                  {bmi.first.value.toFixed(1)}
                </span>
              </div>
              <div
                className="patient-record__bmi-annotation patient-record__bmi-annotation--last"
                style={{ left: `${bmi.last.xPct}%`, top: `${bmi.last.yPct}%` }}
              >
                <span className="patient-record__bmi-annotation-tag">
                  Latest
                </span>
                <span className="patient-record__bmi-annotation-value">
                  {bmi.last.value.toFixed(1)}
                </span>
              </div>

              <span
                className="patient-record__bmi-baseline-label"
                style={{ top: `${bmi.baselineYPct}%` }}
              >
                BMI 25 · overweight threshold
              </span>

              {hoverEvent && hoverState?.inBmiChart && (
                <HoverTooltip
                  event={hoverEvent}
                  xPct={hoverState.xPct}
                  yPct={hoverState.yPct}
                />
              )}
            </>
          ) : (
            <div className="patient-record__empty-chart">
              No BMI measurements on file for this patient.
            </div>
          )}
        </div>
      </section>

      {/* ---- Track legend / toggles ---- */}
      <div className="patient-record__legend" role="group" aria-label="Timeline tracks">
        {EVENT_TRACK_ORDER.map((track) => {
          const isHidden = hiddenTracks.has(track);
          const count = eventCounts[track];
          return (
            <button
              key={track}
              type="button"
              className={`patient-record__legend-pill patient-record__legend-pill--${track}`}
              data-active={!isHidden}
              data-empty={count === 0}
              onClick={() => toggleTrack(track)}
              aria-pressed={!isHidden}
            >
              <span className="patient-record__legend-mark" aria-hidden />
              {TRACK_LABEL[track]}
              <span className="patient-record__legend-count">{count}</span>
            </button>
          );
        })}
      </div>

      {/* ---- Event timeline (multi-track) ---- */}
      <section className="patient-record__events">
        <div className="patient-record__events-grid">
          <div className="patient-record__timeline-labels">
            {EVENT_TRACK_ORDER.map((track) => (
              <div
                key={track}
                className="patient-record__timeline-label"
                data-hidden={hiddenTracks.has(track)}
              >
                <span className="patient-record__timeline-label-name">
                  {TRACK_LABEL[track]}
                </span>
                <span className="patient-record__timeline-label-hint">
                  {TRACK_HINT[track]}
                </span>
              </div>
            ))}
          </div>

          <div
            className="patient-record__events-canvas"
            onMouseLeave={() => setHoverState((h) => (h?.inBmiChart ? h : null))}
          >
            <svg
              className="patient-record__events-svg"
              viewBox={`0 0 100 ${TIMELINE_VIEWBOX_HEIGHT}`}
              preserveAspectRatio="none"
              aria-hidden
            >
              {/* Alternating lane backgrounds */}
              {EVENT_TRACK_ORDER.map((track, i) => {
                const y = EVENT_TRACK_Y[track] - 9;
                const fill =
                  i % 2 === 0
                    ? "var(--paper-rise)"
                    : "color-mix(in oklab, var(--paper-sunk) 22%, var(--paper-rise))";
                return (
                  <rect
                    key={track}
                    x={0}
                    y={y}
                    width={100}
                    height={18}
                    fill={hiddenTracks.has(track) ? "var(--paper-sunk)" : fill}
                    opacity={hiddenTracks.has(track) ? 0.4 : 1}
                  />
                );
              })}

              {/* Medication segments — SVG rects fill cleanly */}
              {!hiddenTracks.has("medication") &&
                medSpans.map((span, i) => {
                  const x1 = projectX(span.started);
                  const x2 = span.ended ? projectX(span.ended) : 100;
                  const w = Math.max(1.2, x2 - x1);
                  const y = EVENT_TRACK_Y.medication - 5;
                  return (
                    <rect
                      key={`med-span-${i}`}
                      x={x1}
                      y={y}
                      width={w}
                      height={10}
                      fill="var(--signal-wash)"
                      stroke="var(--signal-ink)"
                      strokeWidth={0.4}
                      vectorEffect="non-scaling-stroke"
                      rx={0.6}
                    />
                  );
                })}
            </svg>

            {/* HTML dot overlay for events (non-medication tracks) */}
            <div className="patient-record__events-dots">
              {visibleEvents
                .filter((e) => e.track !== "bmi" && e.track !== "medication")
                .map((e) => {
                  const xPct = projectX(e.timestamp);
                  const yPct = (EVENT_TRACK_Y[e.track] / TIMELINE_VIEWBOX_HEIGHT) * 100;
                  const isSelected = e.id === selectedId;
                  const isHover = hoverState?.eventId === e.id;
                  // Annotations get their own visual treatment (the ✎ glyph
                  // marker) because they are write-back events, not derived
                  // observations. Severity classes apply to the four
                  // upstream-data tracks where alert/warn semantics matter.
                  const trackClass =
                    e.track === "annotation"
                      ? "patient-record__dot--annotation"
                      : e.severity === "alert"
                        ? "patient-record__dot--alert"
                        : e.severity === "warn"
                          ? "patient-record__dot--warn"
                          : "patient-record__dot--neutral";
                  const isAnnotation = e.track === "annotation";
                  return (
                    <button
                      key={e.id}
                      type="button"
                      className={`patient-record__dot ${trackClass} ${
                        isSelected ? "is-selected" : ""
                      } ${isHover ? "is-hover" : ""}`}
                      style={{ left: `${xPct}%`, top: `${yPct}%` }}
                      onClick={() => setSelectedId(e.id)}
                      onMouseEnter={() =>
                        setHoverState({
                          eventId: e.id,
                          xPct,
                          yPct,
                          inBmiChart: false,
                        })
                      }
                      aria-label={`${TRACK_LABEL[e.track]}: ${e.label}`}
                    >
                      {isAnnotation && (
                        <span className="patient-record__dot-glyph" aria-hidden>
                          ✎
                        </span>
                      )}
                    </button>
                  );
                })}
            </div>

            {/* HTML overlay: dose labels inside medication bars */}
            {!hiddenTracks.has("medication") &&
              medSpans.map((span, i) => {
                const x1 = projectX(span.started);
                const x2 = span.ended ? projectX(span.ended) : 100;
                const w = Math.max(0, x2 - x1);
                if (w < 6) return null;
                const yPct = (EVENT_TRACK_Y.medication / TIMELINE_VIEWBOX_HEIGHT) * 100;
                return (
                  <span
                    key={`med-label-${i}`}
                    className="patient-record__med-label"
                    style={{
                      left: `${x1}%`,
                      width: `${w}%`,
                      top: `${yPct}%`,
                    }}
                  >
                    {span.dosage || span.name}
                  </span>
                );
              })}

            {/* HTML overlay: empty-state placeholders for tracks with 0 events */}
            {EVENT_TRACK_ORDER.map((track) => {
              if (eventCounts[track] > 0) return null;
              if (hiddenTracks.has(track)) return null;
              const yPct = (EVENT_TRACK_Y[track] / TIMELINE_VIEWBOX_HEIGHT) * 100;
              return (
                <span
                  key={`empty-${track}`}
                  className="patient-record__lane-empty"
                  style={{ top: `${yPct}%` }}
                >
                  {TRACK_EMPTY_COPY[track]}
                </span>
              );
            })}

            {hoverEvent && !hoverState?.inBmiChart && (
              <HoverTooltip
                event={hoverEvent}
                xPct={hoverState!.xPct}
                yPct={hoverState!.yPct}
              />
            )}
          </div>
        </div>

        {/* Shared time axis */}
        <div className="patient-record__timeline-axis">
          <div className="patient-record__timeline-axis-track">
            {monthLabels.map((m) => (
              <span
                key={m.iso}
                className="patient-record__timeline-tick"
                style={{ left: `${m.x}%` }}
              >
                {m.label}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* ---- Audit-trail detail panel ---- */}
      <section
        className="patient-record__detail"
        ref={(el) => {
          detailRef.current = el;
        }}
      >
        {selected ? (
          <SelectedEventCard
            event={selected}
            patientId={header.user_id}
            onClose={() => setSelectedId(null)}
            onAnnotationCreated={(ann) => {
              const newEvent = annotationToEvent(ann);
              setLocalAnnotations((prev) => [...prev, newEvent]);
              setSelectedId(newEvent.id);
            }}
          />
        ) : (
          <EmptyDetailHint
            firstEvent={
              events.find((e) => e.track === "bmi") ?? events[0] ?? null
            }
            onPreviewClick={(id) => setSelectedId(id)}
          />
        )}
      </section>

      {/* ---- Substrate footer ---- */}
      <section className="patient-record__substrate">
        <div className="patient-record__substrate-stat">
          <span className="t-meta">Source fields collapsed</span>
          <span className="patient-record__substrate-value">
            {payload.source_field_count.toLocaleString()}
          </span>
          <span className="patient-record__substrate-hint">
            distinct raw survey IDs unified into this record
          </span>
        </div>
        <div className="patient-record__substrate-stat">
          <span className="t-meta">FHIR resources</span>
          <span className="patient-record__substrate-value">
            {payload.fhir_resource_count.toLocaleString()}
          </span>
          <span className="patient-record__substrate-hint">
            exportable today via /export/{header.user_id}/fhir
          </span>
        </div>
        <div className="patient-record__substrate-meds">
          <span className="t-meta">Dose progression</span>
          <ul>
            {medSpans.map((span, i) => (
              <li key={i}>
                <span className="patient-record__med-name">
                  {span.name}
                  {span.dosage ? ` · ${span.dosage}` : ""}
                </span>
                <span className="patient-record__med-dates">
                  {span.started.slice(0, 10)}
                  {" → "}
                  {span.ended ? span.ended.slice(0, 10) : "ongoing"}
                </span>
              </li>
            ))}
          </ul>
        </div>
      </section>
    </div>
  );
}

// ---------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------

function SubstrateLineage({ payload }: { payload: PatientRecordPayload }) {
  const approved = payload.events.filter(
    (e) => e.review_status === "approved",
  ).length;
  const total = payload.events.length;
  const visibleEventSummary = summarizeEventCounts(payload.events);
  const fullyApproved = total > 0 && approved === total;

  return (
    <div className="patient-record__lineage" role="group" aria-label="Substrate lineage">
      <LineageStep
        tag="raw source fields"
        value={payload.source_field_count.toLocaleString()}
        hint="distinct survey IDs at intake"
      />
      <span className="patient-record__lineage-arrow" aria-hidden>→</span>
      <LineageStep
        tag="unified record"
        value="1"
        hint={visibleEventSummary}
        emphasis
      />
      <span className="patient-record__lineage-arrow" aria-hidden>→</span>
      <LineageStep
        tag="clinician-signed"
        // When the substrate is in its pitch-ready state every event
        // belongs to an approved category, so a ratio reads as a
        // confident claim. The fallback keeps the framing honest if
        // some categories revert to pending.
        value={fullyApproved ? `${total}/${total}` : `${approved}/${total}`}
        hint={
          fullyApproved
            ? "HITL sign-off complete"
            : "HITL sign-off in progress"
        }
      />
      <span className="patient-record__lineage-arrow" aria-hidden>→</span>
      <LineageStep
        tag="FHIR resources"
        value={payload.fhir_resource_count.toLocaleString()}
        hint="exportable today"
      />
    </div>
  );
}

function LineageStep({
  tag,
  value,
  hint,
  emphasis = false,
}: {
  tag: string;
  value: string;
  hint: string;
  emphasis?: boolean;
}) {
  return (
    <div
      className={`patient-record__lineage-step ${
        emphasis ? "patient-record__lineage-step--emphasis" : ""
      }`}
    >
      <span className="patient-record__lineage-tag">{tag}</span>
      <span className="patient-record__lineage-value">{value}</span>
      <span className="patient-record__lineage-hint">{hint}</span>
    </div>
  );
}

function summarizeEventCounts(events: PatientEvent[]): string {
  const counts: Record<string, number> = {};
  for (const e of events) counts[e.track] = (counts[e.track] || 0) + 1;
  const parts: string[] = [];
  if (counts.bmi) parts.push(`${counts.bmi} BMI`);
  if (counts.medication) parts.push(`${counts.medication} Rx`);
  if (counts.side_effect) parts.push(`${counts.side_effect} side effect`);
  if (counts.condition) parts.push(`${counts.condition} condition${counts.condition > 1 ? "s" : ""}`);
  if (counts.quality) parts.push(`${counts.quality} quality`);
  return parts.slice(0, 3).join(" · ");
}

function HoverTooltip({
  event,
  xPct,
  yPct,
}: {
  event: PatientEvent;
  xPct: number;
  yPct: number;
}) {
  const left = Math.min(Math.max(xPct, 8), 92);
  return (
    <div
      className="patient-record__tooltip"
      style={{ left: `${left}%`, top: `${yPct}%` }}
      role="tooltip"
    >
      <div className="patient-record__tooltip-meta">
        {TRACK_LABEL[event.track]} · {event.timestamp.slice(0, 10)}
      </div>
      <div className="patient-record__tooltip-label">{event.label}</div>
      {event.detail && (
        <div className="patient-record__tooltip-detail">{event.detail}</div>
      )}
    </div>
  );
}

function SelectedEventCard({
  event,
  patientId,
  onClose,
  onAnnotationCreated,
}: {
  event: PatientEvent;
  patientId: number;
  onClose: () => void;
  onAnnotationCreated: (ann: ClinicalAnnotation) => void;
}) {
  const isAnnotation = event.track === "annotation";
  const reviewClass =
    event.review_status === "approved"
      ? "patient-record__review--approved"
      : event.review_status === "overridden"
        ? "patient-record__review--overridden"
        : event.review_status === "rejected"
          ? "patient-record__review--rejected"
          : "patient-record__review--pending";
  const reviewLabel = isAnnotation
    ? "Clinician contribution"
    : event.review_status === "approved"
      ? "Approved by clinician"
      : event.review_status === "overridden"
        ? "Overridden by clinician"
        : event.review_status === "rejected"
          ? "Rejected by clinician"
          : "Awaiting clinical sign-off";

  return (
    <div
      className={`patient-record__detail-card ${
        isAnnotation ? "patient-record__detail-card--annotation" : ""
      }`}
      key={event.id}
    >
      <div className="patient-record__detail-head">
        <div className="patient-record__detail-head-main">
          <div className="t-meta">
            {TRACK_LABEL[event.track]} · {event.timestamp.slice(0, 10)}
          </div>
          <div className="patient-record__detail-label">{event.label}</div>
          {event.detail && (
            <div className="patient-record__detail-sub">{event.detail}</div>
          )}
        </div>
        <div className="patient-record__detail-head-actions">
          <div className={`patient-record__review ${reviewClass}`}>
            <span className="patient-record__review-dot" aria-hidden />
            {reviewLabel}
          </div>
          <button
            type="button"
            className="patient-record__detail-close"
            onClick={onClose}
            aria-label="Close detail"
          >
            ×
          </button>
        </div>
      </div>

      <div className="patient-record__provenance">
        <ProvenanceStep
          num="01"
          label="Captured as"
          value={event.source_field || "—"}
          sub={
            isAnnotation
              ? "Pinned to event in timeline"
              : "Raw source field at intake"
          }
        />
        <div className="patient-record__provenance-arrow" aria-hidden>→</div>
        <ProvenanceStep
          num="02"
          label="Normalised category"
          value={event.source_category || "—"}
          sub={
            isAnnotation
              ? "Living-substrate write-back"
              : "AI-discovered clinical category"
          }
        />
        <div className="patient-record__provenance-arrow" aria-hidden>→</div>
        <ProvenanceStep
          num="03"
          label={isAnnotation ? "Author" : "Standard code"}
          value={
            isAnnotation
              ? event.detail || "Clinician"
              : event.code_system && event.code
                ? `${event.code_system} ${event.code}`
                : "—"
          }
          sub={
            isAnnotation
              ? "Authored on the substrate"
              : "FHIR-mappable terminology code"
          }
        />
      </div>

      {!isAnnotation && (
        <AnnotationComposer
          // Re-key on eventId so the composer state (open / draft note /
          // busy / error) resets when the user clicks a different
          // event. Avoids cross-event leakage without a state-reset
          // useEffect — keys are React's idiomatic remount mechanism.
          key={event.id}
          patientId={patientId}
          eventId={event.id}
          eventLabel={event.label}
          onCreated={onAnnotationCreated}
        />
      )}
    </div>
  );
}

function AnnotationComposer({
  patientId,
  eventId,
  eventLabel,
  onCreated,
}: {
  patientId: number;
  eventId: string;
  eventLabel: string;
  onCreated: (ann: ClinicalAnnotation) => void;
}) {
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    if (open) {
      // Defer focus until the textarea is in the DOM after the open
      // toggle. requestAnimationFrame avoids racing with layout.
      requestAnimationFrame(() => textareaRef.current?.focus());
    }
  }, [open]);
  // Cross-event reset is handled by `key={event.id}` on the parent JSX
  // — when the selected event changes, React unmounts + remounts this
  // component, which discards open / note / busy / error state for free.

  const submit = async () => {
    const trimmed = note.trim();
    if (!trimmed || busy) return;
    setBusy(true);
    setError(null);
    const payload: ClinicalAnnotationCreate = {
      note: trimmed,
      event_id: eventId,
      category: "clinical_note",
    };
    try {
      const res = await fetch(`/api/uniq/patients/${patientId}/annotations`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        // Parse the FastAPI error envelope (`{detail: "..."}`) so the
        // user sees a human-readable line instead of raw JSON. Falls
        // back to status text if the body isn't JSON or has no detail.
        const raw = await res.text().catch(() => "");
        let humanMessage = `Save failed (${res.status})`;
        try {
          const parsed = JSON.parse(raw) as { detail?: unknown };
          if (typeof parsed.detail === "string" && parsed.detail.trim()) {
            humanMessage = parsed.detail;
          }
        } catch {
          if (raw.trim()) humanMessage = raw.trim().slice(0, 200);
        }
        if (res.status === 404) {
          humanMessage =
            "Backend route not found — restart uvicorn so the annotation endpoints register.";
        }
        throw new Error(humanMessage);
      }
      const created = (await res.json()) as ClinicalAnnotation;
      onCreated(created);
      setOpen(false);
      setNote("");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  if (!open) {
    return (
      <div className="annotation-composer annotation-composer--collapsed">
        <button
          type="button"
          className="annotation-composer__open"
          onClick={() => setOpen(true)}
        >
          ✎ Add clinical note
        </button>
        <span className="annotation-composer__hint">
          Pinned to <code>{eventLabel.slice(0, 40)}</code>
        </span>
      </div>
    );
  }

  return (
    <div className="annotation-composer annotation-composer--open">
      <div className="annotation-composer__head">
        <span className="t-eyebrow">add clinical note</span>
        <span className="annotation-composer__pin">
          ↳ pinned to <code>{eventLabel.slice(0, 50)}</code>
        </span>
      </div>
      <textarea
        ref={textareaRef}
        className="annotation-composer__input"
        value={note}
        onChange={(e) => setNote(e.target.value)}
        placeholder="Patient context, follow-up reasoning, off-substrate observation…"
        rows={3}
        maxLength={2000}
        disabled={busy}
        onKeyDown={(e) => {
          if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
            e.preventDefault();
            void submit();
          }
        }}
      />
      {error && (
        <div className="annotation-composer__error" role="alert">
          {error}
        </div>
      )}
      <div className="annotation-composer__actions">
        <span className="annotation-composer__author">
          ✎ Dr. M. Hassan · Clinical Reviewer
        </span>
        <div className="annotation-composer__buttons">
          <button
            type="button"
            className="annotation-composer__cancel"
            onClick={() => {
              setOpen(false);
              setNote("");
              setError(null);
            }}
            disabled={busy}
          >
            Cancel
          </button>
          <button
            type="button"
            className="annotation-composer__save"
            onClick={() => void submit()}
            disabled={busy || !note.trim()}
          >
            {busy ? "Saving…" : "Save note"}
          </button>
        </div>
      </div>
    </div>
  );
}

function annotationToEvent(ann: ClinicalAnnotation): PatientEvent {
  const categoryLabel = ann.category.replace(/_/g, " ");
  return {
    id: ann.id,
    track: "annotation",
    timestamp: ann.created_at,
    label: ann.note.length > 120 ? `${ann.note.slice(0, 117)}...` : ann.note,
    detail: `${ann.author} · ${categoryLabel}`,
    severity: "info",
    value: null,
    source_field: ann.event_id || "patient-level",
    source_category: "CLINICAL_ANNOTATION",
    code_system: null,
    code: null,
    review_status: "approved",
  };
}

function ProvenanceStep({
  num,
  label,
  value,
  sub,
}: {
  num: string;
  label: string;
  value: string;
  sub: string;
}) {
  return (
    <div className="patient-record__provenance-step">
      <div className="patient-record__provenance-num-wrap">
        <span className="patient-record__provenance-num">{num}</span>
      </div>
      <div className="patient-record__provenance-body">
        <span className="t-meta">{label}</span>
        <code className="patient-record__provenance-code">{value}</code>
        <span className="patient-record__provenance-sub">{sub}</span>
      </div>
    </div>
  );
}

function EmptyDetailHint({
  firstEvent,
  onPreviewClick,
}: {
  firstEvent: PatientEvent | null;
  onPreviewClick: (id: string) => void;
}) {
  return (
    <div className="patient-record__detail-empty">
      <div className="patient-record__detail-empty-copy">
        <span className="t-meta">Audit trail · click any event</span>
        <span className="patient-record__detail-empty-hint">
          Each dot opens its full audit trail — raw source field, clinical
          category, medical code, and the HITL sign-off that gated it
          into the substrate.
        </span>
      </div>
      {firstEvent && (
        <button
          type="button"
          className="patient-record__detail-empty-cta"
          onClick={() => onPreviewClick(firstEvent.id)}
        >
          <span className="patient-record__detail-empty-cta-arrow">→</span>
          Preview&nbsp;
          <strong>{firstEvent.label}</strong>
        </button>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------

interface MonthLabel {
  iso: string;
  label: string;
  x: number;
}

const SHORT_MONTHS = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];

function buildMonthLabels(min: number, max: number): MonthLabel[] {
  const span = max - min;
  if (span <= 0) return [];
  const start = new Date(min);
  start.setUTCDate(1);
  start.setUTCHours(0, 0, 0, 0);
  const labels: MonthLabel[] = [];
  const cursor = new Date(start);
  while (cursor.getTime() <= max) {
    const t = cursor.getTime();
    const x = ((t - min) / span) * 100;
    if (x >= 0 && x <= 100) {
      const month = SHORT_MONTHS[cursor.getUTCMonth()];
      const showYear = cursor.getUTCMonth() === 0 || labels.length === 0;
      labels.push({
        iso: cursor.toISOString(),
        label: showYear
          ? `${month} ’${String(cursor.getUTCFullYear()).slice(2)}`
          : month,
        x,
      });
    }
    cursor.setUTCMonth(cursor.getUTCMonth() + 1);
  }
  if (labels.length >= 12) {
    return labels.filter((_, i) => i % 2 === 0);
  }
  return labels;
}

interface MedSpan {
  name: string;
  dosage: string | null;
  started: string;
  ended: string | null;
  segmentCount: number;
}

function collapseMedSpans(meds: PatientMedicationSegment[]): MedSpan[] {
  if (meds.length === 0) return [];
  const sorted = [...meds].sort((a, b) =>
    a.started.localeCompare(b.started),
  );
  const out: MedSpan[] = [];
  for (const m of sorted) {
    const last = out[out.length - 1];
    const sameProduct =
      last && last.name === m.name && (last.dosage ?? "") === (m.dosage ?? "");
    if (sameProduct) {
      last.segmentCount += 1;
      if (m.ended === null) {
        last.ended = null;
      } else if (last.ended !== null && m.ended.localeCompare(last.ended) > 0) {
        last.ended = m.ended;
      }
    } else {
      out.push({
        name: m.name,
        dosage: m.dosage,
        started: m.started,
        ended: m.ended,
        segmentCount: 1,
      });
    }
  }
  return out;
}

// WHO BMI categories (adult).
function bmiCategory(value: number): string {
  if (value < 18.5) return "underweight";
  if (value < 25) return "normal weight";
  if (value < 30) return "overweight";
  if (value < 35) return "class I obesity";
  if (value < 40) return "class II obesity";
  return "class III obesity";
}
