import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { fontFamily } from "../fonts";

export const Close: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const logoProgress = spring({
    frame,
    fps,
    config: { damping: 200 },
  });
  const logoOpacity = interpolate(logoProgress, [0, 1], [0, 1]);
  const logoScale = interpolate(logoProgress, [0, 1], [0.92, 1]);

  const lineProgress = spring({
    frame,
    fps,
    delay: 12,
    config: { damping: 200 },
  });
  const lineWidth = interpolate(lineProgress, [0, 1], [0, 64]);

  const taglineProgress = spring({
    frame,
    fps,
    delay: Math.round(0.8 * fps),
    config: { damping: 200 },
  });
  const taglineOpacity = interpolate(taglineProgress, [0, 1], [0, 1]);
  const taglineY = interpolate(taglineProgress, [0, 1], [15, 0]);

  const badgeProgress = spring({
    frame,
    fps,
    delay: Math.round(1.6 * fps),
    config: { damping: 200 },
  });
  const badgeOpacity = interpolate(badgeProgress, [0, 1], [0, 1]);

  return (
    <AbsoluteFill
      style={{
        backgroundColor: "#FAFAFA",
        fontFamily,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      {/* Subtle glow */}
      <div
        style={{
          position: "absolute",
          width: "100%",
          height: "100%",
          background:
            "radial-gradient(ellipse at 50% 45%, rgba(0,201,167,0.05) 0%, transparent 55%)",
        }}
      />

      <div style={{ textAlign: "center", position: "relative" }}>
        {/* Logo */}
        <div
          style={{
            opacity: logoOpacity,
            transform: `scale(${logoScale})`,
          }}
        >
          <span
            style={{
              fontSize: 120,
              fontWeight: 800,
              color: "#1D1D1F",
              letterSpacing: -4,
              lineHeight: 1,
            }}
          >
            Uni
          </span>
          <span
            style={{
              fontSize: 120,
              fontWeight: 800,
              color: "#00C9A7",
              letterSpacing: -4,
              lineHeight: 1,
            }}
          >
            Q
          </span>
        </div>

        {/* Accent line */}
        <div
          style={{
            display: "flex",
            justifyContent: "center",
            marginTop: 16,
          }}
        >
          <div
            style={{
              width: lineWidth,
              height: 3,
              backgroundColor: "#00C9A7",
              borderRadius: 2,
            }}
          />
        </div>

        {/* Tagline */}
        <div
          style={{
            opacity: taglineOpacity,
            transform: `translateY(${taglineY}px)`,
            marginTop: 32,
          }}
        >
          <div
            style={{
              fontSize: 22,
              fontWeight: 400,
              color: "#86868B",
              lineHeight: 1.5,
            }}
          >
            Fragmented data in.
          </div>
          <div
            style={{
              fontSize: 22,
              fontWeight: 600,
              color: "#1D1D1F",
              lineHeight: 1.5,
            }}
          >
            Unified, coded, interoperable healthcare data out.
          </div>
        </div>

        {/* Badge */}
        <div
          style={{
            opacity: badgeOpacity,
            marginTop: 40,
          }}
        >
          <span
            style={{
              display: "inline-block",
              backgroundColor: "#00C9A7",
              borderRadius: 100,
              padding: "10px 32px",
              fontSize: 14,
              fontWeight: 600,
              color: "#FFFFFF",
              letterSpacing: 1,
            }}
          >
            Wellster Hackathon 2025
          </span>
        </div>
      </div>
    </AbsoluteFill>
  );
};
