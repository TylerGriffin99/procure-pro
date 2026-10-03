import { useId, type ReactElement, cloneElement } from "react";
import { type FieldError } from "react-hook-form";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

interface FormFieldProps {
	label: string;
	required?: boolean;
	error?: FieldError;
	children: ReactElement<{ id?: string }>;
	className?: string;
	hint?: string;
}

export function FormField({ label, required, error, children, className, hint }: FormFieldProps) {
	const id = useId();

	return (
		<div className={cn("space-y-1", className)}>
			<Label htmlFor={id} className="text-[11px] text-ink-3 font-medium tracking-[0.04em] uppercase">
				{label}
				{required && <span className="text-destructive ml-0.5">*</span>}
			</Label>
			{cloneElement(children, { id })}
			{hint && !error && (
				<p className="text-xs text-muted-foreground">{hint}</p>
			)}
			{error && (
				<p className="text-xs text-destructive" role="alert">{error.message}</p>
			)}
		</div>
	);
}
