"use client";

import { motion } from "motion/react";
import { Database, Sparkles, Layers, ShieldCheck, Share2 } from "lucide-react";

interface Stage {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  metric: string;
  description: string;
  hue: "glacial" | "mineral";
}

const STAGES: Stage[] = [
  {
    icon: Database,
    title: "Ingest",
    metric: "133,996 rows",
    description: "Raw questionnaire export from any telehealth schema",
    hue: "glacial",
  },
  {
    icon: Sparkles,
    title: "Discover",
    metric: "20 categories",
    description: "AI classifier groups questions into clinical concepts",
    hue: "glacial",
  },
  {
    icon: Layers,
    title: "Map",
    metric: "FHIR + LOINC",
    description: "Semantic mapping proposes resource type & medical codes",
    hue: "mineral",
  },
  {
    icon: ShieldCheck,
    title: "Review",
    metric: "human in the loop",
    description: "Clinician approves, overrides, or rejects each mapping",
    hue: "mineral",
  },
  {
    icon: Share2,
    title: "Export",
    metric: "FHIR R4 / SQL",
    description: "Standards-compliant data, queryable by your AI analyst",
    hue: "mineral",
  },
];

export function PipelineTimeline() {
  return (
    <div className="relative">
      {/* Center axis */}
      <div className="absolute left-0 right-0 top-12 hidden h-px bg-gradient-to-r from-transparent via-ink-600 to-transparent md:block" />

      <div className="grid grid-cols-1 gap-8 md:grid-cols-5 md:gap-4">
        {STAGES.map((stage, i) => {
          const Icon = stage.icon;
          const accent = stage.hue === "glacial" ? "text-glacial" : "text-mineral";
          const ring =
            stage.hue === "glacial"
              ? "border-glacial/40 bg-glacial/10"
              : "border-mineral/40 bg-mineral/10";

          return (
            <motion.div
              key={stage.title}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-50px" }}
              transition={{ duration: 0.5, delay: i * 0.1, ease: "easeOut" }}
              className="relative flex flex-col items-center text-center"
            >
              <div
                className={`relative z-10 grid h-24 w-24 place-items-center rounded-full border ${ring}`}
              >
                <Icon className={`h-9 w-9 ${accent}`} />
                <div className="absolute -bottom-2 left-1/2 -translate-x-1/2 rounded-full bg-ink-900 px-2 py-0.5 font-mono text-[10px] text-text-3 border border-ink-700">
                  {String(i + 1).padStart(2, "0")}
                </div>
              </div>

              <div className="mt-6 space-y-1">
                <h3 className="font-display text-lg font-semibold text-text-0">
                  {stage.title}
                </h3>
                <p className={`font-mono text-xs uppercase tracking-wider ${accent}`}>
                  {stage.metric}
                </p>
                <p className="mx-auto max-w-[160px] text-xs leading-relaxed text-text-3">
                  {stage.description}
                </p>
              </div>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
