"use client";

import { useMemo } from "react";
import type { CohortTrendPayload } from "@/lib/api";
import { ArtifactKpis } from "./artifact-kpis";
import { ArtifactTable } from "./artifact-table-view";

/**
 * Cohort-trend artifact renderer.
 *
 * Handles 1..n line series against a shared X axis — the same layout
 * covers single-cohort trajectories (n=1 series) and Mounjaro-vs-Wegovy
 * comparisons (n=2..3). No other chart grammar is expressed here: the
 * backend's job is to choose *this* template, ours is to draw it well.
 */
export function ArtifactDashboard({ payload }: { payload: CohortTrendPayload }) {
  const { kpis, chart, table } = payload;

  const geometry = useMemo(() => {
    const w = 100;
    const h = 60;
    const flat = chart.series.flatMap((s) => s.points);
    if (flat.length === 0) {
      return { series: [] as Array<{ name: string; d: string; area: string; coords: [number, number][] }>, h };
    }
    const max = Math.max(...flat) + 1;
    const min = Math.min(...flat) - 1;
    const span = Math.max(0.01, max - min);
    const denom = Math.max(1, chart.x_labels.length - 1);
    return {
      series: chart.series.map((s) => {
        const coords = s.points.map<[number, number]>((v, i) => [
          (i / denom) * w,
          h - ((v - min) / span) * h,
        ]);
        const d = coords
          .map(([x, y], i) => (i === 0 ? `M ${x} ${y}` : `L ${x} ${y}`))
          .join(" ");
        const area = `${d} L ${w} ${h} L 0 ${h} Z`;
        return { name: s.name, d, area, coords };
      }),
      h,
    };
  }, [chart.series, chart.x_labels.length]);

  const isCompare = chart.series.length > 1;

  return (
    <div>
      <ArtifactKpis kpis={kpis} />

      <div className="chart">
        <div className="chart__head">
          <div className="chart__title">{chart.title}</div>
          {chart.subtitle && <div className="chart__sub">{chart.subtitle}</div>}
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
          {geometry.series.map((s, idx) => {
            // Compare mode shifts secondary series to a muted ink so the
            // primary series stays legible. Single-series uses the wash
            // fill for the signature "ledger" feel.
            const isPrimary = idx === 0;
            const stroke = isPrimary ? "var(--signal-ink)" : "var(--ink-3)";
            return (
              <g key={s.name}>
                {!isCompare && isPrimary && (
                  <path d={s.area} fill="var(--signal-wash)" opacity={0.6} />
                )}
                <path
                  d={s.d}
                  fill="none"
                  stroke={stroke}
                  strokeWidth="0.5"
                  vectorEffect="non-scaling-stroke"
                />
                {s.coords.map(([x, y], i) => (
                  <circle
                    key={i}
                    cx={x}
                    cy={y}
                    r="0.6"
                    fill="var(--paper-rise)"
                    stroke={stroke}
                    strokeWidth="0.3"
                  />
                ))}
              </g>
            );
          })}
        </svg>

        <div className="chart__axis">
          {chart.x_labels.map((label) => (
            <span key={label}>{label}</span>
          ))}
        </div>

        {isCompare && (
          <div className="chart__legend">
            {chart.series.map((s, idx) => (
              <span key={s.name} className="chart__legend-item">
                <span
                  className="chart__legend-swatch"
                  style={{ background: idx === 0 ? "var(--signal-ink)" : "var(--ink-3)" }}
                />
                {s.name}
              </span>
            ))}
          </div>
        )}
      </div>

      <ArtifactTable data={table} />
    </div>
  );
}
