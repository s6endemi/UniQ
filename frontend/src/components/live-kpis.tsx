"use client";

import { useQuery } from "@tanstack/react-query";
import { motion } from "motion/react";
import type { HealthResponse } from "@/lib/api";
import { cn } from "@/lib/utils";

async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch("/api/uniq/health");
  if (!res.ok) throw new Error("health unreachable");
  return res.json();
}

interface KpiTile {
  label: string;
  value: number | string;
  detail?: string;
  hue?: "glacial" | "mineral" | "amber";
}

function Tile({ label, value, detail, hue = "glacial" }: KpiTile) {
  const accent =
    hue === "mineral" ? "text-mineral" : hue === "amber" ? "text-amber" : "text-glacial";

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="rounded-lg border border-ink-700 bg-ink-900/60 p-5 backdrop-blur-sm"
    >
      <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-3">
        {label}
      </div>
      <div className={cn("mt-2 font-display text-3xl font-semibold tabular-nums", accent)}>
        {value}
      </div>
      {detail && <div className="mt-1 text-xs text-text-3">{detail}</div>}
    </motion.div>
  );
}

export function LiveKpis() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    refetchInterval: 10_000,
  });

  if (isLoading) {
    return (
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="h-[110px] animate-pulse rounded-lg border border-ink-700 bg-ink-900/40"
          />
        ))}
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="rounded-lg border border-amber/40 bg-amber/10 px-4 py-3 text-sm text-amber">
        Backend unreachable — start FastAPI:{" "}
        <code className="font-mono text-xs">
          .venv\Scripts\python -m uvicorn src.api.main:app --port 8000
        </code>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
      <Tile
        label="patients"
        value={data.patients.toLocaleString()}
        detail="unified across brands"
        hue="glacial"
      />
      <Tile
        label="categories"
        value={data.categories}
        detail="AI-discovered"
        hue="glacial"
      />
      <Tile
        label="mappings"
        value={data.mapping_entries}
        detail="advisory + reviewed"
        hue="mineral"
      />
      <Tile
        label="status"
        value={data.status === "ok" ? "operational" : "degraded"}
        detail={data.artifacts_loaded ? "artifacts loaded" : "pipeline not run"}
        hue={data.status === "ok" ? "mineral" : "amber"}
      />
    </div>
  );
}
