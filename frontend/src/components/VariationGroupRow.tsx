import { useState } from "react";
import { cn } from "@/lib/utils";
import { ChevronRight, ChevronDown } from "lucide-react";
import { formatCurrency } from "@/components/currency-cell";
import { ClaimItemRow } from "@/components/ClaimItemRow";
import { RowActionMenu } from "@/components/RowActionMenu";
import type { AggregatedVariationGroup } from "@/hooks/useAssessments";
import type { PriorInterimItem } from "@/hooks/useAssessments";
import type { ItemStatus } from "@/types/domain";

const STATUS_COLOR: Record<ItemStatus, string> = {
	approved: "var(--color-ok)",
	interim: "var(--color-brand)",
	unapproved: "var(--color-warn)",
};

interface VariationGroupRowProps {
	group: AggregatedVariationGroup;
	onUpdate: (id: string, data: Record<string, unknown>) => void;
	onReclassify: (itemId: string) => void;
	isPending: boolean;
	claimLineWarnings?: Map<string, string[]>;
	claimLineConfidence?: Map<string, number>;
	priorInterim?: PriorInterimItem;
	onInterimAdjust?: (parentId: string, description: string, previouslyPaid: string, existingComment: string | null) => void;
	onCloseOut?: (parentId: string) => void;
}

