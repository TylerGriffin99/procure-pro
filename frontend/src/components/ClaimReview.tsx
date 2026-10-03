import { useState } from "react";
import type {
	Assessment,
	AggregatedWBSGroup,
} from "@/hooks/useAssessments";
import {
	useUpdateLineItem,
	useUpdateVariationItem,
	useUpdateProvisionalSumItem,
	useReclassifyItem,
	useCreateInterimAdjustment,
	useCloseOutItem,
	usePriorInterims,
} from "@/hooks/useAssessments";
import type { PriorInterimItem } from "@/hooks/useAssessments";
import { InterimAdjustPopover } from "@/components/InterimAdjustPopover";
import { WBSGroupRow } from "@/components/WBSGroupRow";
import { VariationGroupRow } from "@/components/VariationGroupRow";
import { PSGroupRow } from "@/components/PSGroupRow";
import { ReclassifyPopover } from "@/components/ReclassifyPopover";
import type { ComboboxOption } from "@/components/ui/combobox";
import type { WBSCode, RetentionTier } from "@/types/domain";

/** Legacy shape used by callers that haven't migrated to ComboboxOption yet */
interface WBSOption {
	id: string;
	label: string;
}

interface Props {
	assessment: Assessment;
	projectId: string;
	wbsOptions?: WBSOption[];
	wbsCodes?: WBSCode[];
	claimLineWarnings?: Map<string, string[]>;
	claimLineConfidence?: Map<string, number>;
	retentionTiers?: RetentionTier[];
}

interface CategoryGroup {
	category: WBSCode;
	wbsGroups: AggregatedWBSGroup[];
}

