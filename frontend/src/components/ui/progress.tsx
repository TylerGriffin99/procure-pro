import { cn } from "@/lib/utils";

interface ProgressProps {
	value: number;
	className?: string;
	indicatorClassName?: string;
}

function Progress({ value, className, indicatorClassName }: ProgressProps) {
	return (
		<div className={cn("w-full bg-gray-100 rounded-full h-1.5", className)}>
			<div
				className={cn(
					"h-full rounded-full transition-all duration-500",
					indicatorClassName ?? "bg-primary"
				)}
				style={{ width: `${Math.min(100, Math.max(0, value))}%` }}
			/>
		</div>
	);
}

export { Progress };
