"use client";

import type { FhirBundlePayload } from "@/lib/api";

/**
 * FHIR bundle renderer.
 *
 * Pretty-prints the bundle as JSON in monospace. Post-pitch we can
 * evolve this into a resource-by-resource inspector; for now the raw
 * JSON is the honest artifact — what a downstream system would consume.
 */
export function ArtifactFhir({ bundle }: { bundle: FhirBundlePayload }) {
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
      {JSON.stringify(bundle, null, 2)}
    </pre>
  );
}