export function VariationGroupRow({
	group,
	onUpdate,
	onReclassify,
	isPending,
	claimLineWarnings,
	claimLineConfidence,
	priorInterim,
	onInterimAdjust,
	onCloseOut,
}: VariationGroupRowProps) {
	const [expanded, setExpanded] = useState(false);
	const [editing, setEditing] = useState(false);
	const [autoEditChildId, setAutoEditChildId] = useState<string | null>(null);
	const [thisPeriodAmount, setThisPeriodAmount] = useState(
		group.history_row?.recommended_this_period || "0"
	);
	const [comment, setComment] = useState(group.history_row?.comments || "");
	const [hovered, setHovered] = useState(false);

	const fmt = formatCurrency;
	const hasChildren = group.child_rows.length > 0;
	const activeChildren = group.child_rows.filter((c) => Number(c.contractor_claim_to_date) > 0 || c.adjustment_type);

	const contractorSubmission = Number(group.contractor_submission);
	const previouslyPaid = Number(group.previously_paid);
	const childThisPeriod = Number(group.recommended_this_period);
	const totalRecommended = Number(group.total_recommended);
	const childClaimToDate = Number(group.contractor_claim_to_date);
	const variance = Number(group.variance_to_claim);
	const percentage = Number(group.percentage);

	const aggregateStatus: ItemStatus = hasChildren
		? group.child_rows.every((c) => c.status === "approved")
			? "approved"
			: group.child_rows.every((c) => c.status !== "unapproved")
				? "interim"
				: "unapproved"
		: group.history_row?.status || "unapproved";

	const statusColor = STATUS_COLOR[aggregateStatus];
	const rowBg = aggregateStatus === "unapproved"
		? "color-mix(in oklab, var(--color-warn-tint) 28%, transparent)"
		: "transparent";
	const hoverBg = aggregateStatus === "unapproved"
		? "color-mix(in oklab, var(--color-warn-tint) 28%, transparent)"
		: "var(--color-paper-2)";

	const handleApprove = (status: "approved" | "interim") => {
		if (!group.history_row) return;
		const total = Number(group.history_row.previously_paid) + Number(thisPeriodAmount);
		const data: Record<string, unknown> = {
			total_recommended: total,
			status,
		};
		if (comment) data.comments = comment;
		onUpdate(group.history_row.id, data);
		setEditing(false);
	};

	const startEditing = () => {
		if (!group.history_row) return;
		const defaultThisPeriod =
			Number(group.history_row.contractor_claim_to_date) - Number(group.history_row.previously_paid);
		setThisPeriodAmount(String(defaultThisPeriod));
		setComment(group.history_row.comments || "");
		setEditing(true);
	};

	return (
		<>
			<tr
				className={cn("text-sm", hasChildren && "cursor-pointer")}
				style={{
					borderTop: "1px solid var(--color-line)",
					background: hovered ? hoverBg : rowBg,
					transition: "background 120ms ease",
				}}
				onClick={hasChildren ? () => setExpanded(!expanded) : undefined}
				onMouseEnter={() => setHovered(true)}
				onMouseLeave={() => setHovered(false)}
			>
				<td className="py-2.5 pr-3" style={{ paddingLeft: 18, borderLeft: `3px solid ${statusColor}` }}>
					<div className="flex items-center gap-1.5 min-w-0">
						{hasChildren ? (
							expanded ? (
								<ChevronDown className="w-3.5 h-3.5 shrink-0 text-ink-4" />
							) : (
								<ChevronRight className="w-3.5 h-3.5 shrink-0 text-ink-4" />
							)
						) : (
							<span className="w-3 shrink-0" />
						)}
						<div className="min-w-0 flex-1">
							<div className="font-mono-nums text-[11px] text-brand tracking-[0.04em]">
								CI-{String(group.contractor_ref).padStart(2, "0")}
							</div>
							<div className="text-[13px] truncate">
								{group.description}
								{priorInterim && aggregateStatus !== "approved" && (
									<span
										style={{
											marginLeft: 6,
											fontSize: 9,
											fontWeight: 600,
											letterSpacing: "0.04em",
											textTransform: "uppercase",
											color: "var(--color-brand)",
											background: "color-mix(in oklab, var(--color-brand) 12%, transparent)",
											padding: "1px 5px",
											borderRadius: 3,
										}}
									>
										Interim open
									</span>
								)}
							</div>
						</div>
						{hasChildren && (
							<span
								className="font-mono-nums shrink-0"
								style={{
									display: "inline-flex",
									alignItems: "center",
									justifyContent: "center",
									minWidth: 18,
									height: 16,
									padding: "0 5px",
									background: "var(--color-paper-3)",
									border: "1px solid var(--color-line-2)",
									borderRadius: 99,
									fontSize: 10,
									color: "var(--color-ink-3)",
								}}
							>
								{group.child_rows.length}
							</span>
						)}
						<span
							className="shrink-0"
							style={{
								width: 7,
								height: 7,
								borderRadius: 99,
								background: statusColor,
							}}
						/>
					</div>
				</td>
				<td className="px-3 py-2.5 text-right font-mono-nums text-xs text-ink-3">${fmt(group.contractor_submission)}</td>
				<td className="px-3 py-2.5 text-right font-mono-nums text-xs">${fmt(String(childClaimToDate))}</td>
				<td className="px-3 py-2.5 text-right font-mono-nums text-xs font-medium">
					${editing && activeChildren.length === 0
						? fmt(String(previouslyPaid + Number(thisPeriodAmount)))
						: fmt(String(totalRecommended))}
				</td>
				<td className="px-3 py-2.5 text-right font-mono-nums text-xs text-ink-4">
					{editing && activeChildren.length === 0
						? (() => {
								const totalRec = previouslyPaid + Number(thisPeriodAmount);
								return contractorSubmission > 0
									? ((totalRec / contractorSubmission) * 100).toFixed(1) + "%"
									: "0.0%";
							})()
						: percentage.toFixed(1) + "%"}
				</td>
				{(() => {
					const liveVariance =
						editing && activeChildren.length === 0 && group.history_row
							? previouslyPaid +
								Number(thisPeriodAmount) -
								Number(group.history_row.contractor_claim_to_date)
							: variance;
					return (
						<td
							className="px-3 py-2.5 text-right font-mono-nums text-xs"
							style={{ color: liveVariance < 0 ? "var(--color-err)" : "var(--color-ink-5)" }}
						>
							{liveVariance !== 0
								? `($${fmt(String(Math.abs(liveVariance)))})`
								: "\u2014"}
						</td>
					);
				})()}
				<td className="px-3 py-2.5 text-right font-mono-nums text-xs text-ink-3">${fmt(String(previouslyPaid))}</td>
				<td className="px-3 py-2.5 text-right font-mono-nums text-xs" onClick={(e) => e.stopPropagation()}>
					{editing && activeChildren.length === 0 ? (
						<input
							type="number"
							step="0.01"
							value={thisPeriodAmount}
							autoFocus
							onChange={(e) => setThisPeriodAmount(e.target.value)}
							onClick={(e) => e.stopPropagation()}
							style={{
								width: 80,
								padding: "2px 5px",
								textAlign: "right",
								fontFamily: "var(--font-mono)",
								fontSize: 12,
								border: "1px solid var(--color-brand)",
								borderRadius: 3,
								outline: 0,
								background: "var(--color-surface)",
							}}
						/>
					) : (
						`$${fmt(String(childThisPeriod))}`
					)}
				</td>
				<td className="px-3 py-2.5" onClick={(e) => e.stopPropagation()}>
					{editing && activeChildren.length === 0 ? (
						<input
							type="text"
							value={comment}
							onChange={(e) => setComment(e.target.value)}
							onClick={(e) => e.stopPropagation()}
							placeholder="Add note..."
							style={{
								width: "100%",
								padding: "2px 5px",
								fontSize: 11,
								border: "1px solid var(--color-line-2)",
								borderRadius: 3,
								outline: 0,
								background: "var(--color-surface)",
							}}
						/>
					) : (
						<span
							style={{
								fontSize: 11,
								display: "block",
								overflow: "hidden",
								textOverflow: "ellipsis",
								whiteSpace: "nowrap",
								color: group.history_row?.comments ? "var(--color-ink-2)" : "var(--color-ink-5)",
								fontStyle: group.history_row?.comments ? "normal" : "italic",
							}}
						>
							{group.history_row?.comments || "\u2014"}
						</span>
					)}
				</td>
				<td className="px-3 py-2.5 text-center" onClick={(e) => e.stopPropagation()}>
					<RowActionMenu
						aggregateStatus={aggregateStatus}
						activeChildCount={activeChildren.length}
						isPending={isPending}
						editing={editing}
						onQuickApprove={() => {
							const child = activeChildren[0];
							const totalRecommended = Number(child.contractor_claim_to_date);
							onUpdate(child.id, {
								total_recommended: totalRecommended,
								status: "approved",
							});
						}}
						onStartEditing={() => {
							if (activeChildren.length === 1) {
								setExpanded(true);
								setAutoEditChildId(activeChildren[0].id);
							} else if (activeChildren.length > 1) {
								setExpanded(true);
								startEditing();
							} else {
								startEditing();
							}
						}}
						onApprove={() => handleApprove("approved")}
						onInterim={() => handleApprove("interim")}
						onCancelEditing={() => setEditing(false)}
						onReclassify={group.history_row ? () => onReclassify(group.history_row!.id) : undefined}
						hasPriorInterim={!!priorInterim && aggregateStatus !== "approved"}
						onInterimAdjust={priorInterim ? () => onInterimAdjust?.(
							group.variation_id,
							group.description,
							priorInterim.previously_paid,
							priorInterim.comments,
						) : undefined}
						onCloseOut={onCloseOut ? () => onCloseOut(group.variation_id) : undefined}
						hasHistoryRow={!!group.history_row}
					/>
				</td>
			</tr>
			{expanded &&
				group.child_rows.map((child) => (
					<ClaimItemRow
						key={child.id}
						item={child}
						denominator={contractorSubmission}
						onUpdate={onUpdate}
						onReclassify={onReclassify}
						isPending={isPending}
						warnings={claimLineWarnings?.get(child.id)}
						confidence={claimLineConfidence?.get(child.id)}
						autoEdit={autoEditChildId === child.id}
						onStatusChange={() => {
							setExpanded(false);
							setAutoEditChildId(null);
						}}
					/>
				))}
		</>
	);
}
