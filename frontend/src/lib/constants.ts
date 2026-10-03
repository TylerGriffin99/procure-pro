import type { ItemStatus } from "@/types/domain";

/** Status-based row background colors for assessment review tables */
export const STATUS_ROW_COLORS: Record<ItemStatus, string> = {
	unapproved: "bg-yellow-50 border-l-4 border-yellow-400",
	approved: "bg-green-50 border-l-4 border-green-400",
	interim: "bg-blue-50 border-l-4 border-blue-400",
};
