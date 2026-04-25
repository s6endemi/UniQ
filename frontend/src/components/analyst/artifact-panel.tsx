"use client";

import { useEffect, useState } from "react";
import type { ChatArtifact } from "@/lib/api";
import { ArtifactAlertsTable } from "./artifact-alerts-table";
import { ArtifactDashboard } from "./artifact-dashboard";
import { ArtifactFhir } from "./artifact-fhir";
import { ArtifactPatientRecord } from "./artifact-patient-record";
import { ArtifactPlainTable } from "./artifact-plain-table";

/**
 * Canvas panel on the right of the Analyst when an artifact is open.
 *
 * One dispatch on `artifact.kind` per discriminated-union variant; each
 * variant has its own renderer. The View/JSON toggle falls through to
 * the FHIR-style JSON view for non-FHIR kinds by serialising the
 * payload — handy for debugging and honest-proof of the data behind
 * the rendered artifact.
 *
 * Two affordances added for the patient_record family:
 *   - Fullscreen toggle (data-fullscreen attribute on the aside) so
 *     the timeline gets the full viewport when the doctor wants to
 *     scan it carefully.
 *   - Download button is no longer a no-op: for patient_record it
 *     fetches the FHIR Bundle for that user and triggers a JSON
 *     file download; for fhir_bundle it dumps the bundle that's
 *     already in hand.
 */
export function ArtifactPanel({
  artifact,
  onClose,
}: {
  artifact: ChatArtifact;
  onClose: () => void;
}) {
  const [tab, setTab] = useState<"view" | "json">("view");
  const [fullscreen, setFullscreen] = useState(false);
  const [downloadBusy, setDownloadBusy] = useState(false);

  // Esc closes fullscreen first, then the panel — predictable
  // keyboard behaviour for a jury watching the demo.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      if (fullscreen) {
        setFullscreen(false);
      } else {
        onClose();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [fullscreen, onClose]);

  const handleDownload = async () => {
    if (downloadBusy) return;
    setDownloadBusy(true);
    try {
      await downloadArtifact(artifact);
    } finally {
      setDownloadBusy(false);
    }
  };

  const downloadLabel =
    artifact.kind === "patient_record"
      ? "Export FHIR"
      : artifact.kind === "fhir_bundle"
        ? "Download"
        : "Download JSON";

  return (
    <aside
      className="artifact"
      key={artifact.id}
      data-fullscreen={fullscreen ? "true" : undefined}
    >
      <div className="artifact__head">
        <div className="artifact__meta">
          <h2 className="artifact__title">{artifact.title}</h2>
          <span className="artifact__sub">{artifact.subtitle}</span>
        </div>
        <div className="artifact__tabs">
          <button
            className="artifact__tab"
            aria-pressed={tab === "view"}
            onClick={() => setTab("view")}
          >
            View
          </button>
          <button
            className="artifact__tab"
            aria-pressed={tab === "json"}
            onClick={() => setTab("json")}
          >
            JSON
          </button>
        </div>
        <div className="artifact__actions">
          <button
            type="button"
            onClick={() => setFullscreen((f) => !f)}
            aria-pressed={fullscreen}
          >
            {fullscreen ? "Exit FS" : "Fullscreen"}
          </button>
          <button
            type="button"
            onClick={handleDownload}
            disabled={downloadBusy}
          >
            {downloadBusy ? "…" : downloadLabel}
          </button>
          <button type="button" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
      <div className="artifact__body" key={`${artifact.id}-${tab}`}>
        {tab === "json" ? <JsonView artifact={artifact} /> : <ViewBody artifact={artifact} />}
      </div>
    </aside>
  );
}

function ViewBody({ artifact }: { artifact: ChatArtifact }) {
  switch (artifact.kind) {
    case "cohort_trend":
      return <ArtifactDashboard payload={artifact.payload} />;
    case "alerts_table":
      return <ArtifactAlertsTable payload={artifact.payload} />;
    case "table":
      return <ArtifactPlainTable payload={artifact.payload} />;
    case "fhir_bundle":
      return <ArtifactFhir bundle={artifact.payload} />;
    case "patient_record":
      return <ArtifactPatientRecord payload={artifact.payload} />;
  }
}

function JsonView({ artifact }: { artifact: ChatArtifact }) {
  return (
    <pre
      style={{
        fontFamily: "var(--f-mono)",
        fontSize: 12,
        lineHeight: 1.55,
        color: "var(--ink-2)",
        margin: 0,
        whiteSpace: "pre-wrap",
      }}
    >
      {JSON.stringify(artifact.payload, null, 2)}
    </pre>
  );
}

// ---------------------------------------------------------------------
// Download helpers
// ---------------------------------------------------------------------
//
// For artifacts that already carry their own JSON shape we just save
// what's in hand. For patient_record we fetch the canonical FHIR Bundle
// from the BFF so the file the user gets is the same standards-
// compliant export every downstream system would consume — not a
// derived UI shape.

async function downloadArtifact(artifact: ChatArtifact): Promise<void> {
  if (artifact.kind === "patient_record") {
    const userId = artifact.payload.header.user_id;
    try {
      const res = await fetch(`/api/uniq/export/${userId}/fhir`);
      if (!res.ok) throw new Error(`export failed (${res.status})`);
      const bundle = await res.json();
      saveJson(bundle, `PT-${userId}.fhir.json`);
      return;
    } catch (err) {
      // Fall back to the artifact payload so the user always gets
      // something rather than an error sound — the substrate snapshot
      // is still useful, just less canonical than a fresh FHIR call.
      console.warn("FHIR export fetch failed, falling back to payload", err);
      saveJson(artifact.payload, `PT-${userId}.snapshot.json`);
      return;
    }
  }
  if (artifact.kind === "fhir_bundle") {
    saveJson(artifact.payload, `${artifact.id}.fhir.json`);
    return;
  }
  saveJson(artifact.payload, `${artifact.id}.json`);
}

function saveJson(data: unknown, filename: string): void {
  const blob = new Blob([JSON.stringify(data, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