export default function ClaimReview({
	assessment,
	projectId,
	wbsOptions = [],
	wbsCodes = [],
	claimLineWarnings,
	claimLineConfidence,
	retentionTiers = [],
}: Props) {
	const updateMutation = useUpdateLineItem(projectId, assessment.id);
	const updateVariationMutation = useUpdateVariationItem(projectId, assessment.id);
	const updatePSMutation = useUpdateProvisionalSumItem(projectId, assessment.id);
	const reclassifyMutation = useReclassifyItem(projectId, assessment.id);

	const interimAdjustMutation = useCreateInterimAdjustment(projectId, assessment.id);
	const closeOutMutation = useCloseOutItem(projectId, assessment.id);
	const { data: priorInterims } = usePriorInterims(projectId, assessment.id);

	const wbsInterimMap = new Map<string, PriorInterimItem>(
		(priorInterims?.wbs_interims || []).map((i) => [i.parent_id, i])
	);
	const variationInterimMap = new Map<string, PriorInterimItem>(
		(priorInterims?.variation_interims || []).map((i) => [i.parent_id, i])
	);
	const psInterimMap = new Map<string, PriorInterimItem>(
		(priorInterims?.ps_interims || []).map((i) => [i.parent_id, i])
	);

	const [reclassifyingItemId, setReclassifyingItemId] = useState<string | null>(null);
	const [reclassifySourceType, setReclassifySourceType] = useState<
		"line-item" | "variation" | "provisional-sum"
	>("line-item");

	const [interimAdjustTarget, setInterimAdjustTarget] = useState<{
		itemType: "line-item" | "variation" | "provisional-sum";
		parentId: string;
		description: string;
		previouslyPaid: string;
		existingComment: string | null;
	} | null>(null);

	const handleUpdate = (lineItemId: string, data: Record<string, unknown>) => {
		updateMutation.mutate({ lineItemId, data });
	};

	const handleVariationUpdate = (itemId: string, data: Record<string, unknown>) => {
		updateVariationMutation.mutate({ itemId, data });
	};

	const handlePSUpdate = (itemId: string, data: Record<string, unknown>) => {
		updatePSMutation.mutate({ itemId, data });
	};

	// Map legacy WBSOption shape to ComboboxOption
	const comboboxWbsOptions: ComboboxOption[] = wbsOptions.map((o) => ({
		value: o.id,
		label: o.label,
	}));

	// Use pre-grouped data from the API
	const wbsGroups = assessment.wbs_groups || [];
	const variationGroups = assessment.variation_groups || [];
	const psGroups = assessment.ps_groups || [];

	// --- Progress counting at group level ---
	const countGroupStatus = (
		groups: { child_rows: { status: string }[]; history_row: { status: string } | null }[]
	) => {
		let total = 0;
		let approved = 0;
		for (const group of groups) {
			total++;
			const allItems = group.child_rows.length > 0
				? group.child_rows
				: group.history_row
					? [group.history_row]
					: [];
			if (allItems.length > 0 && allItems.every((i) => i.status !== "unapproved")) {
				approved++;
			}
		}
		return { total, approved };
	};

	const wbsStats = countGroupStatus(wbsGroups);
	const varStats = countGroupStatus(variationGroups);
	const psStats = countGroupStatus(psGroups);

	const allGroupCount = wbsStats.total + varStats.total + psStats.total;
	const allApprovedCount = wbsStats.approved + varStats.approved + psStats.approved;
	const progressPct = allGroupCount > 0 ? (allApprovedCount / allGroupCount) * 100 : 0;

	// Build WBS lookup maps
	const subcategoryMap = new Map<string, WBSCode>();
	const categoryMap = new Map<string, WBSCode>();
	for (const wbs of wbsCodes) {
		if (wbs.level === "subcategory") subcategoryMap.set(wbs.id, wbs);
		if (wbs.level === "category") categoryMap.set(wbs.id, wbs);
	}

	// Group WBS groups by parent category
	const categoryGroups: CategoryGroup[] = [];
	const ungroupedWbs: AggregatedWBSGroup[] = [];
	const categoryOrder = new Map<string, number>();

	for (const group of wbsGroups) {
		const wbsId = group.wbs_code_id;
		if (!wbsId || wbsId === "ungrouped") {
			ungroupedWbs.push(group);
			continue;
		}

		const sub = subcategoryMap.get(wbsId);
		const cat = sub?.parent_id ? categoryMap.get(sub.parent_id) : null;

		if (cat) {
			if (!categoryOrder.has(cat.id)) {
				categoryOrder.set(cat.id, categoryGroups.length);
				categoryGroups.push({ category: cat, wbsGroups: [] });
			}
			categoryGroups[categoryOrder.get(cat.id)!].wbsGroups.push(group);
		} else {
			ungroupedWbs.push(group);
		}
	}

	// Sort categories by code
	const sortedCategories = wbsCodes
		.filter((w) => w.level === "category")
		.sort((a, b) => a.code.localeCompare(b.code, undefined, { numeric: true }));

	// Identify PS/VR parent categories to exclude from contract works
	const excludedCategoryIds = new Set(
		sortedCategories
			.filter((cat) => /^(PS|VR)$/i.test(cat.code))
			.map((cat) => cat.id)
	);

	const orderedCategoryGroups = sortedCategories
		.filter((cat) => categoryOrder.has(cat.id) && !excludedCategoryIds.has(cat.id))
		.map((cat) => categoryGroups[categoryOrder.get(cat.id)!]);

	// Contract-works-only WBS groups for subtotal (exclude PS/VR categories)
	const contractWorksWbsGroups = wbsGroups.filter((group) => {
		if (!group.wbs_code_id) return true;
		const sub = subcategoryMap.get(group.wbs_code_id);
		return !sub?.parent_id || !excludedCategoryIds.has(sub.parent_id);
	});

	// --- Reclassify handlers ---
	const handleReclassifyLineItem = (itemId: string) => {
		setReclassifyingItemId(itemId);
		setReclassifySourceType("line-item");
	};

	const handleReclassifyVariation = (itemId: string) => {
		setReclassifyingItemId(itemId);
		setReclassifySourceType("variation");
	};

	const handleReclassifyPS = (itemId: string) => {
		setReclassifyingItemId(itemId);
		setReclassifySourceType("provisional-sum");
	};

	const handleInterimAdjust = (
		itemType: "line-item" | "variation" | "provisional-sum",
		parentId: string,
		description: string,
		previouslyPaid: string,
		existingComment: string | null,
	) => {
		setInterimAdjustTarget({ itemType, parentId, description, previouslyPaid, existingComment });
	};

	const handleCloseOut = (
		itemType: "line-item" | "variation" | "provisional-sum",
		parentId: string,
	) => {
		if (confirm("Close out this item at its current value?")) {
			closeOutMutation.mutate({ item_type: itemType, parent_id: parentId });
		}
	};

	// Build popover options for variations and PS from grouped data
	const variationComboOptions: ComboboxOption[] = variationGroups.map((g) => ({
		value: g.variation_id,
		label: `CI-${String(g.contractor_ref).padStart(2, "0")} - ${g.description}`,
	}));

	const psComboOptions: ComboboxOption[] = psGroups.map((g) => ({
		value: g.provisional_sum_id,
		label: `PS-${String(g.ps_number).padStart(2, "0")} - ${g.description}`,
	}));

	const colCount = 10;

	const colgroup = (
		<colgroup>
			<col className="w-[28%]" />
			<col className="w-[9%]" />
			<col className="w-[9%]" />
			<col className="w-[9%]" />
			<col className="w-[5%]" />
			<col className="w-[8%]" />
			<col className="w-[8%]" />
			<col className="w-[9%]" />
			<col className="w-[9%]" />
			<col className="w-[6%]" />
		</colgroup>
	);

	const renderReclassifyPopover = () => {
		if (!reclassifyingItemId) return null;
		return (
			<ReclassifyPopover
				sourceItemId={reclassifyingItemId}
				sourceType={reclassifySourceType}
				wbsOptions={comboboxWbsOptions}
				variationOptions={variationComboOptions}
				psOptions={psComboOptions}
				onConfirm={(params) => {
					reclassifyMutation.mutate(params, {
						onSuccess: () => setReclassifyingItemId(null),
					});
				}}
				onCancel={() => setReclassifyingItemId(null)}
				isPending={reclassifyMutation.isPending}
			/>
		);
	};

	return (
		<div>
			{/* Progress strip */}
			<div className="flex items-center gap-5 mb-6">
				<div className="flex items-center gap-2.5 text-xs">
					<span className="text-ink-3">Review progress</span>
					<span className="font-mono-nums font-medium">
						{allApprovedCount}<span className="text-ink-4"> / {allGroupCount}</span>
					</span>
					<span className="text-ink-3">items</span>
				</div>
				<div className="flex-1 max-w-[360px] h-1 bg-paper-3 rounded-full overflow-hidden">
					<div className="h-full bg-brand rounded-full transition-[width] duration-400" style={{ width: `${progressPct}%` }} />
				</div>
				<span className="font-mono-nums text-xs text-ink-3">{progressPct.toFixed(0)}%</span>
			</div>

			{/* Reclassify popover (fixed position overlay) */}
			{reclassifyingItemId && (
				<div className="fixed inset-0 z-40" onClick={() => setReclassifyingItemId(null)}>
					<div
						className="absolute top-1/3 left-1/2 -translate-x-1/2 z-50"
						onClick={(e) => e.stopPropagation()}
					>
						{renderReclassifyPopover()}
					</div>
				</div>
			)}

			{interimAdjustTarget && (
				<div className="fixed inset-0 z-40" onClick={() => setInterimAdjustTarget(null)}>
					<div
						className="absolute top-1/3 left-1/2 -translate-x-1/2 z-50"
						onClick={(e) => e.stopPropagation()}
					>
						<InterimAdjustPopover
							description={interimAdjustTarget.description}
							previouslyPaid={interimAdjustTarget.previouslyPaid}
							existingComment={interimAdjustTarget.existingComment}
							onConfirm={(agreedTotal, comments) => {
								interimAdjustMutation.mutate(
									{
										item_type: interimAdjustTarget.itemType,
										parent_id: interimAdjustTarget.parentId,
										agreed_total: agreedTotal,
										comments,
									},
									{ onSuccess: () => setInterimAdjustTarget(null) },
								);
							}}
							onCancel={() => setInterimAdjustTarget(null)}
							isPending={interimAdjustMutation.isPending}
						/>
					</div>
				</div>
			)}

			{/* 01 Contract Works */}
			<section className="mb-9">
				<div className="flex items-baseline gap-3.5 mb-3">
					<span className="font-mono-nums text-sm text-ink-4 tracking-[0.1em]">01</span>
					<h2 className="text-base font-medium tracking-[-0.01em]">Contract works</h2>
					<div className="flex-1 h-px bg-line" />
					<span className="font-mono-nums text-[11px] text-ink-3">{wbsGroups.length} groups</span>
				</div>
			<div className="border border-line rounded-[var(--radius-lg)] bg-surface overflow-hidden">
			<div className="overflow-x-auto">
				<table className="w-full table-fixed">
					{colgroup}
					<thead>
						<AssessmentHeader firstCol="WBS Item" sumLabel="Contract Sum" />
					</thead>
					<tbody>
						{/* Ungrouped items first */}
						{ungroupedWbs.length > 0 && (
							<>
								<tr className="bg-paper-2 border-t border-line">
									<td colSpan={colCount} className="px-3 py-2 font-medium text-xs text-ink-3 italic">
										Uncategorised
									</td>
								</tr>
								{ungroupedWbs.map((group) => (
									<WBSGroupRow
										key={group.wbs_code_id || group.description}
										group={group}
										onUpdate={handleUpdate}
										onReclassify={handleReclassifyLineItem}
										isPending={updateMutation.isPending}
										claimLineWarnings={claimLineWarnings}
										claimLineConfidence={claimLineConfidence}
										priorInterim={wbsInterimMap.get(group.wbs_code_id)}
										onInterimAdjust={(parentId, desc, prevPaid, comment) =>
											handleInterimAdjust("line-item", parentId, desc, prevPaid, comment)
										}
										onCloseOut={(parentId) => handleCloseOut("line-item", parentId)}
									/>
								))}
							</>
						)}

						{/* Grouped items by parent category */}
						{orderedCategoryGroups.map((catGroup) => (
							<CategorySection
								key={catGroup.category.id}
								catGroup={catGroup}
								colCount={colCount}
								subcategoryMap={subcategoryMap}
								onUpdate={handleUpdate}
								onReclassify={handleReclassifyLineItem}
								isPending={updateMutation.isPending}
								claimLineWarnings={claimLineWarnings}
								claimLineConfidence={claimLineConfidence}
								wbsInterimMap={wbsInterimMap}
								onInterimAdjust={(parentId, desc, prevPaid, comment) =>
									handleInterimAdjust("line-item", parentId, desc, prevPaid, comment)
								}
								onCloseOut={(parentId) => handleCloseOut("line-item", parentId)}
							/>
						))}
					</tbody>
					<tfoot>
						<tr className="bg-paper-2 font-medium text-xs border-t border-line-2">
							<td className="px-3 py-2">Sub Total Contract Works</td>
							<td className="px-3 py-2 text-right">
								{fmtTotal(contractWorksWbsGroups.map((g) => g.contract_sum))}
							</td>
							<td className="px-3 py-2 text-right">
								{fmtTotal(contractWorksWbsGroups.map((g) => g.contractor_claim_to_date))}
							</td>
							<td className="px-3 py-2 text-right">
								{fmtTotal(contractWorksWbsGroups.map((g) => g.total_recommended))}
							</td>
							<td className="px-3 py-2"></td>
							<td className="px-3 py-2 text-right">
								{fmtTotal(contractWorksWbsGroups.map((g) => g.variance_to_claim))}
							</td>
							<td className="px-3 py-2 text-right">
								{fmtTotal(contractWorksWbsGroups.map((g) => g.previously_paid))}
							</td>
							<td className="px-3 py-2 text-right">
								{fmtTotal(contractWorksWbsGroups.map((g) => g.recommended_this_period))}
							</td>
							<td className="px-3 py-2" colSpan={2}></td>
						</tr>
					</tfoot>
				</table>
			</div>
			</div>
			</section>

			{/* 02 Provisional Sums */}
			{psGroups.length > 0 && (
			<section className="mb-9">
				<div className="flex items-baseline gap-3.5 mb-3">
					<span className="font-mono-nums text-sm text-ink-4 tracking-[0.1em]">02</span>
					<h2 className="text-base font-medium tracking-[-0.01em]">Provisional sums</h2>
					<div className="flex-1 h-px bg-line" />
					<span className="font-mono-nums text-[11px] text-ink-3">{psGroups.length} groups</span>
				</div>
			<div className="border border-line rounded-[var(--radius-lg)] bg-surface overflow-hidden">
			<div className="overflow-x-auto">
						<table className="w-full table-fixed">
							{colgroup}
							<thead>
								<AssessmentHeader firstCol="Provisional Sum" sumLabel="Contract Sum" />
							</thead>
							<tbody>
								{psGroups.map((group) => (
									<PSGroupRow
										key={group.provisional_sum_id}
										group={group}
										onUpdate={handlePSUpdate}
										onReclassify={handleReclassifyPS}
										isPending={updatePSMutation.isPending}
										claimLineWarnings={claimLineWarnings}
										claimLineConfidence={claimLineConfidence}
										priorInterim={psInterimMap.get(group.provisional_sum_id)}
										onInterimAdjust={(parentId, desc, prevPaid, comment) =>
											handleInterimAdjust("provisional-sum", parentId, desc, prevPaid, comment)
										}
										onCloseOut={(parentId) => handleCloseOut("provisional-sum", parentId)}
									/>
								))}
							</tbody>
							<tfoot>
								<tr className="bg-paper-2 font-medium text-xs border-t border-line-2">
									<td className="px-3 py-2">Sub Total Provisional Sums</td>
									<td className="px-3 py-2 text-right">{fmtTotal(psGroups.map((g) => g.contract_sum))}</td>
									<td className="px-3 py-2 text-right">{fmtTotal(psGroups.map((g) => g.contractor_claim_to_date))}</td>
									<td className="px-3 py-2 text-right">{fmtTotal(psGroups.map((g) => g.total_recommended))}</td>
									<td className="px-3 py-2"></td>
									<td className="px-3 py-2 text-right">{fmtTotal(psGroups.map((g) => g.variance_to_claim))}</td>
									<td className="px-3 py-2 text-right">{fmtTotal(psGroups.map((g) => g.previously_paid))}</td>
									<td className="px-3 py-2 text-right">{fmtTotal(psGroups.map((g) => g.recommended_this_period))}</td>
									<td className="px-3 py-2" colSpan={2}></td>
								</tr>
							</tfoot>
						</table>
					</div>
				</div>
				</section>
			)}

			{/* 03 Variations */}
			{variationGroups.length > 0 && (
			<section className="mb-9">
				<div className="flex items-baseline gap-3.5 mb-3">
					<span className="font-mono-nums text-sm text-ink-4 tracking-[0.1em]">03</span>
					<h2 className="text-base font-medium tracking-[-0.01em]">Variations</h2>
					<div className="flex-1 h-px bg-line" />
					<span className="font-mono-nums text-[11px] text-ink-3">{variationGroups.length} groups</span>
				</div>
			<div className="border border-line rounded-[var(--radius-lg)] bg-surface overflow-hidden">
			<div className="overflow-x-auto">
				<table className="w-full table-fixed">
					{colgroup}
					<thead>
						<AssessmentHeader firstCol="Variation" sumLabel="Submission" />
					</thead>
					<tbody>
						{variationGroups.map((group) => (
							<VariationGroupRow
								key={group.variation_id}
								group={group}
								onUpdate={handleVariationUpdate}
								onReclassify={handleReclassifyVariation}
								isPending={updateVariationMutation.isPending}
								claimLineWarnings={claimLineWarnings}
								claimLineConfidence={claimLineConfidence}
								priorInterim={variationInterimMap.get(group.variation_id)}
								onInterimAdjust={(parentId, desc, prevPaid, comment) =>
									handleInterimAdjust("variation", parentId, desc, prevPaid, comment)
								}
								onCloseOut={(parentId) => handleCloseOut("variation", parentId)}
							/>
						))}
					</tbody>
					<tfoot>
						<tr className="bg-paper-2 font-medium text-xs border-t border-line-2">
							<td className="px-3 py-2">Sub Total Variations</td>
							<td className="px-3 py-2 text-right">{fmtTotal(variationGroups.map((g) => g.contractor_submission))}</td>
							<td className="px-3 py-2 text-right">{fmtTotal(variationGroups.map((g) => g.contractor_claim_to_date))}</td>
							<td className="px-3 py-2 text-right">{fmtTotal(variationGroups.map((g) => g.total_recommended))}</td>
							<td className="px-3 py-2"></td>
							<td className="px-3 py-2 text-right">{fmtTotal(variationGroups.map((g) => g.variance_to_claim))}</td>
							<td className="px-3 py-2 text-right">{fmtTotal(variationGroups.map((g) => g.previously_paid))}</td>
							<td className="px-3 py-2 text-right">{fmtTotal(variationGroups.map((g) => g.recommended_this_period))}</td>
							<td className="px-3 py-2" colSpan={2}></td>
						</tr>
					</tfoot>
				</table>
			</div>
			</div>
			</section>
			)}

			{/* 04 Retentions & total */}
			<section>
				<div className="flex items-baseline gap-3.5 mb-3">
					<span className="font-mono-nums text-sm text-ink-4 tracking-[0.1em]">04</span>
					<h2 className="text-base font-medium tracking-[-0.01em]">Retentions & total</h2>
					<div className="flex-1 h-px bg-line" />
				</div>
			<div className="border border-line rounded-[var(--radius-lg)] bg-surface overflow-hidden">
			{(() => {
				const sumStr = (vals: string[]) => vals.reduce((s, v) => s + Number(v || 0), 0);

				const col1Total =
					sumStr(contractWorksWbsGroups.map((g) => g.contract_sum)) +
					sumStr(psGroups.map((g) => g.contract_sum)) +
					sumStr(variationGroups.map((g) => g.contractor_submission));

				const col2Total =
					sumStr(contractWorksWbsGroups.map((g) => g.contractor_claim_to_date)) +
					sumStr(psGroups.map((g) => g.contractor_claim_to_date)) +
					sumStr(variationGroups.map((g) => g.contractor_claim_to_date));

				const col3Total =
					sumStr(contractWorksWbsGroups.map((g) => g.total_recommended)) +
					sumStr(psGroups.map((g) => g.total_recommended)) +
					sumStr(variationGroups.map((g) => g.total_recommended));

				const col4Total =
					sumStr(contractWorksWbsGroups.map((g) => g.variance_to_claim)) +
					sumStr(psGroups.map((g) => g.variance_to_claim)) +
					sumStr(variationGroups.map((g) => g.variance_to_claim));

				const col5Total =
					sumStr(contractWorksWbsGroups.map((g) => g.previously_paid)) +
					sumStr(psGroups.map((g) => g.previously_paid)) +
					sumStr(variationGroups.map((g) => g.previously_paid));

				const col6Total =
					sumStr(contractWorksWbsGroups.map((g) => g.recommended_this_period)) +
					sumStr(psGroups.map((g) => g.recommended_this_period)) +
					sumStr(variationGroups.map((g) => g.recommended_this_period));

				const retCol2 = calcRet(col2Total, retentionTiers);
				const retCol3 = calcRet(col3Total, retentionTiers);
				const retCol5 = calcRet(col5Total, retentionTiers);
				const retCol4 = retCol3 - retCol2;
				const retCol6 = retCol3 - retCol5;

				const tierBreakdown = calcRetTiers(col3Total, retentionTiers);
				const tierBreakdownClaimed = calcRetTiers(col2Total, retentionTiers);
				const hasRetention = retentionTiers.length > 0;

				const fmtRet = (v: number) => {
					const formatted = Math.abs(v).toLocaleString(undefined, { minimumFractionDigits: 2 });
					return v !== 0 ? `(${formatted})` : "0.00";
				};

				const fmtRetOrDash = (v: number) => {
					const formatted = Math.abs(v).toLocaleString(undefined, { minimumFractionDigits: 2 });
					return v !== 0 ? `(${formatted})` : "-";
				};

				const fmtTotalVal = (v: number) => {
					const formatted = Math.abs(v).toLocaleString(undefined, { minimumFractionDigits: 2 });
					if (v < 0) return <span className="text-err-tint">({formatted})</span>;
					return formatted;
				};

				return (
					<div>
						<div className="overflow-x-auto">
							<table className="w-full table-fixed">
								{colgroup}
								<tbody>
									{hasRetention && (
										<>
											{tierBreakdown.map((tier, idx) => (
												<tr key={idx} className="text-xs text-ink-3">
													<td className="pl-6 pr-3 py-1 italic text-xs">
														{fmtPct(tier.percentage)}% of total works recommended
													</td>
													<td className="px-3 py-1"></td>
													<td className="px-3 py-1"></td>
													<td className="px-3 py-1 text-right text-xs">{fmtRet(tier.amount)}</td>
													<td className="px-3 py-1"></td>
													<td className="px-3 py-1 text-right text-xs">
														{fmtRet(tier.amount - tierBreakdownClaimed[idx].amount)}
													</td>
													<td className="px-3 py-1" colSpan={4}></td>
												</tr>
											))}
											<tr className="text-xs border-t border-line">
												<td className="px-3 py-2 font-medium">Retentions</td>
												<td className="px-3 py-2"></td>
												<td className="px-3 py-2 text-right text-err">{fmtRetOrDash(retCol2)}</td>
												<td className="px-3 py-2 text-right text-err">{fmtRetOrDash(retCol3)}</td>
												<td className="px-3 py-2"></td>
												<td className="px-3 py-2 text-right text-err">{fmtRetOrDash(retCol4)}</td>
												<td className="px-3 py-2 text-right text-err">{fmtRetOrDash(retCol5)}</td>
												<td className="px-3 py-2 text-right text-err">{fmtRetOrDash(retCol6)}</td>
												<td className="px-3 py-2" colSpan={2}></td>
											</tr>
										</>
									)}
								</tbody>
								<tfoot>
									<tr className="font-semibold text-[13px]" style={{ background: "var(--color-brand)", color: "var(--color-paper)" }}>
										<td className="px-3 py-3">TOTAL</td>
										<td className="px-3 py-3 text-right">{fmtTotalVal(col1Total)}</td>
										<td className="px-3 py-3 text-right">{fmtTotalVal(col2Total - retCol2)}</td>
										<td className="px-3 py-3 text-right">{fmtTotalVal(col3Total - retCol3)}</td>
										<td className="px-3 py-3"></td>
										<td className="px-3 py-3 text-right">{fmtTotalVal(col4Total - retCol4)}</td>
										<td className="px-3 py-3 text-right">{fmtTotalVal(col5Total - retCol5)}</td>
										<td className="px-3 py-3 text-right">{fmtTotalVal(col6Total - retCol6)}</td>
										<td className="px-3 py-3" colSpan={2}></td>
									</tr>
								</tfoot>
							</table>
						</div>
					</div>
				);
			})()}
			</div>
			</section>
		</div>
	);
}

