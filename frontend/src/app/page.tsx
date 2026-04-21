import Link from "next/link";
import { ArrowRight, ShieldCheck, Sparkles, Workflow } from "lucide-react";
import { AiOrb } from "@/components/ai-orb";
import { Button } from "@/components/ui/button";
import { LiveKpis } from "@/components/live-kpis";
import { PipelineTimeline } from "@/components/pipeline-timeline";

export default function StoryPage() {
  return (
    <>
      {/* ─── Hero ────────────────────────────────────────────────── */}
      <section className="relative overflow-hidden">
        <div className="mx-auto grid max-w-7xl grid-cols-1 items-center gap-12 px-6 pt-24 pb-32 lg:grid-cols-[1.2fr_1fr] lg:gap-16">
          <div className="space-y-8">
            <div className="inline-flex items-center gap-2 rounded-full border border-glacial/30 bg-glacial/5 px-3 py-1 font-mono text-[11px] uppercase tracking-wider text-glacial">
              <span className="h-1.5 w-1.5 rounded-full bg-glacial animate-pulse" />
              clinical futurist · v0.1
            </div>

            <h1 className="font-display text-5xl font-semibold leading-[1.05] tracking-tight text-text-0 sm:text-6xl lg:text-7xl">
              Healthcare data,
              <br />
              <span className="text-glacial">unified by intelligence.</span>
            </h1>

            <p className="max-w-xl text-lg leading-relaxed text-text-2">
              UniQ ingests fragmented questionnaire data, discovers its clinical
              meaning automatically, and exports standards-compliant records
              your AI analyst can actually reason about. The engine adapts.
              Your clinicians stay in control.
            </p>

            <div className="flex flex-wrap gap-3">
              <Link href="/review">
                <Button variant="primary" size="lg">
                  See it work
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </Link>
              <Link href="/analyst">
                <Button variant="secondary" size="lg">
                  Open the analyst
                </Button>
              </Link>
            </div>
          </div>

          {/* Orb */}
          <div className="relative flex justify-center lg:justify-end">
            <AiOrb size={360} />
          </div>
        </div>
      </section>

      {/* ─── Live KPI strip ──────────────────────────────────────── */}
      <section className="mx-auto max-w-7xl px-6 pb-20">
        <div className="mb-4 flex items-baseline justify-between">
          <h2 className="font-mono text-[11px] uppercase tracking-[0.18em] text-text-3">
            Pipeline · live state
          </h2>
          <span className="font-mono text-[11px] text-text-3">
            polled every 10 s
          </span>
        </div>
        <LiveKpis />
      </section>

      {/* ─── Pipeline timeline ───────────────────────────────────── */}
      <section className="border-t border-ink-700/60 bg-ink-900/30 py-24">
        <div className="mx-auto max-w-7xl px-6">
          <div className="mb-16 max-w-2xl">
            <h2 className="font-display text-3xl font-semibold tracking-tight text-text-0 sm:text-4xl">
              Five stages.
              <br />
              <span className="text-text-2">From raw export to FHIR Bundle.</span>
            </h2>
            <p className="mt-4 text-base leading-relaxed text-text-2">
              Every stage is observable, every AI suggestion is reviewable, every
              output is standards-compliant. No predefined dashboards — your
              data shapes its own surface.
            </p>
          </div>

          <PipelineTimeline />
        </div>
      </section>

      {/* ─── Three pillars ───────────────────────────────────────── */}
      <section className="border-t border-ink-700/60 py-24">
        <div className="mx-auto max-w-7xl px-6">
          <div className="grid grid-cols-1 gap-8 md:grid-cols-3">
            <Pillar
              icon={Sparkles}
              title="Adaptive engine"
              text="The AI discovers clinical structure from any questionnaire dataset. No schema mapping, no hardcoded categories — the engine adapts to each customer's data shape."
            />
            <Pillar
              icon={ShieldCheck}
              title="Human in the loop"
              text="AI proposes mappings with confidence scores. Clinicians approve, override, or reject. Approved decisions persist across pipeline runs — review once, scale forever."
            />
            <Pillar
              icon={Workflow}
              title="Open by design"
              text="FHIR R4 out of the box. Read-only SQL access for your AI analyst. Generic API surface — your team builds the use cases, not us."
            />
          </div>
        </div>
      </section>

      {/* ─── Footer call ─────────────────────────────────────────── */}
      <section className="border-t border-ink-700/60 py-20">
        <div className="mx-auto flex max-w-3xl flex-col items-center gap-6 px-6 text-center">
          <h2 className="font-display text-3xl font-semibold tracking-tight text-text-0 sm:text-4xl">
            Built for the question
            <br />
            <span className="text-glacial">you haven&apos;t asked yet.</span>
          </h2>
          <p className="max-w-xl text-base text-text-2">
            We don&apos;t ship dashboards. We ship the unified data layer your team
            can build any clinical use case on top of.
          </p>
          <Link href="/analyst">
            <Button variant="primary" size="lg">
              Talk to your data
              <ArrowRight className="h-4 w-4" />
            </Button>
          </Link>
        </div>
      </section>
    </>
  );
}

function Pillar({
  icon: Icon,
  title,
  text,
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  text: string;
}) {
  return (
    <div className="space-y-4">
      <div className="grid h-12 w-12 place-items-center rounded-lg border border-glacial/30 bg-glacial/10">
        <Icon className="h-6 w-6 text-glacial" />
      </div>
      <h3 className="font-display text-xl font-semibold text-text-0">{title}</h3>
      <p className="text-sm leading-relaxed text-text-2">{text}</p>
    </div>
  );
}
