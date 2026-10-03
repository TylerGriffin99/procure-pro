import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
	"inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-[var(--radius-md)] text-[13px] font-medium tracking-[0.005em] transition-all duration-100 cursor-pointer disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0",
	{
		variants: {
			variant: {
				primary: "bg-brand text-brand-fg border border-brand hover:bg-brand-2",
				secondary: "bg-surface text-ink border border-line-2 hover:bg-paper-2",
				destructive: "bg-transparent text-err border border-line-2 hover:bg-err-tint",
				outline: "border border-line-2 bg-surface hover:bg-paper-2 text-ink",
				ghost: "hover:bg-paper-2 text-ink-2",
				link: "text-brand underline-offset-4 hover:underline",
				success: "bg-ok text-white border border-ok hover:opacity-90",
				info: "bg-brand-400 text-white border border-brand-400 hover:bg-brand",
				warning: "bg-warn text-white hover:opacity-90",
				quiet: "bg-paper-2 text-ink border border-transparent hover:bg-paper-3",
			},
			size: {
				xs: "h-[26px] px-2.5 text-xs",
				sm: "h-[30px] px-3 text-xs",
				md: "h-[32px] px-3 text-[13px]",
				lg: "h-[38px] px-4 text-sm",
				icon: "h-8 w-8",
				"icon-sm": "h-7 w-7",
			},
		},
		defaultVariants: {
			variant: "primary",
			size: "md",
		},
	}
);

interface ButtonProps
	extends ButtonHTMLAttributes<HTMLButtonElement>,
		VariantProps<typeof buttonVariants> {}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
	({ className, variant, size, ...props }, ref) => {
		return (
			<button
				className={cn(buttonVariants({ variant, size, className }))}
				ref={ref}
				{...props}
			/>
		);
	}
);
Button.displayName = "Button";

// eslint-disable-next-line react-refresh/only-export-components
export { Button, buttonVariants };
export type { ButtonProps };