function CategorySection({
	catGroup,
	colCount,
	subcategoryMap,
	onUpdate,
	onReclassify,
	isPending,
	claimLineWarnings,
	claimLineConfidence,
	wbsInterimMap,
	onInterimAdjust,
	onCloseOut,
}: {
	catGroup: CategoryGroup;
	colCount: number;
	subcategoryMap: Map<string, WBSCode>;
	onUpdate: (id: string, data: Record<string, unknown>) => void;
	onReclassify: (itemId: string) => void;
	isPending: boolean;
	claimLineWarnings?: Map<string, string[]>;
	claimLineConfidence?: Map<string, number>;
	wbsInterimMap: Map<string, PriorInterimItem>;
	onInterimAdjust: (parentId: string, description: string, previouslyPaid: string, existingComment: string | null) => void;
	onCloseOut: (parentId: string) => void;
}) {
	// Sort WBS groups by subcategory sort_order
	const sortedGroups = [...catGroup.wbsGroups].sort((a, b) => {
		const subA = subcategoryMap.get(a.wbs_code_id);
		const subB = subcategoryMap.get(b.wbs_code_id);
		return (subA?.sort_order ?? 999) - (subB?.sort_order ?? 999);
	});

	// Category sum from child groups
	const categorySum = sortedGroups.reduce(
		(sum, g) => sum + Number(g.contract_sum || 0),
		0,
	);

	return (
		<>
			<tr
				style={{
					background: "var(--color-paper-2)",
					borderTop: "1px solid var(--color-line)",
					borderBottom: "1px solid var(--color-line)",
				}}
			>
				<td colSpan={colCount} className="px-3.5 py-2">
					<div className="flex items-center justify-between">
						<div className="flex items-center gap-2.5">
							<span
								className="font-mono-nums"
								style={{
									fontSize: 10,
									color: "var(--color-ink-4)",
									letterSpacing: "0.06em",
								}}
							>
								{catGroup.category.code}
							</span>
							<span className="text-xs font-medium">
								{catGroup.category.description}
							</span>
						</div>
						<span
							className="font-mono-nums"
							style={{ fontSize: 11, color: "var(--color-ink-3)" }}
						>
							${categorySum.toLocaleString(undefined, { minimumFractionDigits: 0 })}
						</span>
					</div>
				</td>
			</tr>
			{sortedGroups.map((group) => {
				const sub = subcategoryMap.get(group.wbs_code_id);
				return (
					<WBSGroupRow
						key={group.wbs_code_id}
						group={group}
						wbsCode={sub?.code}
						onUpdate={onUpdate}
						onReclassify={onReclassify}
						isPending={isPending}
						claimLineWarnings={claimLineWarnings}
						claimLineConfidence={claimLineConfidence}
						priorInterim={wbsInterimMap.get(group.wbs_code_id)}
						onInterimAdjust={onInterimAdjust}
						onCloseOut={onCloseOut}
					/>
				);
			})}
		</>
	);
}

