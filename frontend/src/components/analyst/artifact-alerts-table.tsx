"use client";

import type { AlertsTablePayload } from "@/lib/api";
import { ArtifactKpis } from "./artifact-kpis";
import { ArtifactTable } from "./artifact-table-view";

export function ArtifactAlertsTable({ payload }: { payload: AlertsTablePayload }) {
  return (
    <div>
      <ArtifactKpis kpis={payload.kpis} />
      <ArtifactTable data={payload.table} />
    </div>
  );
}
