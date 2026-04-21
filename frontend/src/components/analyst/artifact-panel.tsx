"use client";

import { AnimatePresence, motion } from "motion/react";
import { X, Download, FileJson, TableProperties, ChartLine } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export type Artifact =
  | {
      id: string;
      kind: "fhir";
      title: string;
      subtitle?: string;
      bundle: Record<string, unknown>;
    }
  | {
      id: string;
      kind: "table";
      title: string;
      subtitle?: string;
      columns: string[];
      rows: Array<Record<string, unknown>>;
    }
  | {
      id: string;
      kind: "chart";
      title: string;
      subtitle?: string;
      chartSpec: Record<string, unknown>;
    };

const KIND_META = {
  fhir: { icon: FileJson, label: "FHIR Bundle" },
  table: { icon: TableProperties, label: "Cohort" },
  chart: { icon: ChartLine, label: "Chart" },
} as const;

interface ArtifactPanelProps {
  artifact: Artifact | null;
  onClose: () => void;
}

export function ArtifactPanel({ artifact, onClose }: ArtifactPanelProps) {
  return (
    <AnimatePresence>
      {artifact && (
        <motion.aside
          initial={{ x: "100%", opacity: 0.7 }}
          animate={{ x: 0, opacity: 1 }}
          exit={{ x: "100%", opacity: 0 }}
          transition={{ type: "spring", stiffness: 300, damping: 34 }}
          className="flex h-full w-full max-w-xl flex-col border-l border-ink-700 bg-ink-900"
        >
          <ArtifactHeader artifact={artifact} onClose={onClose} />
          <div className="flex-1 overflow-y-auto">
            {artifact.kind === "fhir" && <FhirRenderer bundle={artifact.bundle} />}
            {artifact.kind === "table" && (
              <TableRenderer columns={artifact.columns} rows={artifact.rows} />
            )}
            {artifact.kind === "chart" && <ChartRendererPlaceholder spec={artifact.chartSpec} />}
          </div>
          <ArtifactFooter artifact={artifact} />
        </motion.aside>
      )}
    </AnimatePresence>
  );
}

function ArtifactHeader({
  artifact,
  onClose,
}: {
  artifact: Artifact;
  onClose: () => void;
}) {
  const meta = KIND_META[artifact.kind];
  const Icon = meta.icon;
  return (
    <div className="flex items-start justify-between gap-4 border-b border-ink-700 p-5">
      <div className="space-y-2">
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge tone="glacial">
            <Icon className="h-2.5 w-2.5" />
            {meta.label}
          </Badge>
        </div>
        <h2 className="font-display text-xl font-semibold leading-tight text-text-0">
          {artifact.title}
        </h2>
        {artifact.subtitle && (
          <p className="text-xs text-text-3">{artifact.subtitle}</p>
        )}
      </div>
      <button
        onClick={onClose}
        className="rounded-md p-1.5 text-text-3 hover:bg-ink-800 hover:text-text-0"
        aria-label="Close artifact"
      >
        <X className="h-5 w-5" />
      </button>
    </div>
  );
}

function ArtifactFooter({ artifact }: { artifact: Artifact }) {
  const download = () => {
    const payload =
      artifact.kind === "fhir"
        ? JSON.stringify(artifact.bundle, null, 2)
        : artifact.kind === "table"
          ? JSON.stringify({ columns: artifact.columns, rows: artifact.rows }, null, 2)
          : JSON.stringify(artifact.chartSpec, null, 2);
    const blob = new Blob([payload], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${artifact.id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };
  return (
    <div className="border-t border-ink-700 p-4">
      <Button variant="secondary" size="sm" onClick={download}>
        <Download className="h-3.5 w-3.5" />
        Download JSON
      </Button>
    </div>
  );
}

function FhirRenderer({ bundle }: { bundle: Record<string, unknown> }) {
  const text = JSON.stringify(bundle, null, 2);
  // Rough syntax highlight for keys. Keeps it dependency-free.
  const lines = text.split("\n");
  return (
    <pre className="px-5 py-4 font-mono text-[11px] leading-relaxed text-text-1">
      {lines.map((line, i) => {
        const keyMatch = line.match(/^(\s*)"([^"]+)":(.*)$/);
        if (keyMatch) {
          return (
            <div key={i}>
              <span>{keyMatch[1]}</span>
              <span className="text-glacial">&quot;{keyMatch[2]}&quot;</span>
              <span className="text-text-3">:</span>
              <span>{keyMatch[3]}</span>
            </div>
          );
        }
        return <div key={i}>{line}</div>;
      })}
    </pre>
  );
}

function TableRenderer({
  columns,
  rows,
}: {
  columns: string[];
  rows: Array<Record<string, unknown>>;
}) {
  return (
    <div className="overflow-x-auto p-5">
      <table className="w-full min-w-full text-sm">
        <thead>
          <tr className="border-b border-ink-700">
            {columns.map((c) => (
              <th
                key={c}
                className="px-3 py-2 text-left font-mono text-[10px] uppercase tracking-wider text-text-3"
              >
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-b border-ink-800/60">
              {columns.map((c) => (
                <td key={c} className="px-3 py-2 font-mono text-[12px] text-text-1">
                  {String(row[c] ?? "")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ChartRendererPlaceholder({ spec }: { spec: Record<string, unknown> }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 p-8 text-center">
      <ChartLine className="h-10 w-10 text-glacial/60" />
      <p className="text-sm text-text-2">
        Chart renderer arrives in phase 6. Spec available for download.
      </p>
      <pre className="mt-4 max-h-64 overflow-auto rounded-md border border-ink-700 bg-ink-850 px-3 py-2 font-mono text-[10px] text-text-3">
        {JSON.stringify(spec, null, 2)}
      </pre>
    </div>
  );
}
