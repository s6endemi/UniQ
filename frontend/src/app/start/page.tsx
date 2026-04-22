"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

/**
 * Intake Console — `/start`.
 *
 * Guided demo entry point. Source Manifest on the left (Wellster connected,
 * adapters as roadmap), Processing Trace on the right that streams a
 * scripted 5-stage animation when the user runs intake on Wellster.
 *
 * The trace is scripted — we control the pacing so the pitch never stalls
 * on Anthropic latency or network flakes. The underlying pipeline is real
 * (Phase 2–4 shipped it); this page narrates one intake run in a
 * predictable, demo-grade rhythm. Numbers count up during the running
 * phase to give weight to the work the system is doing; a slim progress
 * bar under each running line adds a "something is happening" cue
 * beyond just a spinner.
 */

type StepId =
  | "schema"
  | "semantic"
  | "review"
  | "validate"
  | "materialize";

type Status = "pending" | "running" | "done";

interface TraceDef {
  id: StepId;
  label: string;
  target: number;
  unit: string;
  duration: number;
}

// Uneven pacing by design — "Reading schema" is a fast IO scan,
// AI classification is the genuine beat of the pipeline, materialisation
// is a near-instant write of an in-memory view. The semantic step is
// stretched to 3.2 s deliberately — it's the only one that corresponds
// to a real Anthropic call in production, and giving it visible
// weight sells "AI is thinking here", not "progress bar theatre".
// Total ≈ 8.5 s end to end.
const TRACE_DEFS: TraceDef[] = [
  { id: "schema",      label: "Reading schema",               target: 48,    unit: "fields",      duration: 700 },
  { id: "semantic",    label: "Classifying clinical categories", target: 20, unit: "categories",  duration: 3200 },
  { id: "review",      label: "Preparing clinical review",    target: 1,     unit: "final check", duration: 2000 },
  { id: "validate",    label: "Validating substrate",         target: 1031,  unit: "flags",       duration: 1400 },
  { id: "materialize", label: "Materializing substrate",      target: 5374,  unit: "patients",    duration: 850 },
];

interface TraceItem {
  def: TraceDef;
  status: Status;
  tsStart: string;
  tsDone: string | null;
  /** Wallclock ms when this item flipped to "running". Drives the counter + bar. */
  runStartedAt: number | null;
}

function fmtTimestamp(offsetMs: number, base: number): string {
  const d = new Date(base + offsetMs);
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  const ss = String(d.getSeconds()).padStart(2, "0");
  const ms = String(d.getMilliseconds()).padStart(3, "0");
  return `${hh}:${mm}:${ss}.${ms}`;
}

// Standard ease-out — fast start, slow finish — so the count-up feels
// like the number is "settling" rather than robotically ticking.
function easeOutCubic(t: number): number {
  return 1 - Math.pow(1 - t, 3);
}

