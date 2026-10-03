import { cn } from "@/lib/utils";

interface SpinnerProps {
	className?: string;
	size?: "sm" | "md" | "lg";
}

const SIZE_CLASSES = {
	sm: "h-3 w-3 border-2",
	md: "h-6 w-6 border-2",
	lg: "h-8 w-8 border-4",
};

function Spinner({ className, size = "md" }: SpinnerProps) {
	return (
		<div
			className={cn(
				"animate-spin rounded-full border-primary border-t-transparent",
				SIZE_CLASSES[size],
				className
			)}
		/>
	);
}

export { Spinner };
