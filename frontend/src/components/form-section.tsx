import { type ReactNode } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface FormSectionProps {
	title: string;
	description?: string;
	children: ReactNode;
	columns?: 1 | 2 | 3;
	className?: string;
}

export function FormSection({
	title,
	description,
	children,
	columns = 2,
	className,
}: FormSectionProps) {
	const gridClass = {
		1: "grid-cols-1",
		2: "grid-cols-2",
		3: "grid-cols-3",
	}[columns];

	return (
		<Card className={className}>
			<CardHeader className="pb-4">
				<CardTitle className="text-lg">{title}</CardTitle>
				{description && (
					<p className="text-sm text-muted-foreground">{description}</p>
				)}
			</CardHeader>
			<CardContent>
				<div className={cn("grid gap-4", gridClass)}>{children}</div>
			</CardContent>
		</Card>
	);
}
