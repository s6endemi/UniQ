"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

interface FieldPos {
  x: number;
  y: number;
  r?: number;
}

interface LatticeField {
  label: string;
  bucket: "Vitals" | "Labs" | "Medications" | "Conditions" | "Surveys";
  raw: FieldPos;
  struct: FieldPos;
}

// Hero lattice fields — chaotic & clean positions. Ported from data.js.
const LATTICE_FIELDS: LatticeField[] = [
  { label: "sys_bp", bucket: "Vitals", raw: { x: 8, y: 18, r: -7 }, struct: { x: 4, y: 72 } },
  { label: "bp_sys", bucket: "Vitals", raw: { x: 22, y: 52, r: 4 }, struct: { x: 11, y: 72 } },
  { label: "bmi_calc", bucket: "Vitals", raw: { x: 72, y: 14, r: 6 }, struct: { x: 18, y: 72 } },
  { label: "weight_kg", bucket: "Vitals", raw: { x: 58, y: 34, r: -3 }, struct: { x: 4, y: 80 } },
  { label: "hr", bucket: "Vitals", raw: { x: 40, y: 66, r: 8 }, struct: { x: 11, y: 80 } },
  { label: "height_cm", bucket: "Vitals", raw: { x: 12, y: 44, r: 12 }, struct: { x: 18, y: 80 } },
  { label: "a1c", bucket: "Labs", raw: { x: 82, y: 60, r: -6 }, struct: { x: 30, y: 72 } },
  { label: "glucose_fasting", bucket: "Labs", raw: { x: 32, y: 20, r: 3 }, struct: { x: 40, y: 72 } },
  { label: "cholesterol_t", bucket: "Labs", raw: { x: 66, y: 50, r: 9 }, struct: { x: 30, y: 80 } },
  { label: "triglyc", bucket: "Labs", raw: { x: 48, y: 8, r: -9 }, struct: { x: 40, y: 80 } },
  { label: "rx_tirzepatide", bucket: "Medications", raw: { x: 20, y: 72, r: 6 }, struct: { x: 55, y: 72 } },
  { label: "mounjaro_dose", bucket: "Medications", raw: { x: 76, y: 38, r: -2 }, struct: { x: 66, y: 72 } },
  { label: "rx_semaglutide", bucket: "Medications", raw: { x: 52, y: 52, r: 5 }, struct: { x: 55, y: 80 } },
  { label: "dx_t2d", bucket: "Conditions", raw: { x: 62, y: 74, r: -5 }, struct: { x: 81, y: 72 } },
  { label: "hypertension", bucket: "Conditions", raw: { x: 6, y: 72, r: 11 }, struct: { x: 92, y: 72 } },
  { label: "obesity_bmi30", bucket: "Conditions", raw: { x: 86, y: 26, r: -3 }, struct: { x: 81, y: 80 } },
  { label: "phq9", bucket: "Surveys", raw: { x: 38, y: 40, r: 7 }, struct: { x: 92, y: 80 } },
  { label: "sleep_q", bucket: "Surveys", raw: { x: 90, y: 76, r: -8 }, struct: { x: 81, y: 88 } },
];

function Lattice() {
  const [structured, setStructured] = useState(false);
  const [autoMode, setAutoMode] = useState(true);

  useEffect(() => {
    if (!autoMode) return;
    const t = setInterval(() => setStructured((s) => !s), 5500);
    return () => clearInterval(t);
  }, [autoMode]);

  return (
    <div className={`lattice ${structured ? "is-structured" : ""}`}>
      <div className="lattice__frame">
        <div className="lattice__caption">
          <span>{structured ? "STATE · STRUCTURED" : "STATE · RAW INGEST"}</span>
          <span>5,374 patients · 48 source fields · 20 mappings</span>
        </div>
        <div />
      </div>

      <div className="lattice__toggle" role="group" aria-label="Lattice state">
        <button
          aria-pressed={!structured}
          onClick={() => {
            setAutoMode(false);
            setStructured(false);
          }}
        >
          Raw
        </button>
        <button
          aria-pressed={structured}
          onClick={() => {
            setAutoMode(false);
            setStructured(true);
          }}
        >
          Structured
        </button>
      </div>

      <div className="lattice__scene">
        {LATTICE_FIELDS.map((f, i) => {
          const pos = structured ? f.struct : f.raw;
          const rot = structured ? 0 : f.raw.r ?? 0;
          return (
            <div
              key={f.label}
              className={`field ${structured ? "is-structured" : ""}`}
              style={{
                left: `${pos.x}%`,
                top: `${pos.y}%`,
                transform: `rotate(${rot}deg)`,
                transitionDelay: structured
                  ? `${i * 28}ms`
                  : `${(LATTICE_FIELDS.length - i) * 12}ms`,
              }}
            >
              {f.label}
            </div>
          );
        })}
      </div>

      <div className="lattice__buckets">
        <div className="bucket">
          Category<b>Vitals</b>
        </div>
        <div className="bucket">
          Category<b>Labs</b>
        </div>
        <div className="bucket">
          Category<b>Medications</b>
        </div>
        <div className="bucket">
          Category<b>Conditions</b>
        </div>
        <div className="bucket">
          Category<b>Surveys</b>
        </div>
      </div>
    </div>
  );
}

