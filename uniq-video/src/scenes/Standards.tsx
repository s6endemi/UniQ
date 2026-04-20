import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { fontFamily } from "../fonts";

const STANDARDS = [
  {
    name: "LOINC",
    code: "39156-5",
    desc: "Observations",
    example: "Body Mass Index",
    accent: "#00C9A7",
  },
  {
    name: "ICD-10",
    code: "I10",
    desc: "Diagnoses",
    example: "Hypertension",
    accent: "#007AFF",
  },
  {
    name: "SNOMED CT",
    code: "422587007",
    desc: "Clinical Terms",
    example: "Nausea",
    accent: "#AF52DE",
  },
  {
    name: "RxNorm",
    code: "2601734",
    desc: "Medications",
    example: "Tirzepatide",
    accent: "#FF9500",
  },
  {
    name: "FHIR R4",
    code: "3,731",
    desc: "Interoperability",
    example: "Resources exported",
    accent: "#FF3B30",
  },
];

export const Standards: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const pillP = spring({ frame, fps, config: { damping: 200 } });
  const headP = spring({
    frame,
    fps,
    delay: Math.round(0.3 * fps),
    config: { damping: 200 },
  });
  const subP = spring({
    frame,
    fps,
    delay: Math.round(0.5 * fps),
    config: { damping: 200 },
  });

  return (
    <AbsoluteFill
      style={{
        backgroundColor: "#FAFAFA",
        fontFamily,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "0 80px",
      }}
    >
      {/* Phase pill */}
      <div
        style={{
          opacity: interpolate(pillP, [0, 1], [0, 1]),
          display: "inline-flex",
          alignItems: "center",
          gap: 10,
          backgroundColor: "rgba(175,82,222,0.07)",
          borderRadius: 100,
          padding: "10px 24px",
          marginBottom: 20,
        }}
      >
        <div
          style={{
            width: 8,
            height: 8,
            borderRadius: 4,
            backgroundColor: "#AF52DE",
          }}
        />
        <span
          style={{
            fontSize: 13,
            fontWeight: 600,
            color: "#AF52DE",
            letterSpacing: 2,
            textTransform: "uppercase" as const,
          }}
        >
          Output Format
        </span>
      </div>

      {/* Headline */}
      <div
        style={{
          opacity: interpolate(headP, [0, 1], [0, 1]),
          transform: `translateY(${interpolate(headP, [0, 1], [15, 0])}px)`,
          fontSize: 44,
          fontWeight: 700,
          color: "#1D1D1F",
          letterSpacing: -1.5,
          marginBottom: 14,
          textAlign: "center",
        }}
      >
        Real medical codes. Not custom labels.
      </div>

      {/* Subtitle */}
      <div
        style={{
          opacity: interpolate(subP, [0, 1], [0, 1]),
          fontSize: 18,
          fontWeight: 400,
          color: "#86868B",
          marginBottom: 52,
          textAlign: "center",
        }}
      >
        Production-grade interoperability with any EHR system
      </div>

      {/* Standard cards */}
      <div
        style={{
          display: "flex",
          gap: 16,
          width: "100%",
          maxWidth: 1150,
        }}
      >
        {STANDARDS.map((std, i) => {
          const delay = Math.round((0.7 + i * 0.22) * fps);
          const s = spring({
            frame,
            fps,
            delay,
            config: { damping: 200 },
          });

          return (
            <div
              key={std.name}
              style={{
                flex: 1,
                opacity: interpolate(s, [0, 1], [0, 1]),
                transform: `translateY(${interpolate(s, [0, 1], [25, 0])}px)`,
                backgroundColor: "#FFFFFF",
                borderRadius: 16,
                padding: "28px 20px",
                boxShadow: "0 2px 16px rgba(0,0,0,0.04)",
                borderLeft: `4px solid ${std.accent}`,
              }}
            >
              <div
                style={{
                  fontSize: 22,
                  fontWeight: 700,
                  color: std.accent,
                  letterSpacing: -0.5,
                }}
              >
                {std.name}
              </div>
              <div
                style={{
                  fontSize: 12,
                  fontWeight: 600,
                  color: "#AEAEB2",
                  textTransform: "uppercase" as const,
                  letterSpacing: 2,
                  marginTop: 8,
                }}
              >
                {std.desc}
              </div>
              <div
                style={{
                  marginTop: 16,
                  paddingTop: 12,
                  borderTop: "1px solid #F0F0F2",
                }}
              >
                <div
                  style={{
                    fontSize: 13,
                    fontWeight: 400,
                    color: "#86868B",
                  }}
                >
                  {std.example}
                </div>
                <div
                  style={{
                    fontSize: 15,
                    fontWeight: 600,
                    color: "#1D1D1F",
                    fontFamily: "monospace",
                    marginTop: 4,
                  }}
                >
                  {std.code}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
