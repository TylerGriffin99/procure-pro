import { useState, useEffect } from "react";
import { formatCurrency } from "@/components/currency-cell";
import { RowBtn } from "@/components/RowBtn";
import type { ItemStatus } from "@/types/domain";

const STATUS_COLOR: Record<ItemStatus, string> = {
	approved: "var(--color-ok)",
	interim: "var(--color-brand)",
	unapproved: "var(--color-warn)",
};

const STATUS_LABEL: Record<ItemStatus, string> = {
	approved: "approved",
	interim: "interim",
	unapproved: "pending",
};

const STATUS_TINT: Record<ItemStatus, string> = {
	approved: "var(--color-ok-tint)",
	interim: "var(--color-brand-tint)",
	unapproved: "var(--color-warn-tint)",
};

interface ClaimItemRowProps {
	item: {
		id: string;
		description: string;
		contractor_claim_to_date: string;
		total_recommended: string;
		percentage: string;
		variance_to_claim: string;
		previously_paid: string;
		recommended_this_period: string;
		status: ItemStatus;
		comments: string | null;
		adjustment_type?: string | null;
	};
	denominator: number;
	onUpdate: (id: string, data: Record<string, unknown>) => void;
	onReclassify: (itemId: string) => void;
	isPending: boolean;
	warnings?: string[];
	confidence?: number;
	autoEdit?: boolean;
	onStatusChange?: (status: "approved" | "interim") => void;
}

