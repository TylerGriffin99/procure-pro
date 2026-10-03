import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Info, X, Sparkles, Check, RotateCcw } from "lucide-react";
import api from "@/api/client";
import { cn } from "@/lib/utils";

interface ClaimFlag {
	id: string;
	flag_type: string;
	severity: "error" | "warning" | "info";
	line_item_ref: string | null;
	description: string;
	expected_value: string | null;
	actual_value: string | null;
	resolved: boolean;
	resolved_at: string | null;
	created_at: string;
}

interface SmartReviewPanelProps {
	projectId: string;
	claimId: string;
	onClose: () => void;
}

const FLAG_TYPE_LABELS: Record<string, string> = {
	total_mismatch: "Total Mismatch",
	project_over_budget: "Project Over Budget",
	over_claim: "Over-claim",
	percentage_error: "Percentage Error",
	ptd_decrease: "PTD Decrease",
	missing_ref: "Missing Reference",
	duplicate_item: "Duplicate Item",
	format_warning: "Format Warning",
	confidence_low: "Low Confidence",
};

const SEVERITY_ORDER: Record<ClaimFlag["severity"], number> = {
	error: 0,
	warning: 1,
	info: 2,
};

const SEVERITY_CONFIG = {
	error: {
		colorClass: "text-err",
		bgClass: "bg-err-tint",
		label: "CRITICAL",
		Icon: AlertTriangle,
	},
	warning: {
		colorClass: "text-warn",
		bgClass: "bg-warn-tint",
		label: "WARNING",
		Icon: AlertTriangle,
	},
	info: {
		colorClass: "text-brand",
		bgClass: "bg-brand-tint",
		label: "INFO",
		Icon: Info,
	},
} as const;

/* ── Confidence meter ─────────────────────────────────────── */
function ConfidenceMeter({ value }: { value: number | null }) {
	if (value === null) {
		return (
			<div>
				<div className="flex items-baseline justify-between mb-1.5">
					<span className="eyebrow">Overall confidence</span>
					<span className="text-[11px] text-ink-3">Waiting for flags</span>
				</div>
				<div className="h-3.5 bg-paper-3 rounded" />
			</div>
		);
	}
	const v = Math.round(value * 100);
	const color =
		v < 70 ? "var(--color-warn)" : v < 85 ? "var(--color-brand)" : "var(--color-ok)";

	return (
		<div>
			<div className="flex items-baseline justify-between mb-1.5">
				<span className="eyebrow">Overall confidence</span>
				<span className="font-mono-nums text-[13px] text-ink font-medium">{v}%</span>
			</div>
			<div className="flex gap-0.5 h-3.5">
				{Array.from({ length: 20 }, (_, i) => {
					const cellVal = (i + 1) * 5;
					const active = cellVal <= v;
					return (
						<svg key={i} viewBox="0 0 8 14" className="flex-1 h-3.5" preserveAspectRatio="none">
							<polygon
								points="0,0 8,0 8,14 0,14"
								fill={active ? color : "var(--color-paper-3)"}
								opacity={active ? 0.55 + (i / 20) * 0.45 : 1}
							/>
							<polygon
								points="0,0 8,0 4,7"
								fill={active ? color : "var(--color-paper-3)"}
								opacity={active ? 0.75 : 1}
							/>
						</svg>
					);
				})}
			</div>
		</div>
	);
}

/* ── Tab button ───────────────────────────────────────────── */
function TabBtn({
	active,
	onClick,
	children,
}: {
	active: boolean;
	onClick: () => void;
	children: React.ReactNode;
}) {
	return (
		<button
			onClick={onClick}
			className={cn(
				"inline-flex items-center gap-1.5 px-3 py-2.5 text-xs -mb-px border-b-2",
				active
					? "text-ink font-medium border-ink"
					: "text-ink-3 font-normal border-transparent",
			)}
		>
			{children}
		</button>
	);
}

