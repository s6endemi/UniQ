import { cva, type VariantProps } from "class-variance-authority";
import type { ComponentPropsWithoutRef } from "react";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider",
  {
    variants: {
      tone: {
        neutral: "bg-ink-800 text-text-2 border border-ink-700",
        glacial: "bg-glacial/15 text-glacial border border-glacial/30",
        mineral: "bg-mineral/15 text-mineral border border-mineral/30",
        amber: "bg-amber/15 text-amber border border-amber/30",
        coral: "bg-coral/15 text-coral border border-coral/30",
      },
    },
    defaultVariants: { tone: "neutral" },
  },
);

interface BadgeProps
  extends ComponentPropsWithoutRef<"span">,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, tone, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ tone }), className)} {...props} />;
}
