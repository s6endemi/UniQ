"use client";

import type { TablePayload } from "@/lib/api";
import { ArtifactKpis } from "./artifact-kpis";
import { ArtifactTable } from "./artifact-table-view";

/**
 * Generic `table` artifact — the degraded/fallback surface when a
 * query does not cleanly fit a richer template. KPIs are optional; the
 * table is always present (possibly empty).
 */
export function ArtifactPlainTable({ payload }: { payload: TablePayload }) {
  return (
    <div>
      {payload.kpis && payload.kpis.length > 0 && <ArtifactKpis kpis={payload.kpis} />}
      <ArtifactTable data={payload.table} />
    </div>
  );
}