/* ── Flag card ────────────────────────────────────────────── */
function FlagCard({
	flag,
	onToggleResolve,
	isPending,
}: {
	flag: ClaimFlag;
	onToggleResolve: () => void;
	isPending: boolean;
}) {
	const config = SEVERITY_CONFIG[flag.severity];
	const { Icon } = config;

	return (
		<div
			className={cn(
				"rounded-[var(--radius-md)] p-3 transition-opacity",
				config.bgClass,
				flag.resolved && "opacity-50",
			)}
		>
			<div className="flex items-start gap-2.5">
				<div className={cn("mt-0.5 shrink-0", config.colorClass)}>
					<Icon className="w-3.5 h-3.5" strokeWidth={2.5} />
				</div>
				<div className="flex-1 min-w-0">
					{/* Top line */}
					<div className="flex items-center gap-2 mb-1">
						<span className={cn("text-[10px] font-medium tracking-[0.08em] uppercase", config.colorClass)}>
							{config.label}
						</span>
						{flag.line_item_ref && (
							<span className="font-mono text-[10px] text-ink-4">{flag.line_item_ref}</span>
						)}
						<div className="flex-1" />
					</div>

					{/* Title */}
					<p className="text-xs font-medium text-ink leading-snug">
						{FLAG_TYPE_LABELS[flag.flag_type] ?? flag.flag_type}
					</p>

					{/* Description */}
					<p className="text-xs text-ink-2 mt-1 leading-snug">{flag.description}</p>

					{/* Expected / Actual */}
					{(flag.expected_value || flag.actual_value) && (
						<div className="flex gap-3 mt-1.5">
							{flag.expected_value && (
								<span className="text-[11px] text-ink-3">
									Expected: <span className="font-mono">{flag.expected_value}</span>
								</span>
							)}
							{flag.actual_value && (
								<span className="text-[11px] text-ink-3">
									Actual: <span className="font-mono">{flag.actual_value}</span>
								</span>
							)}
						</div>
					)}

					{/* Resolve toggle */}
					<div className="mt-2 flex justify-end">
						<button
							onClick={(e) => { e.stopPropagation(); onToggleResolve(); }}
							disabled={isPending}
							className={cn(
								"text-[11px] font-medium px-2 py-0.5 rounded transition-colors",
								flag.resolved
									? "text-ink-3 hover:text-ink-2"
									: "text-brand hover:text-brand-2",
							)}
						>
							{flag.resolved ? "Unresolve" : "Resolve"}
						</button>
					</div>
				</div>
			</div>
		</div>
	);
}

/* ── Checks tab ──────────────────────────────────────────── */
function ChecksList() {
	const checks = [
		"Contract sum matches WBS total",
		"Sum of line items = claim total",
		"Line items mapped to WBS codes",
		"Retention tiers applied correctly",
		"Previously paid \u2264 recommended",
	];
	return (
		<div className="flex flex-col">
			<p className="text-[10px] text-ink-4 uppercase tracking-wide mb-2">Automated checks (coming soon)</p>
			<div className="rounded border border-dashed border-line bg-paper-2 px-3 py-4 text-center">
				<p className="text-xs text-ink-3 mb-2">These checks will run automatically once available.</p>
				<ul className="text-[11px] text-ink-4 space-y-1">
					{checks.map((name, i) => (
						<li key={i}>{name}</li>
					))}
				</ul>
			</div>
		</div>
	);
}

/* ── History tab ─────────────────────────────────────────── */
function HistoryTab() {
	return (
		<div className="flex flex-col items-center justify-center py-12 text-center">
			<p className="text-xs text-ink-3">
				Claim history comparison will appear here after multiple claims are processed.
			</p>
		</div>
	);
}

