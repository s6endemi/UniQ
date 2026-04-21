"use client";

import { useState } from "react";
import type { ChatArtifact } from "@/lib/api";
import { ArtifactAlertsTable } from "./artifact-alerts-table";
import { ArtifactDashboard } from "./artifact-dashboard";
import { ArtifactFhir } from "./artifact-fhir";
import { ArtifactPlainTable } from "./artifact-plain-table";

/**
 * Canvas panel on the right of the Analyst when an artifact is open.
 *
 * One dispatch on `artifact.kind` per discriminated-union variant; each
 * variant has its own renderer. The View/JSON toggle falls through to
 * the FHIR-style JSON view for non-FHIR kinds by serialising the
 * payload — handy for debugging and honest-proof of the data behind
 * the rendered artifact.
 */
export function ArtifactPanel({
  artifact,
  onClose,
}: {
  artifact: ChatArtifact;
  onClose: () => void;
}) {
  const [tab, setTab] = useState<"view" | "json">("view");

  return (
    <aside className="artifact" key={artifact.id}>
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
          <button type="button">Download</button>
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