export default function StoryPage() {
  return (
    <div className="room" data-screen-label="01 Story">
      <main>
        <section className="story-hero">
          <div className="container container--wide">
            <div className="story-hero__eyebrow">
              <span className="t-eyebrow">UniQ · v0.6 preview</span>
            </div>

            <h1 className="story-hero__claim">
              Healthcare data
              <br />
              arrives as <span className="faded">chaos.</span>
              <br />
              We ship it as <em>structure.</em>
            </h1>

            <p className="story-hero__lede">
              UniQ is the data layer beneath your telehealth stack. We ingest
              fragmented questionnaire and clinical data, discover its clinical
              structure with AI, let your clinicians approve every decision, and
              expose the result as a FHIR-compliant, queryable substrate anyone
              can build on.
            </p>

            <div className="story-hero__cta-row">
              <Link href="/start" className="btn btn--primary">
                Start demo <span className="arrow">→</span>
              </Link>
              <Link href="/analyst" className="btn btn--ghost">
                Skip to analyst <span className="arrow">→</span>
              </Link>
              <span className="t-meta" style={{ marginLeft: 8 }}>
                or press <span className="kbd">s</span> ·{" "}
                <span className="kbd">3</span>
              </span>
            </div>

            <Lattice />
          </div>
        </section>

        <section className="story-section">
          <div className="container container--wide">
            <div className="story-section__head">
              <span className="story-section__num">§ 01 — Pipeline</span>
              <h2 className="story-section__title">
                Four stages, one <em>substrate.</em>
              </h2>
            </div>

            <div className="pillars">
              <div className="pillar">
                <div className="pillar__num">01 · Ingest</div>
                <h3 className="pillar__title">Raw feeds land as-is.</h3>
                <p className="pillar__body">
                  Questionnaires, lab CSVs, EHR exports, SDK events. No
                  normalization required upstream.
                </p>
              </div>
              <div className="pillar">
                <div className="pillar__num">02 · Discover</div>
                <h3 className="pillar__title">AI proposes structure.</h3>
                <p className="pillar__body">
                  Every field is matched to a FHIR resource and coded to LOINC /
                  RxNorm / SNOMED / ICD-10 with a confidence score.
                </p>
              </div>
              <div className="pillar">
                <div className="pillar__num">03 · Review</div>
                <h3 className="pillar__title">Clinicians hold the pen.</h3>
                <p className="pillar__body">
                  Approve, override or reject. Decisions persist across pipeline
                  re-runs — the AI doesn&apos;t overwrite your judgment.
                </p>
              </div>
              <div className="pillar">
                <div className="pillar__num">04 · Query</div>
                <h3 className="pillar__title">Build anything on top.</h3>
                <p className="pillar__body">
                  Dashboards, alert systems, AI analysts, integrations — all
                  reading one unified FHIR substrate.
                </p>
              </div>
            </div>
          </div>
        </section>

        <section className="story-section" style={{ paddingTop: 64 }}>
          <div className="container container--wide">
            <div className="stats">
              <div className="stat">
                <div className="stat__value">5,374</div>
                <div className="stat__label">patient records ingested</div>
              </div>
              <div className="stat">
                <div className="stat__value">20</div>
                <div className="stat__label">semantic mappings proposed</div>
              </div>
              <div className="stat">
                <div className="stat__value">
                  94<span className="unit">%</span>
                </div>
                <div className="stat__label">average confidence · high tier</div>
              </div>
              <div className="stat">
                <div className="stat__value">
                  0.42<span className="unit">s</span>
                </div>
                <div className="stat__label">median artifact generation</div>
              </div>
            </div>
          </div>
        </section>

        <section className="story-section">
          <div className="container container--wide">
            <div className="story-section__head">
              <span className="story-section__num">§ 02 — Surfaces</span>
              <h2 className="story-section__title">
                Step into either <em>room.</em>
              </h2>
            </div>

            <div className="pathways">
              <Link href="/review" className="pathway">
                <div className="pathway__eyebrow">
                  <span>Surface 01</span>
                  <span>/ review</span>
                </div>
                <h3 className="pathway__title">
                  The <em>review</em> desk.
                </h3>
                <p className="pathway__desc">
                  Twenty AI proposals waiting for a human decision. Approve,
                  override with field edits, reject. Your judgment persists
                  across re-runs.
                </p>
                <span className="pathway__enter">
                  Enter <span className="arrow">→</span>
                </span>
              </Link>

              <Link href="/analyst" className="pathway">
                <div className="pathway__eyebrow">
                  <span>Surface 02</span>
                  <span>/ analyst</span>
                </div>
                <h3 className="pathway__title">
                  The <em>analyst</em> room.
                </h3>
                <p className="pathway__desc">
                  Ask in plain language, receive an artifact. Dashboards,
                  cohorts, FHIR bundles — generated against real data, rendered
                  beside you, downloadable.
                </p>
                <span className="pathway__enter">
                  Enter <span className="arrow">→</span>
                </span>
              </Link>
            </div>
          </div>
        </section>

        <footer className="footer">
          <div className="container container--wide footer__inner">
            <span>UniQ · infrastructure for clinical data · 2026</span>
            <span>FHIR R4 · HIPAA-ready · SOC 2 Type II</span>
          </div>
        </footer>
      </main>
    </div>
  );
}