/* ── Main panel ──────────────────────────────────────────── */
export default function SmartReviewPanel({
	projectId,
	claimId,
	onClose,
}: SmartReviewPanelProps) {
	const queryClient = useQueryClient();
	const [tab, setTab] = useState<"flags" | "checks" | "history">("flags");

	const { data: flags = [] } = useQuery<ClaimFlag[]>({
		queryKey: ["claim-flags", projectId, claimId],
		queryFn: () =>
			api.get(`/projects/${projectId}/claims/${claimId}/flags`).then((r) => r.data),
	});

const resolveMutation = useMutation({
		mutationFn: ({ flagId, resolved }: { flagId: string; resolved: boolean }) =>
			api.patch(`/projects/${projectId}/claims/${claimId}/flags/${flagId}`, { resolved }),
		onSuccess: () =>
			queryClient.invalidateQueries({ queryKey: ["claim-flags", projectId, claimId] }),
	});

	const sortedFlags = [...flags].sort(
		(a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity],
	);

	const unresolvedCount = flags.filter((f) => !f.resolved).length;
	const totalCount = flags.length;
	const confidence = totalCount > 0 ? 1 - (unresolvedCount / totalCount) * 0.4 : null;

	return (
		<aside className="sticky top-[52px] h-[calc(100vh-52px)] w-[380px] border-l border-line bg-surface flex flex-col animate-[slideRight_280ms_ease-out]">
			{/* Header */}
			<div className="px-5 pt-4 pb-3.5 border-b border-line shrink-0">
				<div className="flex items-center justify-between mb-3">
					<div className="flex items-center gap-2">
						<Sparkles className="w-4 h-4 text-brand" />
						<span className="text-[13px] font-medium text-ink tracking-[-0.005em]">Smart Review</span>
						<span className="text-[10px] font-medium tracking-wide uppercase px-1.5 py-0.5 rounded border border-line text-ink-3">
							BETA
						</span>
					</div>
					<button
						onClick={onClose}
						className="w-6 h-6 flex items-center justify-center rounded hover:bg-paper-2 text-ink-3 hover:text-ink-2 transition-colors"
						aria-label="Close Smart Review panel"
					>
						<X className="w-4 h-4" />
					</button>
				</div>

				<ConfidenceMeter value={confidence} />

				{totalCount > 0 && (
					<p className="text-[11px] text-ink-3 mt-2 leading-snug">
						{unresolvedCount} unresolved of {totalCount} total
					</p>
				)}
			</div>

			{/* Tabs */}
			<div className="flex shrink-0 border-b border-line px-3">
				<TabBtn active={tab === "flags"} onClick={() => setTab("flags")}>
					Flags
					{totalCount > 0 && (
						<span className={cn(
							"font-mono-nums inline-flex items-center justify-center min-w-4 h-4 px-1 rounded-full text-[10px] font-medium",
							unresolvedCount > 0 ? "bg-warn-tint text-warn" : "bg-paper-3 text-ink-3",
						)}>
							{totalCount}
						</span>
					)}
				</TabBtn>
				<TabBtn active={tab === "checks"} onClick={() => setTab("checks")}>Checks</TabBtn>
				<TabBtn active={tab === "history"} onClick={() => setTab("history")}>History</TabBtn>
			</div>

			{/* Body */}
			<div className="flex-1 overflow-y-auto p-3 space-y-2">
				{tab === "flags" && (
					<>
						{sortedFlags.length === 0 ? (
							<div className="flex flex-col items-center justify-center h-full text-center pb-12">
								<div className="w-8 h-8 rounded-full bg-ok-tint flex items-center justify-center mb-3">
									<Check className="w-4 h-4 text-ok" />
								</div>
								<p className="text-[13px] font-medium text-ink-2">No flags found</p>
								<p className="text-xs text-ink-3 mt-1">This claim looks clean.</p>
							</div>
						) : (
							sortedFlags.map((flag) => (
								<FlagCard
									key={flag.id}
									flag={flag}
									isPending={resolveMutation.isPending}
									onToggleResolve={() =>
										resolveMutation.mutate({ flagId: flag.id, resolved: !flag.resolved })
									}
								/>
							))
						)}
					</>
				)}
				{tab === "checks" && <ChecksList />}
				{tab === "history" && <HistoryTab />}
			</div>

			{/* Footer */}
			<div className="border-t border-line px-4 py-3 shrink-0 bg-paper">
				<div className="flex items-center justify-between gap-2">
					<div>
						<div className="flex items-center gap-1.5 text-[11px] text-ink-3">
							<span className="w-1.5 h-1.5 rounded-full bg-ok shrink-0" />
							Run completed &middot; {totalCount} flag{totalCount !== 1 ? "s" : ""} detected
						</div>
						<div className="font-mono mt-0.5 text-[10px] text-ink-4">
							Reviewed against contract baseline
						</div>
					</div>
					<button
						disabled
						title="Re-run requires persistent file storage (coming soon)"
						className="inline-flex items-center gap-1.5 text-[11px] font-medium px-2.5 py-1.5 rounded transition-colors text-ink-4 bg-paper-2 border border-line-2 cursor-not-allowed opacity-50"
					>
						<RotateCcw className="w-3 h-3" />
						Re-run
					</button>
				</div>
			</div>
		</aside>
	);
}
