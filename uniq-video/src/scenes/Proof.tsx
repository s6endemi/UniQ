import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { fontFamily } from "../fonts";

const METRICS = [
  { value: "5,374", label: "Patients", sub: "unified profiles" },
  { value: "8,835", label: "Treatments", sub: "tracked end-to-end" },
  { value: "19", label: "Medications", sub: "Mounjaro to Sildenafil" },
  { value: "2", label: "Brands", sub: "zero code changes" },
];

export const Proof: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Phase pill
  const pillP = spring({ frame, fps, config: { damping: 200 } });

  // Headline
  const headP = spring({
    frame,
    fps,
    delay: Math.round(0.3 * fps),
    config: { damping: 200 },
  });

  // Hero counter
  const heroP = spring({
    frame,
    fps,
    delay: Math.round(0.8 * fps),
    config: { damping: 200 },
  });
  const heroCount = Math.floor(
    interpolate(
      frame,
      [Math.round(0.8 * fps), Math.round(2.2 * fps)],
      [0, 134000],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
    ),
  );

  // Footer
  const footP = spring({
    frame,
    fps,
    delay: Math.round(4.5 * fps),
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
          backgroundColor: "rgba(0,122,255,0.07)",
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
            backgroundColor: "#007AFF",
          }}
        />
        <span
          style={{
            fontSize: 13,
            fontWeight: 600,
            color: "#007AFF",
            letterSpacing: 2,
            textTransform: "uppercase" as const,
          }}
        >
          The Scale
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
          marginBottom: 48,
          textAlign: "center",
        }}
      >
        Real data. Production scale.
      </div>

      {/* Hero number */}
      <div
        style={{
          opacity: interpolate(heroP, [0, 1], [0, 1]),
          transform: `scale(${interpolate(heroP, [0, 1], [0.95, 1])})`,
          textAlign: "center",
          marginBottom: 52,
        }}
      >
        <div
          style={{
            fontSize: 120,
            fontWeight: 800,
            color: "#1D1D1F",
            letterSpacing: -5,
            lineHeight: 1,
          }}
        >
          {heroCount > 0 ? heroCount.toLocaleString("en-US") : "\u00A0"}
        </div>
        <div
          style={{
            fontSize: 18,
            fontWeight: 500,
            color: "#86868B",
            marginTop: 14,
          }}
        >
          patient survey rows processed
        </div>
      </div>

      {/* Metric cards */}
      <div
        style={{
          display: "flex",
          gap: 20,
          maxWidth: 1000,
          width: "100%",
        }}
      >
        {METRICS.map((m, i) => {
          const delay = Math.round((2.6 + i * 0.3) * fps);
          const s = spring({
            frame,
            fps,
            delay,
            config: { damping: 200 },
          });

          return (
            <div
              key={m.label}
              style={{
                flex: 1,
                opacity: interpolate(s, [0, 1], [0, 1]),
                transform: `translateY(${interpolate(s, [0, 1], [20, 0])}px)`,
                backgroundColor: "#FFFFFF",
                borderRadius: 16,
                padding: "28px 20px",
                boxShadow: "0 2px 16px rgba(0,0,0,0.04)",
                textAlign: "center",
              }}
            >
              <div
                style={{
                  fontSize: 40,
                  fontWeight: 800,
                  color: "#1D1D1F",
                  letterSpacing: -1,
                  lineHeight: 1,
                }}
              >
                {m.value}
              </div>
              <div
                style={{
                  fontSize: 15,
                  fontWeight: 600,
                  color: "#1D1D1F",
                  marginTop: 10,
                }}
              >
                {m.label}
              </div>
              <div
                style={{
                  fontSize: 12,
                  fontWeight: 400,
                  color: "#AEAEB2",
                  marginTop: 4,
                }}
              >
                {m.sub}
              </div>
            </div>
          );
        })}
      </div>

      {/* Efficiency footer */}
      <div
        style={{
          opacity: interpolate(footP, [0, 1], [0, 1]),
          marginTop: 40,
          display: "flex",
          alignItems: "center",
          gap: 24,
        }}
      >
        {["1 API call", "$0.10 total cost", "99.9% deterministic"].map(
          (item, i) => (
            <div
              key={item}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 24,
              }}
            >
              <span
                style={{
                  fontSize: 14,
                  fontWeight: 600,
                  color: "#00C9A7",
                }}
              >
                {item}
              </span>
              {i < 2 && (
                <div
                  style={{
                    width: 4,
                    height: 4,
                    borderRadius: 2,
                    backgroundColor: "#D1D1D6",
                  }}
                />
              )}
            </div>
          ),
        )}
      </div>
    </AbsoluteFill>
  );
};
