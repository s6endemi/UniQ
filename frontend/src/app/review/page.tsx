"use client";

import { Suspense, useMemo, useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { motion } from "motion/react";
import type { MappingEntry } from "@/lib/api";
import { MappingCard } from "@/components/review/mapping-card";
import { MappingDrawer } from "@/components/review/mapping-drawer";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

async function fetchMapping(): Promise<MappingEntry[]> {
  const res = await fetch("/api/uniq/mapping");
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? `mapping unreachable (${res.status})`);
  }
  return res.json();
}

const CONFIDENCE_ORDER: Array<MappingEntry["confidence"]> = ["high", "medium", "low"];

const CONFIDENCE_COPY = {
  high: {
    title: "High confidence",
    sub: "Ready for auto-use after a glance.",
    tone: "mineral" as const,
  },
  medium: {
    title: "Medium confidence",
    sub: "Review before it feeds runtime pipelines.",
    tone: "amber" as const,
  },
  low: {
    title: "Low confidence",
    sub: "Human decision required — AI flagged composite or unclear intent.",
    tone: "coral" as const,
  },
};

type StatusFilter = "all" | MappingEntry["review_status"];
const STATUS_FILTERS: Array<{ key: StatusFilter; label: string }> = [
  { key: "all", label: "All" },
  { key: "pending", label: "Pending" },
  { key: "approved", label: "Approved" },
  { key: "overridden", label: "Overridden" },
  { key: "rejected", label: "Rejected" },
];

