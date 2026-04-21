"use client";

import { useMemo } from "react";
import type { DashboardPayload } from "@/lib/demo/recipes";

/**
 * Dashboard-artifact renderer.
 *
 * Pure presentation: KPI strip + SVG BMI trajectory + cohort table.
 * Phase 6 feeds real `DashboardPayload` from the agent; the Clinical
 * Ledger styling lives in globals.css (.dash-kpis, .chart, .cohort-table).
 */
export function ArtifactDashboard({ payload }: { payload: DashboardPayload }) {
  const { kpis, trajectoryPoints, cohortTable } = payload;

  const path = useMemo(() => {
    const w = 100;
    const h = 60;
    const max = Math.max(...trajectoryPoints) + 1;
    const min = Math.min(...trajectoryPoints) - 1;
    const coords = trajectoryPoints.map<[number, number]>((v, i) => [
      (i / (trajectoryPoints.length - 1)) * w,
      h - ((v - min) / (max - min)) * h,
    ]);
    const d = coords
      .map(([x, y], i) => (i === 0 ? `M ${x} ${y}` : `L ${x} ${y}`))
      .join(" ");
    const area = `${d} L ${w} ${h} L 0 ${h} Z`;
    return { d, area, coords };
  }, [trajectoryPoints]);

  return (
    <div>
      <div className="dash-kpis">
        {kpis.map((k) => (
          <div className="dash-kpi" key={k.label}>
            <div className="dash-kpi__label">{k.label}</div>
            <div className="dash-kpi__value">{k.value}</div>
            <div
              className={`dash-kpi__delta ${k.deltaDirection === "down" ? "is-down" : ""}`}
            >
              {k.delta}
            </div>
          </div>
        ))}
      </div>

      <div className="chart">
        <div className="chart__head">
          <div className="chart__title">BMI trajectory — Mounjaro cohort</div>
          <div className="chart__sub">
            weeks 0 — 24 · n = {kpis.find((k) => k.label.includes("Cohort"))?.value ?? "—"}
          </div>
        </div>
        <svg className="chart__svg" viewBox="0 0 100 60" preserveAspectRatio="none">
          {[0, 15, 30, 45, 60].map((y) => (
            <line
              key={y}
              x1="0"
              y1={y}
              x2="100"
              y2={y}
              stroke="var(--rule-soft)"
              strokeWidth="0.15"
            />
          ))}
          <path d={path.area} fill="var(--signal-wash)" opacity={0.6} />
          <path
            d={path.d}
            fill="none"
            stroke="var(--signal-ink)"
            strokeWidth="0.5"
            vectorEffect="non-scaling-stroke"
          />
          {path.coords.map(([x, y], i) => (
            <circle
              key={i}
              cx={x}
              cy={y}
              r="0.6"
              fill="var(--paper-rise)"
              stroke="var(--signal-ink)"
              strokeWidth="0.3"
            />
          ))}
        </svg>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            padding: "6px 16px 14px",
            fontFamily: "var(--f-mono)",
            fontSize: 10,
            color: "var(--ink-3)",
            letterSpacing: "0.08em",
          }}
        >
          <span>W0</span>
          <span>W4</span>
          <span>W8</span>
          <span>W12</span>
          <span>W16</span>
          <span>W20</span>
          <span>W24</span>
        </div>
      </div>

      <table className="cohort-table">
        <thead>
          <tr>
            <th>Patient ID</th>
            <th>Dose</th>
            <th>BMI · W0</th>
            <th>BMI · W24</th>
            <th>Δ</th>
            <th>Adherence</th>
          </tr>
        </thead>
        <tbody>
          {cohortTable.map((row) => (
            <tr key={row.patient}>
              <td>{row.patient}</td>
              <td>{row.dose}</td>
              <td>{row.bmiBaseline}</td>
              <td>{row.bmiLatest}</td>
              <td style={{ color: "var(--signal-ink)" }}>{row.delta}</td>
              <td>{row.adherence}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
