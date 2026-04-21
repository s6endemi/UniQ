"use client";

import { AnimatePresence, motion } from "motion/react";
import { Check, X, Pencil } from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { MappingEntry, MappingUpdate } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

interface MappingDrawerProps {
  entry: MappingEntry | null;
  onClose: () => void;
}

async function patchMapping(category: string, update: MappingUpdate): Promise<MappingEntry> {
  const res = await fetch(`/api/uniq/mapping/${encodeURIComponent(category)}`, {
    method: "PATCH",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(update),
  });
  if (!res.ok) throw new Error(`PATCH failed: ${res.status}`);
  return res.json();
}

export function MappingDrawer({ entry, onClose }: MappingDrawerProps) {
  const qc = useQueryClient();

  const mutation = useMutation({
    mutationFn: ({ category, update }: { category: string; update: MappingUpdate }) =>
      patchMapping(category, update),
    onSuccess: (updated) => {
      // Update the list cache in place so the card reflects new status instantly
      qc.setQueryData<MappingEntry[]>(["mapping"], (old) =>
        old ? old.map((e) => (e.category === updated.category ? updated : e)) : old,
      );
    },
  });

  const approve = () =>
    entry && mutation.mutate({ category: entry.category, update: { review_status: "approved" } });
  const reject = () =>
    entry && mutation.mutate({ category: entry.category, update: { review_status: "rejected" } });

  return (
    <AnimatePresence>
      {entry && (
        <>
          {/* Backdrop */}
          <motion.div
            className="fixed inset-0 z-40 bg-ink-950/60 backdrop-blur-sm"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />

          {/* Drawer */}
          <motion.aside
            className="fixed right-0 top-0 z-50 flex h-full w-full max-w-xl flex-col border-l border-ink-700 bg-ink-900 shadow-2xl"
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", stiffness: 300, damping: 32 }}
          >
            {/* Header */}
            <div className="flex items-start justify-between gap-4 border-b border-ink-700 p-6">
              <div className="space-y-2">
                <div className="flex flex-wrap gap-1.5">
                  <Badge
                    tone={
                      entry.confidence === "high"
                        ? "mineral"
                        : entry.confidence === "medium"
                          ? "amber"
                          : "coral"
                    }
                  >
                    {entry.confidence} confidence
                  </Badge>
                  <Badge tone="glacial">{entry.fhir_resource_type}</Badge>
                  <Badge
                    tone={
                      entry.review_status === "approved"
                        ? "mineral"
                        : entry.review_status === "rejected"
                          ? "coral"
                          : entry.review_status === "overridden"
                            ? "glacial"
                            : "amber"
                    }
                  >
                    {entry.review_status}
                  </Badge>
                </div>
                <h2 className="font-display text-2xl font-semibold tracking-tight text-text-0">
                  {entry.display_label}
                </h2>
                <p className="font-mono text-xs text-text-3">{entry.category}</p>
              </div>
              <button
                onClick={onClose}
                className="rounded-md p-1.5 text-text-3 hover:bg-ink-800 hover:text-text-0"
                aria-label="Close"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Body */}
            <div className="flex-1 space-y-6 overflow-y-auto p-6">
              {entry.standard_concept && (
                <Section title="Standard concept">
                  <code className="font-mono text-sm text-glacial">{entry.standard_concept}</code>
                </Section>
              )}

              {entry.fhir_category && (
                <Section title="FHIR category">
                  <code className="font-mono text-sm text-text-1">{entry.fhir_category}</code>
                </Section>
              )}

              {entry.codes.length > 0 && (
                <Section title={`Clinical codes (${entry.codes.length})`}>
                  <div className="space-y-2">
                    {entry.codes.map((c) => (
                      <div
                        key={`${c.system}-${c.code}`}
                        className="flex items-start gap-3 rounded-md border border-ink-700 bg-ink-850 p-3"
                      >
                        <Badge tone="neutral">{shortSystem(c.system)}</Badge>
                        <div className="flex-1 space-y-0.5">
                          <div className="font-mono text-sm text-text-0">{c.code}</div>
                          {c.display && (
                            <div className="text-xs text-text-2">{c.display}</div>
                          )}
                          <div className="font-mono text-[10px] text-text-3">{c.system}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </Section>
              )}

              {entry.reasoning && (
                <Section title="AI reasoning">
                  <p className="text-sm leading-relaxed text-text-1">{entry.reasoning}</p>
                </Section>
              )}

              {entry.validation_errors && entry.validation_errors.length > 0 && (
                <Section title="Validation notes">
                  <ul className="space-y-1 text-sm text-coral">
                    {entry.validation_errors.map((e) => (
                      <li key={e} className="font-mono">
                        · {e}
                      </li>
                    ))}
                  </ul>
                </Section>
              )}
            </div>

            {/* Actions */}
            <div className="border-t border-ink-700 bg-ink-900 p-6">
              {mutation.error && (
                <div className="mb-3 rounded-md border border-coral/30 bg-coral/10 px-3 py-2 text-xs text-coral">
                  {(mutation.error as Error).message}
                </div>
              )}
              <div className="flex gap-2">
                <Button
                  variant="approve"
                  size="md"
                  className="flex-1"
                  onClick={approve}
                  disabled={mutation.isPending || entry.review_status === "approved"}
                >
                  <Check className="h-4 w-4" />
                  Approve
                </Button>
                <Button
                  variant="secondary"
                  size="md"
                  className="flex-1"
                  disabled
                  title="Override editor coming in phase polish"
                >
                  <Pencil className="h-4 w-4" />
                  Override
                </Button>
                <Button
                  variant="reject"
                  size="md"
                  className="flex-1"
                  onClick={reject}
                  disabled={mutation.isPending || entry.review_status === "rejected"}
                >
                  <X className="h-4 w-4" />
                  Reject
                </Button>
              </div>
              <p className="mt-3 text-[11px] text-text-3">
                Approved or rejected decisions persist across pipeline re-runs. Your
                review is the authoritative record.
              </p>
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="mb-2 font-mono text-[10px] uppercase tracking-[0.18em] text-text-3">
        {title}
      </h3>
      {children}
    </div>
  );
}

function shortSystem(system: string): string {
  if (system.includes("loinc")) return "LOINC";
  if (system.includes("snomed")) return "SNOMED";
  if (system.includes("icd-10") || system.includes("icd10")) return "ICD-10";
  if (system.includes("rxnorm")) return "RxNorm";
  if (system.includes("whocc") || system.includes("atc")) return "ATC";
  return system.split("/").pop() ?? system;
}
