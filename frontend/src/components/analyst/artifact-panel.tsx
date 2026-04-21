"use client";

import { useState } from "react";
import type { ArtifactDescriptor } from "@/lib/demo/recipes";
import { DEMO_DASHBOARD, DEMO_FHIR_BUNDLE } from "@/lib/demo/recipes";
import { ArtifactDashboard } from "./artifact-dashboard";
import { ArtifactFhir } from "./artifact-fhir";

/**
 * Canvas panel on the right of the Analyst when an artifact is open.
 *
 * Head (title + sub + tabs + actions) + body that switches by
 * artifact.kind and by the View/JSON tab. Closing is handled by the
 * parent; we only fire onClose.
 */
export function ArtifactPanel({
  artifact,
  onClose,
}: {
  artifact: ArtifactDescriptor;
  onClose: () => void;
}) {
  const [tab, setTab] = useState<"view" | "json">("view");

  const body =
    tab === "json"
      ? <ArtifactFhir bundle={DEMO_FHIR_BUNDLE} />
      : artifact.kind === "dashboard"
        ? <ArtifactDashboard payload={DEMO_DASHBOARD} />
        : <ArtifactFhir bundle={DEMO_FHIR_BUNDLE} />;

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
        {body}
      </div>
    </aside>
  );
}
