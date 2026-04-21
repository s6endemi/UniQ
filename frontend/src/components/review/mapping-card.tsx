"use client";

import { motion } from "motion/react";
import { Check, CircleAlert, CircleDashed, X } from "lucide-react";
import type { MappingEntry } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const STATUS_CONFIG = {
  approved: { icon: Check, tone: "mineral", label: "Approved" },
  overridden: { icon: CircleAlert, tone: "glacial", label: "Overridden" },
  rejected: { icon: X, tone: "coral", label: "Rejected" },
  pending: { icon: CircleDashed, tone: "amber", label: "Pending" },
} as const;

const CONFIDENCE_ACCENT = {
  high: "border-mineral/30 hover:border-mineral/60",
  medium: "border-amber/30 hover:border-amber/60",
  low: "border-coral/30 hover:border-coral/60",
} as const;

interface MappingCardProps {
  entry: MappingEntry;
  active?: boolean;
  onOpen: (category: string) => void;
}

export function MappingCard({ entry, active, onOpen }: MappingCardProps) {
  const Status = STATUS_CONFIG[entry.review_status].icon;
  const statusTone = STATUS_CONFIG[entry.review_status].tone;
  const statusLabel = STATUS_CONFIG[entry.review_status].label;
  const primaryCode = entry.codes[0];

  return (
    <motion.button
      layout
      onClick={() => onOpen(entry.category)}
      whileHover={{ y: -2 }}
      transition={{ type: "spring", stiffness: 400, damping: 30 }}
      className={cn(
        "group relative flex w-full flex-col gap-3 rounded-lg border bg-ink-900/50 p-4 text-left",
        "backdrop-blur-sm transition-colors",
        CONFIDENCE_ACCENT[entry.confidence],
        active && "ring-2 ring-glacial/60",
      )}
    >
      {/* Confidence + review-status bar */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge tone={entry.confidence === "high" ? "mineral" : entry.confidence === "medium" ? "amber" : "coral"}>
            {entry.confidence}
          </Badge>
          <Badge tone={statusTone}>
            <Status className="h-2.5 w-2.5" />
            {statusLabel}
          </Badge>
        </div>
        <Badge tone="neutral">{entry.fhir_resource_type}</Badge>
      </div>

      {/* Title */}
      <div>
        <h3 className="font-display text-base font-semibold leading-snug text-text-0">
          {entry.display_label}
        </h3>
        <p className="mt-1 font-mono text-[10px] text-text-3">{entry.category}</p>
      </div>

      {/* Primary code if present */}
      {primaryCode && (
        <div className="flex items-center gap-2 font-mono text-[11px] text-text-2">
          <span className="rounded bg-ink-800 px-1.5 py-0.5 text-text-3">
            {systemLabel(primaryCode.system)}
          </span>
          <span className="truncate">{primaryCode.code}</span>
          {primaryCode.display && (
            <span className="truncate text-text-3">· {primaryCode.display}</span>
          )}
        </div>
      )}

      {/* Confidence-filled hairline at bottom */}
      <div
        className={cn(
          "absolute bottom-0 left-0 right-0 h-[2px] rounded-b-lg opacity-60 transition-opacity group-hover:opacity-100",
          entry.confidence === "high" && "bg-mineral",
          entry.confidence === "medium" && "bg-amber",
          entry.confidence === "low" && "bg-coral",
        )}
      />
    </motion.button>
  );
}

function systemLabel(system: string): string {
  if (system.includes("loinc")) return "LOINC";
  if (system.includes("snomed")) return "SNOMED";
  if (system.includes("icd-10") || system.includes("icd10")) return "ICD-10";
  if (system.includes("rxnorm")) return "RxNorm";
  if (system.includes("whocc") || system.includes("atc")) return "ATC";
  return system.split("/").pop() ?? system;
}
