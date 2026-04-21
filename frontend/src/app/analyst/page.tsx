"use client";

import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";

// ---------------------------------------------------------------
// Artifact renderers
// ---------------------------------------------------------------

type ArtifactType = "dashboard" | "fhir";

interface ArtifactDescriptor {
  id: string;
  type: ArtifactType;
  title: string;
  meta: string;
}

function DashboardArtifact() {
  const path = useMemo(() => {
    const pts = [32.1, 31.8, 31.2, 30.7, 30.1, 29.8, 29.3, 28.7, 28.2, 27.9, 27.5, 27.2];
    const w = 100;
    const h = 60;
    const max = 33;
    const min = 26;
    const coords = pts.map<[number, number]>((v, i) => [
      (i / (pts.length - 1)) * w,
      h - ((v - min) / (max - min)) * h,
    ]);
    const d = coords
      .map(([x, y], i) => (i === 0 ? `M ${x} ${y}` : `L ${x} ${y}`))
      .join(" ");
    const area = `${d} L ${w} ${h} L 0 ${h} Z`;
    return { d, area, coords };
  }, []);

  const table: Array<[string, string, number, number, number, string]> = [
    ["PT-44192", "5 mg", 33.4, 27.8, -5.6, "94%"],
    ["PT-40823", "2.5 mg", 31.1, 27.9, -3.2, "81%"],
    ["PT-51108", "10 mg", 35.6, 28.2, -7.4, "88%"],
    ["PT-39004", "5 mg", 30.8, 26.9, -3.9, "91%"],
    ["PT-48715", "7.5 mg", 34.0, 28.4, -5.6, "84%"],
    ["PT-42290", "5 mg", 32.2, 27.0, -5.2, "90%"],
    ["PT-50331", "2.5 mg", 29.7, 27.4, -2.3, "76%"],
  ];

  return (
    <div>
      <div className="dash-kpis">
        <div className="dash-kpi">
          <div className="dash-kpi__label">Cohort · Mounjaro</div>
          <div className="dash-kpi__value">842</div>
          <div className="dash-kpi__delta">+ 37 past 30d</div>
        </div>
        <div className="dash-kpi">
          <div className="dash-kpi__label">Mean BMI · baseline</div>
          <div className="dash-kpi__value">32.1</div>
          <div className="dash-kpi__delta">n = 842</div>
        </div>
        <div className="dash-kpi">
          <div className="dash-kpi__label">Mean BMI · 24w</div>
          <div className="dash-kpi__value">27.2</div>
          <div className="dash-kpi__delta">− 4.9 pts</div>
        </div>
        <div className="dash-kpi">
          <div className="dash-kpi__label">Adherence</div>
          <div className="dash-kpi__value">
            86<span style={{ fontSize: 22, color: "var(--ink-3)" }}>%</span>
          </div>
          <div className="dash-kpi__delta is-down">− 2 pts WoW</div>
        </div>
      </div>

      <div className="chart">
        <div className="chart__head">
          <div className="chart__title">BMI trajectory — Mounjaro cohort</div>
          <div className="chart__sub">weeks 0 — 24 · n = 842</div>
        </div>
        <svg className="chart__svg" viewBox="0 0 100 60" preserveAspectRatio="none">
          {[0, 15, 30, 45, 60].map((y) => (
            <line
              key={y}
              x1="0"
              y1={y}
              x2="100"
              y2={y}
              stroke="var(--rule-soft)"
              strokeWidth="0.15"
            />
          ))}
          <path d={path.area} fill="var(--signal-wash)" opacity={0.6} />
          <path
            d={path.d}
            fill="none"
            stroke="var(--signal-ink)"
            strokeWidth="0.5"
            vectorEffect="non-scaling-stroke"
          />
          {path.coords.map(([x, y], i) => (
            <circle
              key={i}
              cx={x}
              cy={y}
              r="0.6"
              fill="var(--paper-rise)"
              stroke="var(--signal-ink)"
              strokeWidth="0.3"
            />
          ))}
        </svg>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            padding: "6px 16px 14px",
            fontFamily: "var(--f-mono)",
            fontSize: 10,
            color: "var(--ink-3)",
            letterSpacing: "0.08em",
          }}
        >
          <span>W0</span>
          <span>W4</span>
          <span>W8</span>
          <span>W12</span>
          <span>W16</span>
          <span>W20</span>
          <span>W24</span>
        </div>
      </div>

      <table className="cohort-table">
        <thead>
          <tr>
            <th>Patient ID</th>
            <th>Dose</th>
            <th>BMI · W0</th>
            <th>BMI · W24</th>
            <th>Δ</th>
            <th>Adherence</th>
          </tr>
        </thead>
        <tbody>
          {table.map((row) => (
            <tr key={row[0]}>
              <td>{row[0]}</td>
              <td>{row[1]}</td>
              <td>{row[2]}</td>
              <td>{row[3]}</td>
              <td style={{ color: "var(--signal-ink)" }}>{row[4]}</td>
              <td>{row[5]}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function FhirArtifact() {
  const bundle = {
    resourceType: "Bundle",
    id: "uniq-patient-PT-44192",
    type: "collection",
    timestamp: "2026-04-21T09:14:00Z",
    entry: [
      {
        resource: {
          resourceType: "Patient",
          id: "PT-44192",
          gender: "female",
          birthDate: "1986-03-14",
        },
      },
      {
        resource: {
          resourceType: "Observation",
          code: {
            coding: [
              { system: "LOINC", code: "39156-5", display: "BMI" },
            ],
          },
          valueQuantity: { value: 33.4, unit: "kg/m2" },
          effectiveDateTime: "2025-10-12",
        },
      },
      {
        resource: {
          resourceType: "Observation",
          code: {
            coding: [
              { system: "LOINC", code: "39156-5", display: "BMI" },
            ],
          },
          valueQuantity: { value: 27.8, unit: "kg/m2" },
          effectiveDateTime: "2026-04-04",
        },
      },
      {
        resource: {
          resourceType: "MedicationStatement",
          medication: {
            coding: [
              { system: "RxNorm", code: "2601723", display: "tirzepatide 5 MG" },
            ],
          },
          status: "active",
        },
      },
      {
        resource: {
          resourceType: "Condition",
          code: {
            coding: [
              { system: "ICD-10", code: "E66.9", display: "Obesity, unspecified" },
            ],
          },
        },
      },
    ],
  };

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

function ArtifactPanel({
  artifact,
  onClose,
}: {
  artifact: ArtifactDescriptor;
  onClose: () => void;
}) {
  const [tab, setTab] = useState<"view" | "json">("view");
  return (
    <aside className="artifact" key={artifact.id}>
      <div className="artifact__head">
        <div className="artifact__meta">
          <h2 className="artifact__title">{artifact.title}</h2>
          <span className="artifact__sub">{artifact.meta}</span>
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
        {tab === "view" ? (
          artifact.type === "dashboard" ? (
            <DashboardArtifact />
          ) : (
            <FhirArtifact />
          )
        ) : (
          <FhirArtifact />
        )}
      </div>
    </aside>
  );
}

// ---------------------------------------------------------------
// Thinking + streaming primitives
// ---------------------------------------------------------------

interface Step {
  text: string;
  done: boolean;
}

function Thinking({ steps, done }: { steps: Step[]; done: boolean }) {
  return (
    <div className={`thinking ${done ? "is-done" : ""}`}>
      <div className="thinking__header">
        <span className="thinking__spinner" />
        <span>{done ? `Planned · ${steps.length} steps` : "Thinking…"}</span>
      </div>
      {steps.map((s, i) => (
        <div
          key={`${s.text}-${i}`}
          className={`thinking__step ${s.done ? "is-done" : ""}`}
          style={{ animationDelay: `${i * 50}ms` }}
        >
          <span className="dot" />
          <span>{s.text}</span>
        </div>
      ))}
    </div>
  );
}

function TypedText({ text, onDone }: { text: string; onDone?: () => void }) {
  const [out, setOut] = useState("");

  useEffect(() => {
    setOut("");
    let i = 0;
    const id = setInterval(() => {
      i += 2;
      setOut(text.slice(0, i));
      if (i >= text.length) {
        clearInterval(id);
        onDone?.();
      }
    }, 14);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text]);

  const lines = out.split("\n");
  return (
    <div className="turn__text">
      {lines.map((line, i) => (
        <p key={i}>
          {line}
          {i === lines.length - 1 && out.length < text.length && (
            <span className="cursor" />
          )}
        </p>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------
// Turn data + flow
// ---------------------------------------------------------------

interface UserTurn {
  id: number;
  role: "user";
  text: string;
}
interface AiTurn {
  id: number;
  role: "ai";
  phase: "thinking" | "reply";
  steps: Step[];
  text?: string;
  artifact?: ArtifactDescriptor;
}
type Turn = UserTurn | AiTurn;

const SUGGESTIONS = [
  {
    meta: "Cohort · trend",
    text: "Show BMI trends for Mounjaro patients over the past 24 weeks",
  },
  {
    meta: "Adherence",
    text: "Which patients have missed more than two weekly doses?",
  },
  {
    meta: "FHIR export",
    text: "Generate a FHIR bundle for patient PT-44192",
  },
  {
    meta: "Cross-cohort",
    text: "Compare HbA1c change between Ozempic and Mounjaro",
  },
];

function detectArtifact(q: string): ArtifactDescriptor {
  const s = q.toLowerCase();
  if (s.includes("fhir") || s.includes("bundle") || s.includes("pt-")) {
    return {
      id: `fhir-${Date.now()}`,
      type: "fhir",
      title: "FHIR Bundle · PT-44192",
      meta: "Bundle · 5 resources · 1.8 kB",
    };
  }
  return {
    id: `dash-${Date.now()}`,
    type: "dashboard",
    title: "Mounjaro cohort · BMI trajectory",
    meta: "Dashboard · n = 842 · window 24w",
  };
}

function buildSteps(q: string): string[] {
  const s = q.toLowerCase();
  if (s.includes("fhir") || s.includes("bundle")) {
    return [
      "Resolve patient identifier · PT-44192",
      "Query FHIR substrate · Patient, Observation, MedicationStatement, Condition",
      "Assemble Bundle · type=collection",
      "Validate against FHIR R4 schema",
    ];
  }
  return [
    "Resolve cohort · patients with rx_tirzepatide = true",
    "Pull BMI observations · LOINC 39156-5 · weeks 0 – 24",
    "Compute mean trajectory and adherence deltas",
    "Render dashboard with top-7 patient table",
  ];
}

function buildReply(q: string): string {
  if (q.toLowerCase().includes("fhir")) {
    return "Assembled a 5-resource FHIR bundle for PT-44192 — Patient, two BMI Observations (W0, W24), MedicationStatement (tirzepatide 5 mg) and the obesity Condition. Opening it in the canvas.";
  }
  return "Built a 24-week BMI trajectory for the Mounjaro cohort (n = 842). Mean fell from 32.1 to 27.2 kg/m² — a 4.9-point drop. Adherence is 86%, soft downward week-on-week. Table below ranks the top-seven responders. Dashboard is open on the right.";
}

// ---------------------------------------------------------------
// Page
// ---------------------------------------------------------------

export default function AnalystPage() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [artifact, setArtifact] = useState<ArtifactDescriptor | null>(null);
  const streamRef = useRef<HTMLDivElement>(null);
  const idRef = useRef(0);
  const mkId = () => ++idRef.current;

  useEffect(() => {
    streamRef.current?.scrollTo({
      top: streamRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [turns]);

  const submit = async (q: string) => {
    const text = q.trim();
    if (!text || busy) return;

    const stepList = buildSteps(text);
    const aiId = mkId();
    const aiTurn: AiTurn = {
      id: aiId,
      role: "ai",
      phase: "thinking",
      steps: stepList.map((t) => ({ text: t, done: false })),
      artifact: detectArtifact(text),
    };
    setTurns((t) => [...t, { id: mkId(), role: "user", text }, aiTurn]);
    setDraft("");
    setBusy(true);

    // Fire the real stub endpoint so end-to-end wire stays exercised.
    fetch("/api/uniq/chat", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ message: text }),
    }).catch(() => {
      /* stub — swallow errors, the scripted flow still runs */
    });

    // Step-through thinking
    stepList.forEach((_, i) => {
      setTimeout(
        () => {
          setTurns((prev) =>
            prev.map((turn) => {
              if (turn.role !== "ai" || turn.id !== aiId) return turn;
              return {
                ...turn,
                steps: turn.steps.map((s, j) =>
                  j <= i ? { ...s, done: true } : s,
                ),
              };
            }),
          );
        },
        420 * (i + 1),
      );
    });

    // Transition to reply + artifact reveal
    setTimeout(
      () => {
        setTurns((prev) =>
          prev.map((turn) =>
            turn.role === "ai" && turn.id === aiId
              ? { ...turn, phase: "reply", text: buildReply(text) }
              : turn,
          ),
        );
        setTimeout(() => {
          setArtifact(aiTurn.artifact!);
          setBusy(false);
        }, 600);
      },
      420 * (stepList.length + 1),
    );
  };

  const onSend = (e?: FormEvent) => {
    e?.preventDefault();
    submit(draft);
  };

  return (
    <div className="room" data-screen-label="03 Analyst">
      <div className={`analyst ${artifact ? "has-artifact" : ""}`}>
        <div className="chat">
          <div className="chat__stream" ref={streamRef}>
            {turns.length === 0 && (
              <div className="chat__welcome">
                <h1 className="chat__welcome-title">
                  What do you want to <em>know?</em>
                </h1>
                <p className="chat__welcome-sub">
                  Ask in plain language. I&apos;ll query the FHIR substrate and
                  render an artifact beside this conversation.
                </p>
                <div className="chat__suggestions">
                  {SUGGESTIONS.map((s) => (
                    <button
                      key={s.text}
                      type="button"
                      className="chat__suggestion"
                      onClick={() => submit(s.text)}
                    >
                      <span className="t-meta">{s.meta}</span>
                      {s.text}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {turns.map((turn) => {
              if (turn.role === "user") {
                return (
                  <div key={turn.id} className="turn turn--user">
                    <div className="turn__bubble">{turn.text}</div>
                  </div>
                );
              }
              return (
                <div key={turn.id} className="turn turn--ai">
                  <div className="turn__avatar" />
                  <div className="turn__content">
                    <Thinking steps={turn.steps} done={turn.phase === "reply"} />
                    {turn.phase === "reply" && turn.text && (
                      <>
                        <TypedText text={turn.text} />
                        {turn.artifact && (
                          <button
                            type="button"
                            className="turn__artifact-card"
                            onClick={() => setArtifact(turn.artifact!)}
                          >
                            <div className="turn__artifact-thumb" />
                            <div className="turn__artifact-info">
                              <span className="turn__artifact-title">
                                {turn.artifact.title}
                              </span>
                              <span className="turn__artifact-meta">
                                {turn.artifact.meta}
                              </span>
                            </div>
                            <span className="turn__artifact-open">Open →</span>
                          </button>
                        )}
                      </>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          <form className="composer" onSubmit={onSend}>
            <div className="composer__inner">
              <textarea
                rows={1}
                placeholder="Ask the analyst anything about your data…"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    onSend();
                  }
                }}
                disabled={busy}
              />
              <button
                className="composer__send"
                type="submit"
                disabled={!draft.trim() || busy}
              >
                {busy ? "…" : "Ask →"}
              </button>
            </div>
            <div className="composer__hint">
              queries run against FHIR substrate · 5,374 patients · read-only in
              preview mode
            </div>
          </form>
        </div>

        {artifact && (
          <ArtifactPanel
            artifact={artifact}
            onClose={() => setArtifact(null)}
          />
        )}
      </div>
    </div>
  );
}