function ReviewPageInner() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["mapping"],
    queryFn: fetchMapping,
  });

  const router = useRouter();
  const searchParams = useSearchParams();
  const activeCategory = searchParams.get("category");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");

  // Deep-link sync: when ?category=... is set, keep drawer open against
  // the current dataset. If it points to something that no longer exists,
  // clear the query string so the UI doesn't end up stuck.
  const activeEntry: MappingEntry | null = useMemo(() => {
    if (!activeCategory || !data) return null;
    return data.find((e) => e.category === activeCategory) ?? null;
  }, [activeCategory, data]);

  useEffect(() => {
    if (activeCategory && data && !activeEntry) {
      const params = new URLSearchParams(searchParams);
      params.delete("category");
      router.replace(`/review${params.size ? `?${params.toString()}` : ""}`);
    }
  }, [activeCategory, activeEntry, data, router, searchParams]);

  const open = (category: string) => {
    const params = new URLSearchParams(searchParams);
    params.set("category", category);
    router.replace(`/review?${params.toString()}`, { scroll: false });
  };
  const close = () => {
    const params = new URLSearchParams(searchParams);
    params.delete("category");
    router.replace(`/review${params.size ? `?${params.toString()}` : ""}`, { scroll: false });
  };

  const grouped = useMemo(() => {
    const base: Record<MappingEntry["confidence"], MappingEntry[]> = {
      high: [],
      medium: [],
      low: [],
    };
    if (!data) return base;
    for (const entry of data) {
      if (statusFilter !== "all" && entry.review_status !== statusFilter) continue;
      base[entry.confidence].push(entry);
    }
    for (const key of CONFIDENCE_ORDER) {
      base[key].sort((a, b) => a.category.localeCompare(b.category));
    }
    return base;
  }, [data, statusFilter]);

  const totals = useMemo(() => {
    if (!data) return { total: 0, approved: 0, pending: 0, flagged: 0 };
    return {
      total: data.length,
      approved: data.filter((e) => e.review_status === "approved").length,
      pending: data.filter((e) => e.review_status === "pending").length,
      flagged: data.filter((e) => e.confidence === "low").length,
    };
  }, [data]);

  return (
    <div className="mx-auto max-w-7xl px-6 py-16">
      {/* Header */}
      <div className="mb-10 flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
        <div className="space-y-3">
          <h1 className="font-mono text-[11px] uppercase tracking-[0.18em] text-text-3">
            Human in the loop
          </h1>
          <h2 className="font-display text-4xl font-semibold tracking-tight text-text-0 md:text-5xl">
            Review the AI&apos;s work.
          </h2>
          <p className="max-w-2xl text-base leading-relaxed text-text-2">
            Every clinical category the engine discovered is mapped to FHIR
            with a confidence score. Approved or overridden decisions persist
            across future pipeline runs — review once, scale forever.
          </p>
        </div>

        {/* Summary tiles */}
        {data && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
            className="grid grid-cols-4 gap-3 md:w-fit"
          >
            <SummaryTile label="Total" value={totals.total} />
            <SummaryTile label="Approved" value={totals.approved} tone="mineral" />
            <SummaryTile label="Pending" value={totals.pending} tone="amber" />
            <SummaryTile label="Flagged" value={totals.flagged} tone="coral" />
          </motion.div>
        )}
      </div>

      {/* Status filter */}
      <div className="mb-6 flex flex-wrap gap-2">
        {STATUS_FILTERS.map((f) => (
          <button
            key={f.key}
            onClick={() => setStatusFilter(f.key)}
            className={cn(
              "rounded-full border px-3 py-1 font-mono text-[11px] uppercase tracking-wider transition-colors",
              statusFilter === f.key
                ? "border-glacial/60 bg-glacial/10 text-glacial"
                : "border-ink-700 text-text-2 hover:border-ink-600 hover:text-text-1",
            )}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Errors / loading */}
      {error && (
        <div className="rounded-lg border border-coral/40 bg-coral/10 px-4 py-3 text-sm text-coral">
          {(error as Error).message}
        </div>
      )}
      {isLoading && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div
              key={i}
              className="h-40 animate-pulse rounded-lg border border-ink-700 bg-ink-900/40"
            />
          ))}
        </div>
      )}

      {/* Grouped columns */}
      {data && (
        <div className="grid grid-cols-1 gap-10 lg:grid-cols-3">
          {CONFIDENCE_ORDER.map((conf) => {
            const copy = CONFIDENCE_COPY[conf];
            const entries = grouped[conf];
            return (
              <div key={conf} className="space-y-4">
                <div className="space-y-1">
                  <div className="flex items-center justify-between">
                    <h3 className="font-display text-base font-semibold text-text-0">
                      {copy.title}
                    </h3>
                    <Badge tone={copy.tone}>{entries.length}</Badge>
                  </div>
                  <p className="text-xs text-text-3">{copy.sub}</p>
                </div>
                <div className="flex flex-col gap-3">
                  {entries.length === 0 ? (
                    <div className="rounded-md border border-dashed border-ink-700 px-3 py-6 text-center font-mono text-[11px] text-text-3">
                      nothing here
                    </div>
                  ) : (
                    entries.map((e) => (
                      <MappingCard
                        key={e.category}
                        entry={e}
                        active={activeCategory === e.category}
                        onOpen={open}
                      />
                    ))
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      <MappingDrawer entry={activeEntry} onClose={close} />
    </div>
  );
}

function SummaryTile({
  label,
  value,
  tone = "glacial",
}: {
  label: string;
  value: number;
  tone?: "glacial" | "mineral" | "amber" | "coral";
}) {
  const accent =
    tone === "mineral"
      ? "text-mineral"
      : tone === "amber"
        ? "text-amber"
        : tone === "coral"
          ? "text-coral"
          : "text-glacial";
  return (
    <div className="rounded-md border border-ink-700 bg-ink-900/60 px-3 py-2">
      <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-3">
        {label}
      </div>
      <div className={cn("font-display text-2xl font-semibold tabular-nums", accent)}>
        {value}
      </div>
    </div>
  );
}

export default function ReviewPage() {
  return (
    <Suspense fallback={<div className="mx-auto max-w-7xl px-6 py-16 text-text-3">loading…</div>}>
      <ReviewPageInner />
    </Suspense>
  );
}
