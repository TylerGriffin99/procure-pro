import { TableCell } from "@/components/ui/table";
import { cn } from "@/lib/utils";

interface CurrencyCellProps {
	value: string | number | null | undefined;
	className?: string;
	showParens?: boolean;
}

// eslint-disable-next-line react-refresh/only-export-components
export function formatCurrency(v: string | number | null | undefined): string {
	if (v == null || v === "") return "-";
	const num = Number(v);
	if (isNaN(num)) return "-";
	return num.toLocaleString(undefined, { minimumFractionDigits: 2 });
}

export function CurrencyCell({ value, className, showParens = false }: CurrencyCellProps) {
	const num = Number(value || 0);
	const isNegative = num < 0;
	const formatted = Math.abs(num).toLocaleString(undefined, { minimumFractionDigits: 2 });

	const display = isNegative || (showParens && num !== 0)
		? `(${formatted})`
		: formatted;

	return (
		<TableCell className={cn("text-right", isNegative && "text-err font-medium", className)}>
			{value == null || value === "" ? "-" : display}
		</TableCell>
	);
}
