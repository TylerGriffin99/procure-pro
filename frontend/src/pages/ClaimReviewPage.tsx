import { useCallback, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, Download, FileSpreadsheet, FileText, Sparkles } from "lucide-react";
import api from "@/api/client";
import { Nav } from "@/components/nav";
import type { Breadcrumb } from "@/components/nav";
import ClaimReview from "@/components/ClaimReview";
import SmartReviewPanel from "@/components/SmartReviewPanel";
import { PageHeader } from "@/components/page-header";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuItem } from "@/components/ui/dropdown-menu";
import { Badge } from "@/components/ui/badge";
import { formatCurrency } from "@/components/currency-cell";
import { useFinaliseAssessment } from "@/hooks/useAssessments";
import type { Assessment } from "@/hooks/useAssessments";
import type { Project, Claim, ClaimSummary } from "@/types/domain";

export default function ClaimReviewPage({ projectId, claimId, }: { projectId: string; claimId: string; }) {
	const [smartOpen, setSmartOpen] = useState(true);

	const { data: project } = useQuery<Project>({
		queryKey: ["project", projectId],
		queryFn: () => api.get(`/projects/${projectId}`).then((r) => r.data),
	});

	const { data: claim } = useQuery<Claim & { summary?: ClaimSummary | null }>({
		queryKey: ["claim", projectId, claimId],
		queryFn: () =>
			api.get(`/projects/${projectId}/claims/${claimId}`).then((r) => r.data),
	});
 
	const {
		data: assessment,
		isLoading,
		isError,
	} = useQuery<Assessment>({
		queryKey: ["assessment-by-claim", projectId, claimId],
		queryFn: () =>
			api
				.get(`/projects/${projectId}/assessments/by-claim/${claimId}`)
				.then((r) => r.data),
	});

	const finaliseMutation = useFinaliseAssessment(projectId, assessment?.id ?? "");

	const handleExport = useCallback(async (format: "pdf" | "excel") => {
		if (!assessment) return;
		const res = await api.get(
			`/projects/${projectId}/assessments/${assessment.id}/export?format=${format}`,
			{ responseType: "blob" },
		);
		const url = URL.createObjectURL(res.data);
		const a = document.createElement("a");
		a.href = url;
		const dateStr = new Date()
			.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "2-digit" })
			.replace(/ /g, "");
		const prName = project?.name ?? "Project";
		const prNo = claim?.claim_number ?? assessment.version;
		const ext = format === "excel" ? "xlsx" : "pdf";
		a.download = `${prName} PR No ${prNo} ${dateStr}.${ext}`;
		a.click();
		URL.revokeObjectURL(url);
	}, [projectId, assessment?.id, assessment?.version, project?.name, claim?.claim_number]);

	const breadcrumbs: Breadcrumb[] = [
		{ label: "Projects", href: "/" },
		...(project ? [{ label: project.name, href: `/projects/${projectId}` }] : []),
		...(claim ? [{ label: `Claim #${claim.claim_number}` }] : []),
	];

	if (isLoading)
		return (
			<div className="min-h-screen bg-paper flex flex-col">
				<Nav breadcrumbs={breadcrumbs} />
				<div className="w-full px-8 py-7">
					<p className="text-ink-3">Loading assessment...</p>
				</div>
			</div>
		);
	if (isError || !assessment)
		return (
			<div className="min-h-screen bg-paper flex flex-col">
				<Nav breadcrumbs={breadcrumbs} />
				<div className="text-center py-12">
					<p className="text-err mb-4">
						No assessment found for this claim.
					</p>
					<a
						href={`/projects/${projectId}`}
						className="text-primary hover:underline"
					>
						Back to project
					</a>
				</div>
			</div>
		);

	const fmt = (v: string | number | null | undefined) =>
		v != null ? `$${formatCurrency(v)}` : "-";

	// Compute summary totals from pre-grouped data
	const wbsGroups = assessment.wbs_groups || [];
	const varGroups = assessment.variation_groups || [];
	const psGroups = assessment.ps_groups || [];

	// Filter out WBS groups that belong to PS/VR categories to avoid double-counting
	const wbsCodes = project?.wbs_codes || [];
	const subcategoryMap = new Map<string, { parent_id: string | null }>();
	const excludedCategoryIds = new Set<string>();
	for (const wbs of wbsCodes) {
		if (wbs.level === "subcategory") subcategoryMap.set(wbs.id, wbs);
		if (wbs.level === "category" && /^(PS|VR)$/i.test(wbs.code)) excludedCategoryIds.add(wbs.id);
	}
	const contractWorksWbsGroups = wbsGroups.filter((group) => {
		if (!group.wbs_code_id) return true;
		const sub = subcategoryMap.get(group.wbs_code_id);
		return !sub?.parent_id || !excludedCategoryIds.has(sub.parent_id);
	});

	const sumField = (vals: string[]) => vals.reduce((acc, v) => acc + Number(v || 0), 0);

	const contractSum =
		sumField(contractWorksWbsGroups.map((g) => g.contract_sum)) +
		sumField(psGroups.map((g) => g.contract_sum)) +
		sumField(varGroups.map((g) => g.contractor_submission));

	const originalContractWorks = claim?.summary?.original_contract_total
		? Number(claim.summary.original_contract_total)
		: sumField(contractWorksWbsGroups.map((g) => g.contract_sum)) +
		  sumField(psGroups.map((g) => g.contract_sum));

	const totalContractorClaims =
		sumField(contractWorksWbsGroups.map((g) => g.contractor_claim_to_date)) +
		sumField(psGroups.map((g) => g.contractor_claim_to_date)) +
		sumField(varGroups.map((g) => g.contractor_claim_to_date));

	const totalRecommended =
		sumField(contractWorksWbsGroups.map((g) => g.total_recommended)) +
		sumField(psGroups.map((g) => g.total_recommended)) +
		sumField(varGroups.map((g) => g.total_recommended));

	const retentionTiers = project?.retention_tiers || [];
	const claimRetention = calculateRetention(totalContractorClaims, retentionTiers);
	const totalRetention = calculateRetention(totalRecommended, retentionTiers);
	const totalPaymentToDate = totalRecommended - totalRetention;

	// Previously certified = retention on previously paid amounts
	const totalPrevPaid =
		sumField(contractWorksWbsGroups.map((g) => g.previously_paid)) +
		sumField(psGroups.map((g) => g.previously_paid)) +
		sumField(varGroups.map((g) => g.previously_paid));
	const prevRetention = calculateRetention(totalPrevPaid, retentionTiers);
	const previouslyCertified = totalPrevPaid - prevRetention;

	const recommendedThisPeriod = totalPaymentToDate - previouslyCertified;

	const wbsOptions =
		project?.wbs_codes
			?.filter((w) => w.level === "subcategory")
			.map((w) => ({ id: w.id, label: `${w.code} - ${w.description}` })) || [];

	// Build claim_line_item_id -> warnings lookup for assessment rows
	const claimLineWarnings = new Map<string, string[]>();
	const claimLineConfidence = new Map<string, number>();
	if (claim?.line_items) {
		for (const li of claim.line_items) {
			if (li.warnings.length > 0) claimLineWarnings.set(li.id, li.warnings);
			if (li.categorisation_confidence !== null) {
				claimLineConfidence.set(li.id, Number(li.categorisation_confidence));
			}
		}
	}

	const hasUnapproved = [
		...wbsGroups.flatMap((g) => g.child_rows.length > 0 ? g.child_rows : g.history_row ? [g.history_row] : []),
		...varGroups.flatMap((g) => g.child_rows.length > 0 ? g.child_rows : g.history_row ? [g.history_row] : []),
		...psGroups.flatMap((g) => g.child_rows.length > 0 ? g.child_rows : g.history_row ? [g.history_row] : []),
	].some((item) => item.status === "unapproved");

	const claimSubtitle = claim ? (
		<p className="text-ink-3 text-sm">
			Progress Claim #{claim.claim_number}
			{claim.period_from && claim.period_to && (
				<span> | Period: {claim.period_from} to {claim.period_to}</span>
			)}
			{claim.payment_due && <span> | Due: {claim.payment_due}</span>}
		</p>
	) : undefined;

	return (
		<div className="min-h-screen bg-paper flex flex-col">
			<Nav breadcrumbs={breadcrumbs} />
			<div className="flex flex-1 min-h-0">
				{/* Main content */}
				<div className="flex-1 min-w-0 overflow-y-auto">
					<div className="w-full px-8 py-7 pb-20">
						<PageHeader
							title={`Payment Recommendation #${claim?.claim_number ?? assessment.version}`}
							backHref={`/projects/${projectId}`}
							backLabel={`Back to ${project?.name || "Project"}`}
							subtitle={claimSubtitle}
							actions={
								<>
									{!smartOpen && (
										<Button variant="quiet" size="md" onClick={() => setSmartOpen(true)}>
											<Sparkles className="h-3.5 w-3.5" />
											Smart Review
										</Button>
									)}
									<DropdownMenu
										trigger={
											<Button variant="secondary" size="md">
												<Download className="h-4 w-4" />
												Export
												<ChevronDown className="h-3 w-3 ml-0.5 opacity-60" />
											</Button>
										}
									>
										<DropdownMenuItem onClick={() => handleExport("pdf")}>
											<span className="inline-flex items-center gap-2">
												<FileText className="h-3.5 w-3.5" />
												PDF
											</span>
										</DropdownMenuItem>
										<DropdownMenuItem onClick={() => handleExport("excel")}>
											<span className="inline-flex items-center gap-2">
												<FileSpreadsheet className="h-3.5 w-3.5" />
												Excel
											</span>
										</DropdownMenuItem>
									</DropdownMenu>
									{assessment.status === "finalised" ? (
										<Badge variant="success" className="px-3 py-2 text-sm">
											Finalised
										</Badge>
									) : (
										<Button
											variant="primary"
											size="md"
											onClick={() => {
												if (
													confirm(
														"Are you sure? This will lock the assessment and set it as the baseline for future claims."
													)
												) {
													finaliseMutation.mutate();
												}
											}}
											disabled={finaliseMutation.isPending || hasUnapproved}
											title={
												hasUnapproved
													? "Approve all line items before finalising"
													: undefined
											}
										>
											{finaliseMutation.isPending ? "Finalising..." : "Finalise Assessment"}
										</Button>
									)}
								</>
							}
						/>

						{/* Summary Cards */}
						<div className="grid grid-cols-4 mb-8 border border-line rounded-[var(--radius-lg)] bg-surface overflow-hidden">
							<SummaryCell label="Contract Sum" value={fmt(contractSum)} sub={`Original contract ${fmt(originalContractWorks)}`} />
							<SummaryCell label="Contractor Claimed" value={fmt(totalContractorClaims)} sub={`Less retentions ${fmt(claimRetention)}`} />
							<SummaryCell label="Total Recommended to Date" value={fmt(totalRecommended)} sub={`Less retentions ${fmt(totalRetention)}`} />
							<SummaryCell label="Recommended This Period" value={fmt(recommendedThisPeriod)} sub={`Prev certified ${fmt(previouslyCertified)}`} highlight />
						</div>

						{/* Validation Warnings */}
						{claim?.validation_warnings && claim.validation_warnings.length > 0 && (
							<Alert variant="warning" className="mb-4">
								<AlertTitle>Parsing Warnings</AlertTitle>
								<AlertDescription>
									<ul className="mt-1 space-y-1">
										{claim.validation_warnings.map((w, i) => (
											<li key={i}>{w}</li>
										))}
									</ul>
								</AlertDescription>
							</Alert>
						)}

						{/* Assessment Table */}
						<ClaimReview
							assessment={assessment}
							projectId={projectId}
							wbsOptions={wbsOptions}
							wbsCodes={wbsCodes}
							claimLineWarnings={claimLineWarnings}
							claimLineConfidence={claimLineConfidence}
							retentionTiers={retentionTiers}
						/>
					</div>
				</div>

				{/* Smart Review Panel */}
				{smartOpen && (
					<SmartReviewPanel
						projectId={projectId}
						claimId={claimId}
						onClose={() => setSmartOpen(false)}
					/>
				)}
			</div>
		</div>
	);
}