const subStyle: React.CSSProperties = {
	fontSize: 8,
	fontWeight: 400,
	opacity: 0.65,
	letterSpacing: "0.02em",
	textTransform: "none" as const,
	fontFamily: "var(--font-mono)",
	textAlign: "center" as const,
};

function AssessmentHeader({ firstCol, sumLabel }: { firstCol: string; sumLabel: string }) {
	return (
		<tr
			className="text-[10px] tracking-[0.06em] uppercase font-medium"
			style={{ background: "var(--color-brand)", color: "var(--color-brand-fg)" }}
		>
			<th className="px-3.5 py-2.5 text-left align-middle">{firstCol}</th>
			<th className="px-3 py-2.5 text-right align-middle">
				<div className="flex flex-col items-end gap-1">
					<span>{sumLabel}</span>
					<span style={subStyle}>col 1</span>
				</div>
			</th>
			<th className="px-3 py-2.5 text-right align-middle">
				<div className="flex flex-col items-end gap-1">
					<span>Contractor Claim</span>
					<span style={subStyle}>cumulative &middot; col 2</span>
				</div>
			</th>
			<th className="px-3 py-2.5 text-right align-middle">
				<div className="flex flex-col items-end gap-1">
					<span>Recommended</span>
					<span style={subStyle}>cumulative &middot; col 3</span>
				</div>
			</th>
			<th className="px-3 py-2.5 text-right align-middle">%</th>
			<th className="px-3 py-2.5 text-right align-middle">
				<div className="flex flex-col items-end gap-1">
					<span>Variance</span>
					<span style={subStyle}>4 = 3 &ndash; 2</span>
				</div>
			</th>
			<th className="px-3 py-2.5 text-right align-middle">
				<div className="flex flex-col items-end gap-1">
					<span>Prev Paid</span>
					<span style={subStyle}>col 5</span>
				</div>
			</th>
			<th className="px-3 py-2.5 text-right align-middle">
				<div className="flex flex-col items-end gap-1">
					<span>This Period</span>
					<span style={subStyle}>6 = 3 &ndash; 5</span>
				</div>
			</th>
			<th className="px-3 py-2.5 text-left align-middle">Comments</th>
			<th className="px-3 py-2.5 text-center align-middle">Actions</th>
		</tr>
	);
}

