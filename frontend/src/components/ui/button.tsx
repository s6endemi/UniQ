import { cva, type VariantProps } from "class-variance-authority";
import { type ComponentPropsWithoutRef, forwardRef } from "react";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md font-medium " +
    "transition-all duration-200 focus-visible:outline-2 focus-visible:outline-offset-2 " +
    "focus-visible:outline-glacial disabled:pointer-events-none disabled:opacity-40",
  {
    variants: {
      variant: {
        primary:
          "bg-glacial text-ink-950 hover:bg-glacial-soft shadow-[0_0_30px_-12px_rgba(61,184,201,0.7)]",
        secondary:
          "bg-ink-800 text-text-1 border border-ink-600 hover:bg-ink-700 hover:text-text-0",
        ghost: "text-text-2 hover:bg-ink-800/60 hover:text-text-1",
        outline:
          "border border-glacial/40 text-glacial hover:border-glacial hover:bg-glacial/10",
        approve:
          "bg-mineral/20 text-mineral border border-mineral/40 hover:bg-mineral/30",
        reject:
          "bg-coral/20 text-coral border border-coral/40 hover:bg-coral/30",
      },
      size: {
        sm: "h-8 px-3 text-xs",
        md: "h-10 px-4 text-sm",
        lg: "h-12 px-6 text-base",
      },
    },
    defaultVariants: {
      variant: "primary",
      size: "md",
    },
  },
);

interface ButtonProps
  extends ComponentPropsWithoutRef<"button">,
    VariantProps<typeof buttonVariants> {}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { className, variant, size, ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      className={cn(buttonVariants({ variant, size }), className)}
      {...props}
    />
  );
});
