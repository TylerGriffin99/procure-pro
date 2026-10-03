import { cn } from "@/lib/utils";

interface ToggleGroupOption<T extends string> {
	value: T;
	label: string;
}

interface ToggleGroupProps<T extends string> {
	options: ToggleGroupOption<T>[];
	value: T;
	onChange: (value: T) => void;
	className?: string;
}

function ToggleGroup<T extends string>({
	options,
	value,
	onChange,
	className,
}: ToggleGroupProps<T>) {
	return (
		<div className={cn("flex items-center gap-1 bg-muted rounded-lg p-1", className)}>
			{options.map((opt) => (
				<button
					key={opt.value}
					type="button"
					onClick={() => onChange(opt.value)}
					className={cn(
						"px-3 py-1.5 rounded-md text-xs font-medium transition-colors",
						value === opt.value
							? "bg-background text-foreground shadow-sm"
							: "text-muted-foreground hover:text-foreground"
					)}
				>
					{opt.label}
				</button>
			))}
		</div>
	);
}

export { ToggleGroup };
export type { ToggleGroupOption };
