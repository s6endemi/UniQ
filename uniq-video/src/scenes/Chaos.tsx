import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { fontFamily } from "../fonts";

const QUESTION_IDS = [
  37206, 37208, 46949, 46951, 72827, 72832, 80339, 80341, 81404, 81406,
  81679, 81681, 90332, 90334, 95564, 95566, 108754, 108756, 108856, 108858,
  108958, 108960, 109542, 109544, 37150, 49851, 72763, 80366, 81706, 90355,
  95591, 95967, 4553, 8802, 13848, 15321, 17400, 23679, 35335, 41224,
];

// Scattered positions [x%, y%, rotation] — ring around center
const ID_POS: [number, number, number][] = [
  [5, 5, -5], [17, 7, 4], [30, 4, -3], [44, 8, 6], [57, 5, -4],
  [70, 7, 3], [83, 4, -6], [94, 8, 5],
  [4, 20, 4], [15, 23, -6], [83, 21, 5], [95, 18, -3],
  [3, 36, -4], [5, 50, 6], [93, 38, -5], [96, 52, 4],
  [4, 66, 5], [13, 71, -4], [85, 67, 3], [95, 73, -6],
  [6, 84, -3], [19, 88, 5], [31, 85, -6], [43, 91, 4],
  [57, 87, -3], [69, 90, 5], [81, 85, -4], [93, 89, 6],
  [26, 16, 3], [53, 15, -5], [74, 17, 4],
  [26, 76, -4], [50, 79, 5], [74, 77, -3],
  [9, 44, 4], [90, 46, -5], [22, 57, -3], [79, 58, 4],
  [36, 73, 5], [65, 74, -4],
];

const TEXT_VARIANTS = [
  { text: '"Normal blood pressure"', x: 12, y: 29, rot: -2 },
  { text: '"Normaler Blutdruck"', x: 74, y: 32, rot: 3 },
  { text: '"Bluthochdruck, Ramipril 5mg"', x: 8, y: 61, rot: 2 },
  { text: '"Hypertension"', x: 81, y: 63, rot: -3 },
];

