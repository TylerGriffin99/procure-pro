import { Badge } from "@/components/ui/badge";

type ClaimStatus = "unapproved" | "approved" | "interim";

const STATUS_LABELS: Record<ClaimStatus, string> = {
	unapproved: "U",
	approved: "A",
	interim: "I",
};

interface StatusBadgeProps {
	status: ClaimStatus;
	compact?: boolean;
}

export function StatusBadge({ status, compact = true }: StatusBadgeProps) {
	return (
		<Badge variant={status} title={status}>
			{compact ? STATUS_LABELS[status] : status.charAt(0).toUpperCase() + status.slice(1)}
		</Badge>
	);
}