function fmtTotal(values: string[]) {
	const total = values.reduce((sum, v) => sum + Number(v), 0);
	const formatted = Math.abs(total).toLocaleString(undefined, { minimumFractionDigits: 2 });
	if (total < 0) return <span className="text-err">(${formatted})</span>;
	return `$${formatted}`;
}

function fmtPct(decimal: string) {
	const pct = Number(decimal) * 100;
	return pct % 1 === 0 ? pct.toFixed(0) : parseFloat(pct.toFixed(4)).toString();
}

function sortTiers(tiers: { percentage: string; up_to_amount: string | null }[]) {
	return [...tiers].sort((a, b) => {
		const aAmt = a.up_to_amount ? Number(a.up_to_amount) : Infinity;
		const bAmt = b.up_to_amount ? Number(b.up_to_amount) : Infinity;
		return aAmt - bAmt;
	});
}

function roundCurrency(value: number): number {
	return Number(value.toFixed(2));
}

function calcRet(
	total: number,
	tiers: { percentage: string; up_to_amount: string | null }[]
): number {
	let remaining = total;
	let totalRetention = 0;

	for (const tier of sortTiers(tiers)) {
		if (remaining <= 0) break;
		const pct = Number(tier.percentage);
		if (!tier.up_to_amount) {
			totalRetention += roundCurrency(remaining * pct);
			remaining = 0;
		} else {
			const applicable = Math.min(remaining, Number(tier.up_to_amount));
			totalRetention += roundCurrency(applicable * pct);
			remaining -= applicable;
		}
	}

	return totalRetention;
}

function calcRetTiers(
	total: number,
	tiers: { percentage: string; up_to_amount: string | null }[]
): { percentage: string; base: number; amount: number }[] {
	let remaining = total;

	return sortTiers(tiers).map((tier) => {
		if (remaining <= 0) return { percentage: tier.percentage, base: 0, amount: 0 };
		const pct = Number(tier.percentage);
		if (!tier.up_to_amount) {
			const base = remaining;
			const amount = roundCurrency(base * pct);
			remaining = 0;
			return { percentage: tier.percentage, base, amount };
		} else {
			const applicable = Math.min(remaining, Number(tier.up_to_amount));
			const amount = roundCurrency(applicable * pct);
			remaining -= applicable;
			return { percentage: tier.percentage, base: applicable, amount };
		}
	});
}