function SummaryCell({ label, value, sub, highlight }: { label: string; value: string; sub?: string; highlight?: boolean }) {
  return (
    <div className={`py-5 px-[22px] border-l border-line first:border-l-0 transition-colors ${highlight ? "bg-brand-tint" : ""}`}>
      <div className={`eyebrow mb-2.5 ${highlight ? "text-brand-2" : "text-ink-3"}`}>{label}</div>
      <div className={`font-display text-[28px] tracking-tight leading-tight ${highlight ? "text-brand-2" : "text-ink"}`}>
        {value}
      </div>
      {sub && <div className={`mt-1.5 text-[11px] font-mono-nums ${highlight ? "text-brand-2" : "text-ink-3"}`}>{sub}</div>}
    </div>
  );
}

function calculateRetention(
	totalRecommended: number,
	tiers: { percentage: string; up_to_amount: string | null }[],
): number {
	let remaining = totalRecommended;
	let totalRetention = 0;

	const sorted = [...tiers].sort((a, b) => {
		const aAmt = a.up_to_amount ? Number(a.up_to_amount) : Infinity;
		const bAmt = b.up_to_amount ? Number(b.up_to_amount) : Infinity;
		return aAmt - bAmt;
	});

	for (const tier of sorted) {
		if (remaining <= 0) break;
		const pct = Number(tier.percentage);
		if (!tier.up_to_amount) {
			totalRetention += Math.round(remaining * pct * 100) / 100;
			remaining = 0;
		} else {
			const applicable = Math.min(remaining, Number(tier.up_to_amount));
			totalRetention += Math.round(applicable * pct * 100) / 100;
			remaining -= applicable;
		}
	}

	return totalRetention;
}