export default function StartPage() {
  const router = useRouter();
  const [phase, setPhase] = useState<"idle" | "running" | "done">("idle");
  const [items, setItems] = useState<TraceItem[]>([]);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);
  const bannerRef = useRef<HTMLButtonElement | null>(null);

  // Cleanup timers on unmount so mid-trace navigation doesn't schedule
  // state updates against an unmounted tree.
  useEffect(() => {
    return () => {
      for (const t of timers.current) clearTimeout(t);
      timers.current = [];
    };
  }, []);

  const run = useCallback(() => {
    if (phase !== "idle") return;
    setPhase("running");
    setItems([]);

    const base = Date.now();
    let cursor = 120; // small idle before the first step shows

    TRACE_DEFS.forEach((def, i) => {
      const startAt = cursor;
      const endAt = cursor + def.duration;

      // Step enters as "running".
      timers.current.push(
        setTimeout(() => {
          const ts = fmtTimestamp(startAt, base);
          setItems((prev) => [
            ...prev,
            {
              def,
              status: "running",
              tsStart: ts,
              tsDone: null,
              runStartedAt: Date.now(),
            },
          ]);
        }, startAt),
      );

      // Step flips to "done".
      timers.current.push(
        setTimeout(() => {
          const ts = fmtTimestamp(endAt, base);
          setItems((prev) =>
            prev.map((it) =>
              it.def.id === def.id
                ? { ...it, status: "done", tsDone: ts, runStartedAt: null }
                : it,
            ),
          );
          if (i === TRACE_DEFS.length - 1) {
            setPhase("done");
            router.replace("/start?step=done");
          }
        }, endAt),
      );

      cursor = endAt + 110; // small gap between steps so the eye can track
    });
  }, [phase, router]);

  useEffect(() => {
    if (phase === "done") {
      const t = setTimeout(() => bannerRef.current?.focus(), 300);
      return () => clearTimeout(t);
    }
  }, [phase]);

  const handleContinue = () => {
    router.push("/review?from=intake");
  };

  return (
    <div className="room" data-screen-label="Intake Console">
      <div className="intake">
        {/* ─── Left: Source Manifest ──────────────────────────────── */}
        <aside className="intake__manifest">
          <header className="intake__head">
            <h1 className="intake__title">
              Intake <em>Console</em>
            </h1>
            <p className="intake__sub">Run intake on a connected source</p>
          </header>

          <section className="intake__section">
            <div className="intake__section-label">Connected sources</div>
            <article className="source-card" data-active={phase !== "idle"}>
              <div className="source-card__head">
                <span className="source-card__name">Wellster</span>
                <span className="source-card__badge">
                  <span className="source-card__badge-dot" aria-hidden="true" />
                  connected
                </span>
              </div>
              <div className="source-card__desc">
                Telehealth stack · 5,374 patient records
              </div>
              <button
                type="button"
                className="source-card__action"
                onClick={run}
                disabled={phase !== "idle"}
              >
                {phase === "idle"
                  ? "Run intake →"
                  : phase === "running"
                    ? "Running…"
                    : "Complete ✓"}
              </button>
            </article>
          </section>

          <section className="intake__section intake__section--roadmap">
            <div className="intake__section-label">Adapter roadmap</div>
            <div className="adapter-roadmap">
              {[
                "FHIR R4 endpoint",
                "Epic MyChart",
                "Cerner",
                "CSV / Excel bulk",
              ].map((name) => (
                <div key={name} className="adapter-chip" aria-disabled="true">
                  <span className="adapter-chip__lock" aria-hidden="true" />
                  <span className="adapter-chip__name">{name}</span>
                  <span className="adapter-chip__state">planned</span>
                </div>
              ))}
            </div>
          </section>

          <footer className="intake__foot">
            <span className="t-meta">
              Need a different connector? Talk to us →
            </span>
          </footer>
        </aside>

        {/* ─── Right: Processing Trace ────────────────────────────── */}
        <section className="intake__trace">
          <div className="trace-panel">
            <div className="trace-panel__head">
              <span>Processing trace</span>
              <span className="trace-panel__state" data-state={phase}>
                {phase === "idle"
                  ? "idle"
                  : phase === "running"
                    ? "running"
                    : "complete"}
              </span>
            </div>

            <div className="trace-panel__body">
              {items.length === 0 ? (
                <div className="trace-panel__placeholder">
                  Select a source and run intake to see the trace.
                </div>
              ) : (
                <ol className="trace-list">
                  {items.map((it) => (
                    <TraceLine key={it.def.id} item={it} />
                  ))}
                </ol>
              )}
            </div>

            {phase === "done" && (
              <div className="handoff" role="region" aria-label="Next step">
                <div className="handoff__body">
                  <div className="handoff__label">Step 2</div>
                  <div className="handoff__title">
                    Final clinical sign-off required
                  </div>
                  <div className="handoff__sub">
                    One mapping awaits your final approval before the
                    substrate materializes.
                  </div>
                </div>
                <button
                  ref={bannerRef}
                  type="button"
                  className="handoff__action"
                  onClick={handleContinue}
                >
                  Review final mapping →
                </button>
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}

/**
 * One line in the trace. Owns its own requestAnimationFrame loop while
 * running so the counter + progress bar stay smooth without churning the
 * parent's state 25 times a second.
 */
function TraceLine({ item }: { item: TraceItem }) {
  // Local progress state only ticks during the "running" phase; when
  // the status flips to "done" we simply stop updating it and derive
  // the displayed progress from status during render (no setState-in-
  // effect, which React 19 lint now catches).
  const [progress, setProgress] = useState(0);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    if (item.status !== "running" || !item.runStartedAt) return;
    const start = item.runStartedAt;
    const dur = item.def.duration;
    const tick = () => {
      const elapsed = Date.now() - start;
      const p = Math.min(1, elapsed / dur);
      setProgress(p);
      if (p < 1) rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    };
  }, [item.status, item.runStartedAt, item.def.duration]);

  const effectiveProgress = item.status === "done" ? 1 : progress;
  const displayValue =
    item.status === "done"
      ? item.def.target
      : Math.round(item.def.target * easeOutCubic(effectiveProgress));
  const formattedValue = displayValue.toLocaleString("en-US");

  return (
    <li className={`trace-line trace-line--${item.status}`}>
      <span className="trace-line__ts">
        {item.status === "done" ? item.tsDone : item.tsStart}
      </span>
      <span className="trace-line__icon" aria-hidden="true">
        {item.status === "done" ? "✓" : <span className="trace-line__spinner" />}
      </span>
      <span className="trace-line__label">{item.def.label}</span>
      <span className="trace-line__detail">
        <span className="trace-line__count">{formattedValue}</span>{" "}
        <span className="trace-line__unit">{item.def.unit}</span>
      </span>
      {item.status === "running" && (
        <span className="trace-line__bar" aria-hidden="true">
          <span
            className="trace-line__bar-fill"
            style={{ width: `${(effectiveProgress * 100).toFixed(1)}%` }}
          />
        </span>
      )}
    </li>
  );
}
