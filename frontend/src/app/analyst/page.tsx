"use client";

import { useRef, useState, type FormEvent } from "react";
import { Send } from "lucide-react";
import { Conversation, type Message } from "@/components/analyst/conversation";
import { ArtifactPanel, type Artifact } from "@/components/analyst/artifact-panel";
import { Button } from "@/components/ui/button";

// Pre-baked artifacts so the analyst can demo something visual while the real
// SQL-agent backend is still stubbed. Phase 6 replaces these with real
// DuckDB + LLM-generated results.
const DEMO_ARTIFACTS: Record<string, Artifact> = {
  "fhir-381254": {
    id: "fhir-381254",
    kind: "fhir",
    title: "FHIR Bundle · Patient 381254",
    subtitle: "10 resources · Observation, MedicationStatement, AdverseEvent, Patient",
    bundle: {
      resourceType: "Bundle",
      type: "collection",
      total: 10,
      entry: [
        {
          resource: {
            resourceType: "Patient",
            id: "patient-381254",
            identifier: [{ system: "urn:wellster:patient", value: "381254" }],
            gender: "female",
          },
        },
        {
          resource: {
            resourceType: "Observation",
            code: {
              coding: [
                {
                  system: "http://loinc.org",
                  code: "39156-5",
                  display: "Body mass index",
                },
              ],
            },
            valueQuantity: { value: 34.2, unit: "kg/m2" },
          },
        },
      ],
    },
  },
  "cohort-glp1": {
    id: "cohort-glp1",
    kind: "table",
    title: "Cohort · GLP-1 patients",
    subtitle: "Mounjaro + Wegovy · 1,220 patients · BMI delta",
    columns: ["user_id", "product", "baseline_bmi", "latest_bmi", "delta"],
    rows: [
      { user_id: 381254, product: "Wegovy", baseline_bmi: 39.8, latest_bmi: 31.2, delta: -8.6 },
      { user_id: 395128, product: "Mounjaro", baseline_bmi: 42.1, latest_bmi: 34.0, delta: -8.1 },
      { user_id: 388041, product: "Mounjaro", baseline_bmi: 37.4, latest_bmi: 30.9, delta: -6.5 },
      { user_id: 392210, product: "Wegovy", baseline_bmi: 35.6, latest_bmi: 29.8, delta: -5.8 },
      { user_id: 401117, product: "Mounjaro", baseline_bmi: 41.0, latest_bmi: 35.3, delta: -5.7 },
    ],
  },
};

const DEMO_RESPONSES: Record<string, { reply: string; artifactId?: string }> = {
  fhir: {
    reply:
      "Here is the FHIR R4 Bundle for patient 381254 — 10 resources across Patient, Observation, MedicationStatement and AdverseEvent. Codes are LOINC + RxNorm + SNOMED CT. You can download it on the right.",
    artifactId: "fhir-381254",
  },
  cohort: {
    reply:
      "Pulled a cohort of 1,220 GLP-1 patients from the unified survey table. Sorting by BMI delta shows Wegovy and Mounjaro patients clustering around -6 to -8 kg/m². Top five are in the artifact panel.",
    artifactId: "cohort-glp1",
  },
};

function fakeMatchArtifact(query: string): { reply: string; artifactId?: string } {
  const q = query.toLowerCase();
  if (q.includes("fhir") || q.includes("export") || q.includes("bundle")) {
    return DEMO_RESPONSES.fhir;
  }
  if (q.includes("cohort") || q.includes("glp") || q.includes("mounjaro") || q.includes("wegovy")) {
    return DEMO_RESPONSES.cohort;
  }
  return {
    reply:
      "Phase-6 backend will route this question through a DuckDB query + SQL agent. The stub returns a placeholder — try asking for a FHIR export or a GLP-1 cohort to see artifacts.",
  };
}

export default function AnalystPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [pending, setPending] = useState(false);
  const [artifact, setArtifact] = useState<Artifact | null>(null);
  const nextId = useRef(0);
  const mkId = () => `msg-${nextId.current++}`;

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const text = input.trim();
    if (!text || pending) return;

    setMessages((prev) => [...prev, { id: mkId(), role: "user", content: text }]);
    setInput("");
    setPending(true);

    // Hit the stubbed /chat so the end-to-end wire is real, then layer the
    // demo artifact on top until phase 6 builds the actual agent.
    try {
      await fetch("/api/uniq/chat", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ message: text }),
      });
    } catch {
      // fall through to demo reply even if backend is off
    }

    await new Promise((r) => setTimeout(r, 900));

    const match = fakeMatchArtifact(text);
    const assistantId = mkId();
    setMessages((prev) => [
      ...prev,
      { id: assistantId, role: "assistant", content: match.reply, artifactId: match.artifactId },
    ]);

    if (match.artifactId) {
      setArtifact(DEMO_ARTIFACTS[match.artifactId]);
    }
    setPending(false);
  };

  const openArtifactById = (id: string) => {
    const found = DEMO_ARTIFACTS[id];
    if (found) setArtifact(found);
  };

  return (
    <div className="flex h-[calc(100vh-3.5rem)] w-full">
      {/* Conversation column */}
      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex-1 overflow-y-auto">
          <div className="mx-auto max-w-3xl">
            <Conversation
              messages={messages}
              pending={pending}
              onArtifactClick={openArtifactById}
            />
          </div>
        </div>

        {/* Composer */}
        <div className="border-t border-ink-700 bg-ink-900/60 backdrop-blur-sm">
          <form onSubmit={onSubmit} className="mx-auto flex max-w-3xl items-end gap-2 px-6 py-4">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  onSubmit(e as unknown as FormEvent);
                }
              }}
              placeholder="Ask about cohorts, outcomes, FHIR exports…"
              rows={1}
              className="flex-1 resize-none rounded-lg border border-ink-700 bg-ink-900 px-4 py-3 text-sm text-text-0 placeholder:text-text-3 focus:border-glacial/60 focus:outline-none"
            />
            <Button type="submit" variant="primary" size="md" disabled={!input.trim() || pending}>
              <Send className="h-4 w-4" />
              Send
            </Button>
          </form>
          <div className="mx-auto max-w-3xl px-6 pb-3 font-mono text-[10px] text-text-3">
            Phase 6 wires the real SQL agent. Current: stubbed responses demonstrate the
            artifact-panel UX.
          </div>
        </div>
      </div>

      {/* Artifact column */}
      <ArtifactPanel artifact={artifact} onClose={() => setArtifact(null)} />
    </div>
  );
}
