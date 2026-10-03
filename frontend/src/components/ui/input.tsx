import { forwardRef, type InputHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
	({ className, type, ...props }, ref) => {
		return (
			<input
				type={type}
				className={cn(
					"h-8 w-full rounded-[var(--radius-md)] border border-line-2 bg-surface px-2 text-[13px] text-ink transition-[border-color,box-shadow] duration-100 placeholder:text-ink-4 focus:border-brand focus:ring-2 focus:ring-brand-tint focus:outline-none disabled:opacity-50",
					className
				)}
				ref={ref}
				{...props}
			/>
		);
	}
);
Input.displayName = "Input";

export { Input };
