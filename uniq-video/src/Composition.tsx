import { TransitionSeries, linearTiming } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";

import { Logo } from "./scenes/Logo";
import { Chaos } from "./scenes/Chaos";
import { Engine } from "./scenes/Engine";
import { Proof } from "./scenes/Proof";
import { Standards } from "./scenes/Standards";
import { Close } from "./scenes/Close";

const LOGO = 105; // 3.5s  — brand
const CHAOS = 255; // 8.5s  — problem: scattered IDs, overwhelming
const ENGINE = 260; // 8.67s — solution: hero transformation 4553→26
const PROOF = 200; // 6.67s — scale: 134K hero counter + metrics
const STANDARDS = 170; // 5.67s — medical codes
const CLOSE = 130; // 4.33s — tagline + close

const T = 18; // fade transition

// Total: 105+255+260+200+170+130 - 5*18 = 1030 frames ≈ 34.3s

export const MyComposition: React.FC = () => {
  return (
    <TransitionSeries>
      <TransitionSeries.Sequence durationInFrames={LOGO}>
        <Logo />
      </TransitionSeries.Sequence>

      <TransitionSeries.Transition
        presentation={fade()}
        timing={linearTiming({ durationInFrames: T })}
      />

      <TransitionSeries.Sequence durationInFrames={CHAOS}>
        <Chaos />
      </TransitionSeries.Sequence>

      <TransitionSeries.Transition
        presentation={fade()}
        timing={linearTiming({ durationInFrames: T })}
      />

      <TransitionSeries.Sequence durationInFrames={ENGINE}>
        <Engine />
      </TransitionSeries.Sequence>

      <TransitionSeries.Transition
        presentation={fade()}
        timing={linearTiming({ durationInFrames: T })}
      />

      <TransitionSeries.Sequence durationInFrames={PROOF}>
        <Proof />
      </TransitionSeries.Sequence>

      <TransitionSeries.Transition
        presentation={fade()}
        timing={linearTiming({ durationInFrames: T })}
      />

      <TransitionSeries.Sequence durationInFrames={STANDARDS}>
        <Standards />
      </TransitionSeries.Sequence>

      <TransitionSeries.Transition
        presentation={fade()}
        timing={linearTiming({ durationInFrames: T })}
      />

      <TransitionSeries.Sequence durationInFrames={CLOSE}>
        <Close />
      </TransitionSeries.Sequence>
    </TransitionSeries>
  );
};