export function ClaimItemRow({
	item,
	denominator,
	onUpdate,
	onReclassify,
	isPending,
	warnings,
	confidence,
	autoEdit,
	onStatusChange,
}: ClaimItemRowProps) {
	const [editing, setEditing] = useState(false);
	const [thisPeriodAmount, setThisPeriodAmount] = useState(item.recommended_this_period);
	const [comment, setComment] = useState(item.comments || "");

	useEffect(() => {
		if (autoEdit && !editing && item.status === "unapproved") {
			startEditing();
		}
	// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [autoEdit]);

	const fmt = formatCurrency;
	const variance = Number(item.variance_to_claim);
	const statusColor = STATUS_COLOR[item.status];

	const rowBg = item.status !== "approved"
		? "color-mix(in oklab, var(--color-warn-tint) 14%, var(--color-paper-2))"
		: "var(--color-paper-2)";

	const handleApprove = (status: "approved" | "interim") => {
		const totalRecommended = Number(item.previously_paid) + Number(thisPeriodAmount);
		const data: Record<string, unknown> = {
			total_recommended: totalRecommended,
			status,
		};
		if (comment) data.comments = comment;
		onUpdate(item.id, data);
		setEditing(false);
		onStatusChange?.(status);
	};

	const startEditing = () => {
		const defaultThisPeriod = Number(item.contractor_claim_to_date) - Number(item.previously_paid);
		setThisPeriodAmount(String(defaultThisPeriod));
		setComment(item.comments || "");
		setEditing(true);
	};

	return (
		<tr
			style={{
				borderTop: "1px solid var(--color-line)",
				background: rowBg,
			}}
		>
			{/* Description + status pill — with indent guide and tree character */}
			<td
				className="py-2 pr-3"
				style={{
					paddingLeft: 30,
					borderLeft: `3px solid color-mix(in oklab, ${statusColor} 35%, transparent)`,
					position: "relative",
				}}
			>
				{/* Vertical indent guide */}
				<div
					style={{
						position: "absolute",
						left: 18,
						top: 0,
						bottom: 0,
						width: 1,
						background: "var(--color-line-2)",
					}}
				/>
				<div className="flex items-center gap-1.5 min-w-0">
					<span
						className="font-mono-nums shrink-0"
						style={{
							color: "var(--color-line-strong)",
							fontSize: 11,
							lineHeight: 1,
						}}
					>
						&#x2514;
					</span>
					<span
						style={{
							fontSize: 11,
							color: "var(--color-ink-2)",
							lineHeight: 1.3,
							overflow: "hidden",
							textOverflow: "ellipsis",
							whiteSpace: "nowrap",
						}}
					>
						{item.adjustment_type === "interim_adjustment" && (
							<span
								style={{
									fontSize: 9,
									fontWeight: 600,
									letterSpacing: "0.04em",
									textTransform: "uppercase",
									color: "var(--color-brand)",
									marginRight: 4,
								}}
							>
								ADJ
							</span>
						)}
						{item.description}
					</span>
					<span
						className="shrink-0"
						style={{
							display: "inline-flex",
							padding: "1px 6px",
							borderRadius: 3,
							fontSize: 9,
							fontWeight: 500,
							letterSpacing: "0.04em",
							background: STATUS_TINT[item.status],
							color: statusColor,
						}}
					>
						{STATUS_LABEL[item.status]}
					</span>
					{warnings && warnings.length > 0 && (
						<span
							className="shrink-0"
							title={warnings.join("; ")}
							style={{
								display: "inline-flex",
								padding: "1px 6px",
								borderRadius: 3,
								fontSize: 9,
								fontWeight: 500,
								background: "var(--color-warn-tint)",
								color: "var(--color-warn)",
							}}
						>
							{warnings.length} warning{warnings.length > 1 ? "s" : ""}
						</span>
					)}
					{confidence !== undefined && confidence < 0.7 && (
						<span
							className="shrink-0"
							title={`AI confidence: ${Math.round(confidence * 100)}%`}
							style={{
								display: "inline-flex",
								padding: "1px 6px",
								borderRadius: 3,
								fontSize: 9,
								fontWeight: 500,
								background: "var(--color-warn-tint)",
								color: "var(--color-warn)",
							}}
						>
							{Math.round(confidence * 100)}%
						</span>
					)}
				</div>
			</td>
			<td className="px-3 py-2 text-right font-mono-nums" style={{ fontSize: 11, color: "var(--color-ink-5)" }}>
				&mdash;
			</td>
			<td className="px-3 py-2 text-right font-mono-nums" style={{ fontSize: 11 }}>
				${fmt(item.contractor_claim_to_date)}
			</td>
			<td className="px-3 py-2 text-right font-mono-nums font-medium" style={{ fontSize: 11 }}>
				${editing
					? fmt(String(Number(item.previously_paid) + Number(thisPeriodAmount)))
					: fmt(item.total_recommended)}
			</td>
			<td className="px-3 py-2 text-right font-mono-nums" style={{ fontSize: 11, color: "var(--color-ink-4)" }}>
				{editing
					? (() => {
							const totalRec = Number(item.previously_paid) + Number(thisPeriodAmount);
							return denominator > 0
								? ((totalRec / denominator) * 100).toFixed(1) + "%"
								: "0.0%";
						})()
					: Number(item.percentage).toFixed(1) + "%"}
			</td>
			{(() => {
				const liveVariance = editing
					? Number(item.previously_paid) + Number(thisPeriodAmount) - Number(item.contractor_claim_to_date)
					: variance;
				return (
					<td
						className="px-3 py-2 text-right font-mono-nums"
						style={{
							fontSize: 11,
							color: liveVariance < 0 ? "var(--color-err)" : "var(--color-ink-5)",
						}}
					>
						{liveVariance !== 0
							? `($${fmt(String(Math.abs(liveVariance)))})`
							: "\u2014"}
					</td>
				);
			})()}
			<td className="px-3 py-2 text-right font-mono-nums" style={{ fontSize: 11, color: "var(--color-ink-3)" }}>
				${fmt(item.previously_paid)}
			</td>
			<td className="px-3 py-2 text-right font-mono-nums" style={{ fontSize: 11 }}>
				{editing ? (
					<input
						type="number"
						step="0.01"
						value={thisPeriodAmount}
						autoFocus
						onChange={(e) => setThisPeriodAmount(e.target.value)}
						style={{
							width: 74,
							padding: "2px 4px",
							textAlign: "right",
							fontFamily: "var(--font-mono)",
							fontSize: 11,
							border: "1px solid var(--color-brand)",
							borderRadius: 3,
							outline: 0,
							background: "var(--color-surface)",
						}}
					/>
				) : (
					`$${fmt(item.recommended_this_period)}`
				)}
			</td>
			<td className="px-3 py-2" style={{ overflow: "hidden" }}>
				{editing ? (
					<input
						type="text"
						value={comment}
						onChange={(e) => setComment(e.target.value)}
						placeholder="Note..."
						style={{
							width: "100%",
							padding: "2px 4px",
							fontSize: 10,
							border: "1px solid var(--color-line-2)",
							borderRadius: 3,
							outline: 0,
							background: "var(--color-surface)",
						}}
					/>
				) : (
					<span
						style={{
							fontSize: 10,
							display: "block",
							overflow: "hidden",
							textOverflow: "ellipsis",
							whiteSpace: "nowrap",
							color: item.comments ? "var(--color-ink-2)" : "var(--color-ink-5)",
							fontStyle: item.comments ? "normal" : "italic",
						}}
					>
						{item.comments || "\u2014"}
					</span>
				)}
			</td>
			<td className="px-3 py-2">
				<div className="flex flex-col gap-0.5 items-center">
					{editing ? (
						<>
							<div className="flex gap-0.5">
								<RowBtn tone="ok" onClick={() => handleApprove("approved")} disabled={isPending}>
									&#x2713;
								</RowBtn>
								<RowBtn tone="brand" onClick={() => handleApprove("interim")} disabled={isPending}>
									Int
								</RowBtn>
							</div>
							<RowBtn tone="ghost" onClick={() => setEditing(false)}>
								&#x2715;
							</RowBtn>
						</>
					) : (
						<>
							<RowBtn tone="ghost" onClick={startEditing}>
								Review
							</RowBtn>
							<RowBtn tone="err" onClick={() => onReclassify(item.id)}>
								Reclassify
							</RowBtn>
						</>
					)}
				</div>
			</td>
		</tr>
	);
}
