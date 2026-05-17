import { type VariantProps, cva } from "class-variance-authority";
import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium",
  {
    variants: {
      variant: {
        default: "bg-slate-700 text-slate-100",
        ok: "border border-emerald-500/30 bg-emerald-500/15 text-emerald-400",
        warning: "border border-amber-500/30 bg-amber-500/15 text-amber-400",
        critical: "border border-red-500/30 bg-red-500/15 text-red-400",
        unknown: "border border-slate-600/40 bg-slate-600/15 text-slate-400",
      },
    },
    defaultVariants: { variant: "default" },
  },
);

export type BadgeProps = HTMLAttributes<HTMLSpanElement> &
  VariantProps<typeof badgeVariants>;

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}
