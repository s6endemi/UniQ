import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { fontFamily } from "../fonts";

export const Logo: React.FC = () => {
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
    delay: 14,
    config: { damping: 200 },
  });
  const lineWidth = interpolate(lineProgress, [0, 1], [0, 72]);

  const subProgress = spring({
    frame,
    fps,
    delay: 22,
    config: { damping: 200 },
  });
  const subOpacity = interpolate(subProgress, [0, 1], [0, 1]);
  const subY = interpolate(subProgress, [0, 1], [12, 0]);

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
      {/* Subtle green radial glow */}
      <div
        style={{
          position: "absolute",
          width: "100%",
          height: "100%",
          background:
            "radial-gradient(ellipse at 50% 45%, rgba(0,201,167,0.06) 0%, transparent 60%)",
        }}
      />

      <div style={{ textAlign: "center", position: "relative" }}>
        <div
          style={{
            opacity: logoOpacity,
            transform: `scale(${logoScale})`,
          }}
        >
          <span
            style={{
              fontSize: 140,
              fontWeight: 800,
              color: "#1D1D1F",
              letterSpacing: -5,
              lineHeight: 1,
            }}
          >
            Uni
          </span>
          <span
            style={{
              fontSize: 140,
              fontWeight: 800,
              color: "#00C9A7",
              letterSpacing: -5,
              lineHeight: 1,
            }}
          >
            Q
          </span>
        </div>

        <div
          style={{
            display: "flex",
            justifyContent: "center",
            marginTop: 20,
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

        <div
          style={{
            opacity: subOpacity,
            transform: `translateY(${subY}px)`,
            marginTop: 24,
          }}
        >
          <span
            style={{
              fontSize: 20,
              fontWeight: 400,
              color: "#86868B",
              letterSpacing: 6,
              textTransform: "uppercase" as const,
            }}
          >
            Unified Questionnaire Intelligence
          </span>
        </div>
      </div>
    </AbsoluteFill>
  );
};
