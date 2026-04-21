"use client";

import { motion } from "motion/react";
import { cn } from "@/lib/utils";

interface AiOrbProps {
  size?: number;
  className?: string;
  /** Hue offset for visual variety. 0 = glacial cyan, 120 = mineral green. */
  hue?: "glacial" | "mineral";
}

/**
 * The signature visual element. A breathing orb with layered gradients
 * and a subtle ring pulse. Used in the hero, and a smaller version sits
 * next to "AI is thinking" in the analyst.
 *
 * Respects prefers-reduced-motion via the global CSS rule that nukes
 * all animations.
 */
export function AiOrb({ size = 280, className, hue = "glacial" }: AiOrbProps) {
  const accent = hue === "glacial" ? "#3DB8C9" : "#4ABD8A";
  return (
    <div
      className={cn("relative grid place-items-center", className)}
      style={{ width: size, height: size }}
    >
      {/* Outer halo — slow expand */}
      <motion.div
        className="absolute inset-0 rounded-full"
        style={{
          background: `radial-gradient(circle at 50% 50%, ${accent}33 0%, transparent 60%)`,
        }}
        animate={{ scale: [1, 1.1, 1], opacity: [0.6, 1, 0.6] }}
        transition={{ duration: 6, repeat: Infinity, ease: "easeInOut" }}
      />

      {/* Inner core */}
      <motion.div
        className="absolute rounded-full"
        style={{
          width: size * 0.6,
          height: size * 0.6,
          background: `radial-gradient(circle at 35% 30%, ${accent}, #07090d 80%)`,
          boxShadow: `0 0 100px -20px ${accent}AA, inset 0 0 60px ${accent}33`,
        }}
        animate={{ scale: [0.95, 1.02, 0.95] }}
        transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
      />

      {/* Ring pulse */}
      <motion.div
        className="absolute rounded-full border"
        style={{
          width: size * 0.85,
          height: size * 0.85,
          borderColor: `${accent}55`,
        }}
        animate={{ scale: [1, 1.08, 1], opacity: [0.5, 0.2, 0.5] }}
        transition={{ duration: 5, repeat: Infinity, ease: "easeInOut", delay: 0.5 }}
      />

      {/* Innermost highlight */}
      <div
        className="absolute rounded-full"
        style={{
          width: size * 0.15,
          height: size * 0.15,
          left: size * 0.28,
          top: size * 0.22,
          background: "radial-gradient(circle, #ffffff66, transparent 70%)",
          filter: "blur(4px)",
        }}
      />
    </div>
  );
}
