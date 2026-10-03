import { type HTMLAttributes } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
	"inline-flex items-center gap-1 rounded-[var(--radius-sm)] px-[7px] py-0 h-5 text-[11px] font-medium tracking-[0.01em] transition-colors",
	{
		variants: {
			variant: {
				default: "bg-brand-tint text-brand-2",
				approved: "bg-ok-tint text-ok",
				interim: "bg-brand-tint text-brand",
				unapproved: "bg-warn-tint text-[color-mix(in_oklch,var(--color-warn)_60%,black)]",
				error: "bg-err-tint text-err",
				warning: "bg-warn-tint text-[color-mix(in_oklch,var(--color-warn)_60%,black)]",
				info: "bg-brand-tint text-brand-2",
				success: "bg-ok-tint text-ok",
				muted: "bg-paper-2 text-ink-2 border border-line",
				outline: "border border-current bg-transparent text-ink-2",
				ink: "bg-ink text-paper border border-ink",
			},
		},
		defaultVariants: {
			variant: "default",
		},
	}
);

interface BadgeProps
	extends HTMLAttributes<HTMLSpanElement>,
		VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
	return (
		<span className={cn(badgeVariants({ variant }), className)} {...props} />
	);
}

// eslint-disable-next-line react-refresh/only-export-components
export { Badge, badgeVariants };
export type { BadgeProps };