export const Chaos: React.FC = () => {
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

  // Question card
  const cardP = spring({
    frame,
    fps,
    delay: Math.round(0.8 * fps),
    config: { damping: 200 },
  });

  // ID scatter
  const idStart = Math.round(1.4 * fps);
  const idEnd = Math.round(4.5 * fps);
  const visibleIds = Math.min(
    QUESTION_IDS.length,
    Math.floor(
      interpolate(frame, [idStart, idEnd], [0, QUESTION_IDS.length], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      }),
    ),
  );

  // Text variant start
  const varStart = Math.round(2 * fps);

  // Counter
  const counterVal = Math.floor(
    interpolate(frame, [idStart, idEnd], [0, 263], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    }),
  );

  // Emphasis
  const emphP = spring({
    frame,
    fps,
    delay: Math.round(5 * fps),
    config: { damping: 200 },
  });
  const isRed = emphP > 0.3;
  const emphScale = interpolate(emphP, [0, 1], [1, 1.08]);

  return (
    <AbsoluteFill style={{ backgroundColor: "#FAFAFA", fontFamily }}>
      {/* Scattered IDs */}
      {QUESTION_IDS.slice(0, visibleIds).map((id, i) => {
        const pos = ID_POS[i];
        const delay =
          idStart + (i / QUESTION_IDS.length) * (idEnd - idStart);
        const s = spring({
          frame,
          fps,
          delay,
          config: { damping: 200 },
        });
        return (
          <div
            key={id}
            style={{
              position: "absolute",
              left: `${pos[0]}%`,
              top: `${pos[1]}%`,
              transform: `rotate(${pos[2]}deg) scale(${interpolate(s, [0, 1], [0.5, 1])})`,
              opacity: interpolate(s, [0, 1], [0, 0.65]),
              backgroundColor: "#F0F0F2",
              border: "1px solid #E5E5EA",
              borderRadius: 8,
              padding: "5px 12px",
              fontSize: 11,
              fontWeight: 500,
              fontFamily: "monospace",
              color: "#AEAEB2",
              whiteSpace: "nowrap" as const,
            }}
          >
            #{id}
          </div>
        );
      })}

      {/* Text variant fragments */}
      {TEXT_VARIANTS.map((v, i) => {
        const delay = varStart + i * Math.round(0.4 * fps);
        const s = spring({
          frame,
          fps,
          delay,
          config: { damping: 200 },
        });
        return (
          <div
            key={v.text}
            style={{
              position: "absolute",
              left: `${v.x}%`,
              top: `${v.y}%`,
              transform: `rotate(${v.rot}deg)`,
              opacity: interpolate(s, [0, 1], [0, 0.55]),
              backgroundColor: "#FFFFFF",
              border: "1px solid #E5E5EA",
              borderRadius: 12,
              padding: "8px 16px",
              fontSize: 13,
              fontWeight: 400,
              color: "#86868B",
              fontStyle: "italic" as const,
              whiteSpace: "nowrap" as const,
              boxShadow: "0 1px 8px rgba(0,0,0,0.04)",
            }}
          >
            {v.text}
          </div>
        );
      })}

      {/* Center layer */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {/* Phase pill */}
        <div
          style={{
            opacity: interpolate(pillP, [0, 1], [0, 1]),
            display: "inline-flex",
            alignItems: "center",
            gap: 10,
            backgroundColor: "rgba(255,59,48,0.07)",
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
              backgroundColor: "#FF3B30",
            }}
          />
          <span
            style={{
              fontSize: 13,
              fontWeight: 600,
              color: "#FF3B30",
              letterSpacing: 2,
              textTransform: "uppercase" as const,
            }}
          >
            The Problem
          </span>
        </div>

        {/* Headline */}
        <div
          style={{
            opacity: interpolate(headP, [0, 1], [0, 1]),
            transform: `translateY(${interpolate(headP, [0, 1], [20, 0])}px)`,
            fontSize: 52,
            fontWeight: 700,
            color: "#1D1D1F",
            letterSpacing: -1.5,
            marginBottom: 24,
          }}
        >
          One question.
        </div>

        {/* Question card */}
        <div
          style={{
            opacity: interpolate(cardP, [0, 1], [0, 1]),
            transform: `scale(${interpolate(cardP, [0, 1], [0.95, 1])})`,
            backgroundColor: "#FFFFFF",
            borderRadius: 20,
            padding: "24px 40px",
            boxShadow: "0 4px 24px rgba(0,0,0,0.08)",
            maxWidth: 640,
            marginBottom: 40,
            zIndex: 10,
          }}
        >
          <span
            style={{
              fontSize: 19,
              fontWeight: 400,
              color: "#1D1D1F",
              lineHeight: 1.6,
              fontStyle: "italic" as const,
            }}
          >
            &ldquo;Do you suffer from any of the following
            conditions?&rdquo;
          </span>
        </div>

        {/* Counter */}
        {counterVal > 0 && (
          <div
            style={{
              textAlign: "center",
              transform: `scale(${emphScale})`,
              zIndex: 10,
            }}
          >
            <div
              style={{
                fontSize: 80,
                fontWeight: 800,
                color: isRed ? "#FF3B30" : "#1D1D1F",
                letterSpacing: -3,
                lineHeight: 1,
              }}
            >
              {counterVal}
            </div>
            <div
              style={{
                fontSize: 17,
                fontWeight: 500,
                color: isRed ? "#FF3B30" : "#86868B",
                marginTop: 10,
              }}
            >
              different IDs &mdash;{" "}
              <span style={{ fontWeight: 700 }}>same clinical question</span>
            </div>
          </div>
        )}
      </div>
    </AbsoluteFill>
  );
};
