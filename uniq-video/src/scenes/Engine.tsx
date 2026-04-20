import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { fontFamily } from "../fonts";

export const Engine: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const fmt = (n: number) => n.toLocaleString("en-US");

  // Phase pill
  const pillP = spring({ frame, fps, config: { damping: 200 } });

  // Headline
  const headP = spring({
    frame,
    fps,
    delay: Math.round(0.3 * fps),
    config: { damping: 200 },
  });

  // Before number — counts up slowly (heavy, lots of data)
  const beforeP = spring({
    frame,
    fps,
    delay: Math.round(0.8 * fps),
    config: { damping: 200 },
  });
  const beforeCount = Math.floor(
    interpolate(
      frame,
      [Math.round(0.8 * fps), Math.round(2 * fps)],
      [0, 4553],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
    ),
  );

  // Green Q circle — THE moment (slight bounce for pop)
  const circleP = spring({
    frame,
    fps,
    delay: Math.round(2.4 * fps),
    config: { damping: 12, stiffness: 200 },
  });

  // Lines extending from Q
  const leftLineP = spring({
    frame,
    fps,
    delay: Math.round(2.7 * fps),
    config: { damping: 200 },
  });
  const rightLineP = spring({
    frame,
    fps,
    delay: Math.round(2.9 * fps),
    config: { damping: 200 },
  });

  // After number — counts up fast (efficient!)
  const afterP = spring({
    frame,
    fps,
    delay: Math.round(3.2 * fps),
    config: { damping: 200 },
  });
  const afterCount = Math.floor(
    interpolate(
      frame,
      [Math.round(3.2 * fps), Math.round(3.7 * fps)],
      [0, 26],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
    ),
  );

  // Sub-cards
  const sub1P = spring({
    frame,
    fps,
    delay: Math.round(4.5 * fps),
    config: { damping: 200 },
  });
  const sub2P = spring({
    frame,
    fps,
    delay: Math.round(4.9 * fps),
    config: { damping: 200 },
  });

  // Footer
  const footP = spring({
    frame,
    fps,
    delay: Math.round(5.8 * fps),
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
      {/* Subtle green glow */}
      <div
        style={{
          position: "absolute",
          width: "100%",
          height: "100%",
          background:
            "radial-gradient(ellipse at 50% 40%, rgba(0,201,167,0.05) 0%, transparent 60%)",
        }}
      />

      {/* Phase pill */}
      <div
        style={{
          opacity: interpolate(pillP, [0, 1], [0, 1]),
          display: "inline-flex",
          alignItems: "center",
          gap: 10,
          backgroundColor: "rgba(0,201,167,0.08)",
          borderRadius: 100,
          padding: "10px 24px",
          marginBottom: 20,
          position: "relative",
        }}
      >
        <div
          style={{
            width: 8,
            height: 8,
            borderRadius: 4,
            backgroundColor: "#00C9A7",
          }}
        />
        <span
          style={{
            fontSize: 13,
            fontWeight: 600,
            color: "#00C9A7",
            letterSpacing: 2,
            textTransform: "uppercase" as const,
          }}
        >
          The Solution
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
          position: "relative",
        }}
      >
        From chaos to clarity.
      </div>

      {/* ===== Hero transformation card ===== */}
      <div
        style={{
          backgroundColor: "#FFFFFF",
          borderRadius: 24,
          padding: "52px 56px",
          boxShadow: "0 4px 32px rgba(0,0,0,0.06)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          maxWidth: 960,
          width: "100%",
          position: "relative",
          marginBottom: 24,
        }}
      >
        {/* Before */}
        <div
          style={{
            flex: 1,
            textAlign: "center",
            opacity: interpolate(beforeP, [0, 1], [0, 1]),
            transform: `translateX(${interpolate(beforeP, [0, 1], [-20, 0])}px)`,
          }}
        >
          <div
            style={{
              fontSize: 88,
              fontWeight: 800,
              color: "#C7C7CC",
              letterSpacing: -3,
              lineHeight: 1,
            }}
          >
            {beforeCount > 0 ? fmt(beforeCount) : "\u00A0"}
          </div>
          <div
            style={{
              fontSize: 15,
              fontWeight: 500,
              color: "#AEAEB2",
              marginTop: 12,
            }}
          >
            fragmented question IDs
          </div>
        </div>

        {/* Processing: line → Q → line */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            margin: "0 4px",
            flexShrink: 0,
          }}
        >
          <div
            style={{
              width: interpolate(leftLineP, [0, 1], [0, 48]),
              height: 3,
              backgroundColor: "#00C9A7",
              borderRadius: 2,
              opacity: interpolate(leftLineP, [0, 1], [0, 0.4]),
            }}
          />
          <div
            style={{
              width: 68,
              height: 68,
              borderRadius: 34,
              backgroundColor: "#00C9A7",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              transform: `scale(${interpolate(circleP, [0, 1], [0, 1])})`,
              boxShadow: "0 4px 24px rgba(0,201,167,0.35)",
              flexShrink: 0,
            }}
          >
            <span
              style={{ fontSize: 30, fontWeight: 800, color: "#FFFFFF" }}
            >
              Q
            </span>
          </div>
          <div
            style={{
              width: interpolate(rightLineP, [0, 1], [0, 48]),
              height: 3,
              backgroundColor: "#00C9A7",
              borderRadius: 2,
              opacity: interpolate(rightLineP, [0, 1], [0, 0.4]),
            }}
          />
        </div>

        {/* After */}
        <div
          style={{
            flex: 1,
            textAlign: "center",
            opacity: interpolate(afterP, [0, 1], [0, 1]),
            transform: `translateX(${interpolate(afterP, [0, 1], [20, 0])}px)`,
          }}
        >
          <div
            style={{
              fontSize: 88,
              fontWeight: 800,
              color: "#00C9A7",
              letterSpacing: -3,
              lineHeight: 1,
              textShadow: "0 0 40px rgba(0,201,167,0.15)",
            }}
          >
            {afterCount > 0 ? afterCount : "\u00A0"}
          </div>
          <div
            style={{
              fontSize: 15,
              fontWeight: 500,
              color: "#1D1D1F",
              marginTop: 12,
            }}
          >
            clinical categories
          </div>
        </div>
      </div>

      {/* ===== Supporting transformation cards ===== */}
      <div
        style={{
          display: "flex",
          gap: 16,
          maxWidth: 960,
          width: "100%",
          position: "relative",
          marginBottom: 28,
        }}
      >
        {/* Answer variants */}
        <div
          style={{
            flex: 1,
            opacity: interpolate(sub1P, [0, 1], [0, 1]),
            transform: `translateY(${interpolate(sub1P, [0, 1], [20, 0])}px)`,
            backgroundColor: "#FFFFFF",
            borderRadius: 16,
            padding: "22px 28px",
            boxShadow: "0 2px 16px rgba(0,0,0,0.04)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div>
            <div
              style={{ fontSize: 15, fontWeight: 600, color: "#1D1D1F" }}
            >
              Answer variants
            </div>
            <div
              style={{
                fontSize: 13,
                fontWeight: 400,
                color: "#AEAEB2",
                marginTop: 2,
              }}
            >
              Cross-language DE &harr; EN
            </div>
          </div>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
            }}
          >
            <span
              style={{
                fontSize: 28,
                fontWeight: 800,
                color: "#C7C7CC",
              }}
            >
              416
            </span>
            <span style={{ fontSize: 22, color: "#00C9A7" }}>
              &rarr;
            </span>
            <span
              style={{
                fontSize: 28,
                fontWeight: 800,
                color: "#00C9A7",
              }}
            >
              164
            </span>
          </div>
        </div>

        {/* Quality alerts */}
        <div
          style={{
            flex: 1,
            opacity: interpolate(sub2P, [0, 1], [0, 1]),
            transform: `translateY(${interpolate(sub2P, [0, 1], [20, 0])}px)`,
            backgroundColor: "#FFFFFF",
            borderRadius: 16,
            padding: "22px 28px",
            boxShadow: "0 2px 16px rgba(0,0,0,0.04)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div>
            <div
              style={{ fontSize: 15, fontWeight: 600, color: "#1D1D1F" }}
            >
              Quality alerts
            </div>
            <div
              style={{
                fontSize: 13,
                fontWeight: 400,
                color: "#AEAEB2",
                marginTop: 2,
              }}
            >
              BMI gaps, med switches
            </div>
          </div>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
            }}
          >
            <span
              style={{
                fontSize: 28,
                fontWeight: 800,
                color: "#C7C7CC",
              }}
            >
              0
            </span>
            <span style={{ fontSize: 22, color: "#00C9A7" }}>
              &rarr;
            </span>
            <span
              style={{
                fontSize: 28,
                fontWeight: 800,
                color: "#00C9A7",
              }}
            >
              1,010
            </span>
          </div>
        </div>
      </div>

      {/* Footer */}
      <div
        style={{
          opacity: interpolate(footP, [0, 1], [0, 1]),
          display: "flex",
          alignItems: "center",
          gap: 24,
          position: "relative",
        }}
      >
        {[
          "1 API call",
          "$0.10 total",
          "99.9% deterministic",
          "Human-in-the-loop",
        ].map((item, i) => (
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
                color: "#86868B",
              }}
            >
              {item}
            </span>
            {i < 3 && (
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
        ))}
      </div>
    </AbsoluteFill>
  );
};
