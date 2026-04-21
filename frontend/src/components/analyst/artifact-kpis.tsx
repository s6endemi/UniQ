"use client";

import type { Kpi } from "@/lib/api";

/**
 * KPI strip — shared primitive for cohort_trend, alerts_table, and the
 * optional header of a plain `table` artifact. Four-column grid on
 * wide canvases; the CSS collapses gracefully on narrower surfaces.
 *
 * `delta_direction` is consulted only for the "down" red-ink treatment;
 * "up" and "neutral" render identically because we don't want the
 * Clinical Ledger covered in green chevrons. When the caller wants a
 * decline to *not* read as alarm (e.g., falling BMI), they should omit
 * the direction and let the delta string itself carry the sign.
 */
export function ArtifactKpis({ kpis }: { kpis: Kpi[] }) {
  if (kpis.length === 0) return null;
  return (
    <div className="dash-kpis">
      {kpis.map((k) => (
        <div className="dash-kpi" key={k.label}>
          <div className="dash-kpi__label">{k.label}</div>
          <div className="dash-kpi__value">{k.value}</div>
          {k.delta && (
            <div
              className={`dash-kpi__delta ${k.delta_direction === "down" ? "is-down" : ""}`}
            >
              {k.delta}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
