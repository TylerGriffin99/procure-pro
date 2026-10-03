import { RowBtn } from "@/components/RowBtn";
import { DropdownMenu, DropdownMenuItem } from "@/components/ui/dropdown-menu";
import { MoreHorizontal } from "lucide-react";
import type { ItemStatus } from "@/types/domain";

interface RowActionMenuProps {
	aggregateStatus: ItemStatus;
	activeChildCount: number;
	isPending: boolean;
	editing: boolean;
	onQuickApprove: () => void;
	onStartEditing: () => void;
	onApprove: () => void;
	onInterim: () => void;
	onCancelEditing: () => void;
	onReclassify?: () => void;
	hasPriorInterim: boolean;
	onInterimAdjust?: () => void;
	onCloseOut?: () => void;
	hasHistoryRow: boolean;
	allowQuickApprove?: boolean;
}

export function RowActionMenu({
	aggregateStatus,
	activeChildCount,
	isPending,
	editing,
	onQuickApprove,
	onStartEditing,
	onApprove,
	onInterim,
	onCancelEditing,
	onReclassify,
	hasPriorInterim,
	onInterimAdjust,
	onCloseOut,
	hasHistoryRow,
	allowQuickApprove = false,
}: RowActionMenuProps) {
	if (aggregateStatus === "approved" && !onCloseOut) return null;

	// Single child quick-approve: ✓ is primary, Review visible, overflow for reclassify
	if (allowQuickApprove && activeChildCount === 1 && !hasPriorInterim) {
		return (
			<div className="flex items-center justify-center gap-0.5">
				<RowBtn tone="ok" onClick={onQuickApprove} disabled={isPending}>
					&#x2713;
				</RowBtn>
				{hasHistoryRow && (
					<RowBtn tone="ghost" onClick={onStartEditing}>
						Review
					</RowBtn>
				)}
				{onReclassify && (
					<DropdownMenu
						align="right"
						trigger={
							<RowBtn tone="ghost" onClick={() => {}}>
								<MoreHorizontal className="w-3.5 h-3.5" />
							</RowBtn>
						}
					>
						<DropdownMenuItem onClick={onReclassify}>
							<span style={{ color: "var(--color-err)", fontWeight: 500 }}>Reclassify</span>
						</DropdownMenuItem>
					</DropdownMenu>
				)}
			</div>
		);
	}

	// Editing mode: Approve is primary, Interim + Cancel in overflow
	if (editing) {
		return (
			<div className="flex items-center justify-center gap-0.5">
				<RowBtn tone="ok" onClick={onApprove} disabled={isPending}>
					Approve
				</RowBtn>
				<DropdownMenu
					align="right"
					trigger={
						<RowBtn tone="ghost" onClick={() => {}}>
							<MoreHorizontal className="w-3.5 h-3.5" />
						</RowBtn>
					}
				>
					<DropdownMenuItem onClick={onInterim}>
						<span style={{ color: "var(--color-brand)", fontWeight: 500 }}>Interim</span>
					</DropdownMenuItem>
					<DropdownMenuItem onClick={onCancelEditing}>
						Cancel
					</DropdownMenuItem>
				</DropdownMenu>
			</div>
		);
	}

	// Normal state: Review is primary visible button, secondary actions in overflow
	const hasInterimActions = hasPriorInterim && onInterimAdjust && onCloseOut;
	const hasReviewAction = hasHistoryRow;
	const hasOverflowItems = onReclassify || hasInterimActions || onCloseOut;

	if (!hasReviewAction && !hasOverflowItems) return null;

	return (
		<div className="flex items-center justify-center gap-0.5">
			{hasReviewAction && (
				<RowBtn tone="ghost" onClick={onStartEditing}>
					Review
				</RowBtn>
			)}
			{hasOverflowItems && (
				<DropdownMenu
					align="right"
					trigger={
						<RowBtn tone="ghost" onClick={() => {}}>
							<MoreHorizontal className="w-3.5 h-3.5" />
						</RowBtn>
					}
				>
					{onReclassify && (
						<DropdownMenuItem onClick={onReclassify}>
							<span style={{ color: "var(--color-err)", fontWeight: 500 }}>Reclassify</span>
						</DropdownMenuItem>
					)}
					{hasInterimActions && (
						<>
							<DropdownMenuItem onClick={onInterimAdjust!}>
								<span style={{ color: "var(--color-brand)", fontWeight: 500 }}>Adjust</span>
							</DropdownMenuItem>
							<DropdownMenuItem onClick={onCloseOut!}>
								<span style={{ color: "var(--color-ok)", fontWeight: 500 }}>Close out</span>
							</DropdownMenuItem>
						</>
					)}
					{onCloseOut && !hasInterimActions && (
						<DropdownMenuItem onClick={onCloseOut}>
							<span style={{ color: "var(--color-ok)", fontWeight: 500 }}>Close out</span>
						</DropdownMenuItem>
					)}
				</DropdownMenu>
			)}
		</div>
	);
}
