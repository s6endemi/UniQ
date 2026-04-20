import "./index.css";
import { Composition } from "remotion";
import { MyComposition } from "./Composition";

// Total: 105+255+260+200+170+130 - 5*18 = 1030 frames ≈ 34.3s at 30fps
export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="UniQ-Pitch"
        component={MyComposition}
        durationInFrames={1030}
        fps={30}
        width={1920}
        height={1080}
      />
    </>
  );
};
