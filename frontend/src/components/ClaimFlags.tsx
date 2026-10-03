import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Building2, ChevronDown, Check } from "lucide-react";
import api from "@/api/client";
import { Badge } from "@/components/ui/badge";
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

const SEVERITY_CONFIG = {
	error: {
		bg: "bg-red-50",
		border: "border-red-200",
		label: "Errors",
	},
	warning: {
		bg: "bg-amber-50",
		border: "border-amber-200",
		label: "Warnings",
	},
	info: {
		bg: "bg-brand-tint",
		border: "border-brand/20",
		label: "Info",
	},
};

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

export default function ClaimFlags({
	projectId,
	claimId,
}: {
	projectId: string;
	claimId: string;
}) {
	const queryClient = useQueryClient();
	const [expanded, setExpanded] = useState(true);

	const { data: flags = [], isLoading } = useQuery<ClaimFlag[]>({
		queryKey: ["claim-flags", projectId, claimId],
		queryFn: () =>
			api
				.get(`/projects/${projectId}/claims/${claimId}/flags`)
				.then((r) => r.data),
	});

	const resolveMutation = useMutation({
		mutationFn: ({
			flagId,
			resolved,
		}: {
			flagId: string;
			resolved: boolean;
		}) =>
			api.patch(`/projects/${projectId}/claims/${claimId}/flags/${flagId}`, {
				resolved,
			}),
		onSuccess: () => {
			queryClient.invalidateQueries({
				queryKey: ["claim-flags", projectId, claimId],
			});
		},
	});

	if (isLoading) return null;
	if (flags.length === 0) return null;

	const grouped = {
		error: flags.filter((f) => f.severity === "error"),
		warning: flags.filter((f) => f.severity === "warning"),
		info: flags.filter((f) => f.severity === "info"),
	};

	const unresolvedCount = flags.filter((f) => !f.resolved).length;
	const totalCount = flags.length;

	return (
		<div className="mb-6">
			<button
				onClick={() => setExpanded(!expanded)}
				className="w-full flex items-center justify-between bg-white border rounded-lg px-4 py-3 hover:bg-paper-2 transition-colors"
			>
				<div className="flex items-center gap-3">
					<Building2 className="w-5 h-5 text-amber-500" />
					<span className="font-semibold text-ink-2">Claim Warnings</span>
					{unresolvedCount > 0 ? (
						<Badge variant="error">{unresolvedCount} unresolved</Badge>
					) : (
						<Badge variant="success">All resolved</Badge>
					)}
					<span className="text-xs text-ink-3">{totalCount} total</span>
				</div>
				<ChevronDown
					className={cn(
						"w-4 h-4 text-ink-3 transition-transform duration-200",
						expanded && "rotate-180"
					)}
				/>
			</button>

			{expanded && (
				<div className="mt-2 space-y-3">
					{(["error", "warning", "info"] as const).map((severity) => {
						const items = grouped[severity];
						if (items.length === 0) return null;
						const config = SEVERITY_CONFIG[severity];

						return (
							<div
								key={severity}
								className={cn(
									"rounded-lg border overflow-hidden",
									config.border,
									config.bg
								)}
							>
								<div className="px-4 py-2 flex items-center gap-2">
									<Badge variant={severity}>
										{config.label} ({items.length})
									</Badge>
								</div>
								<div className="divide-y divide-line/50">
									{items.map((flag) => (
										<div
											key={flag.id}
											className={cn(
												"px-4 py-3 flex items-start gap-3",
												flag.resolved && "opacity-50"
											)}
										>
											{/* Resolve toggle */}
											<button
												onClick={() =>
													resolveMutation.mutate({
														flagId: flag.id,
														resolved: !flag.resolved,
													})
												}
												className="mt-0.5 flex-shrink-0"
												title={
													flag.resolved
														? "Mark as unresolved"
														: "Mark as resolved"
												}
											>
												{flag.resolved ? (
													<div className="w-5 h-5 rounded border-2 border-emerald-400 bg-emerald-100 flex items-center justify-center">
														<Check className="w-3 h-3 text-emerald-600" strokeWidth={3} />
													</div>
												) : (
													<div className="w-5 h-5 rounded border-2 border-line hover:border-ink-3" />
												)}
											</button>

											{/* Flag content */}
											<div className="flex-1 min-w-0">
												<div className="flex items-center gap-2">
													<span className="text-sm font-medium text-ink-1">
														{FLAG_TYPE_LABELS[flag.flag_type] || flag.flag_type}
													</span>
													{flag.line_item_ref && (
														<span className="text-xs px-1.5 py-0.5 rounded bg-paper-2 text-ink-2 font-mono">
															{flag.line_item_ref}
														</span>
													)}
												</div>
												<p className="text-sm text-ink-2 mt-0.5">
													{flag.description}
												</p>
												{(flag.expected_value || flag.actual_value) && (
													<div className="flex gap-4 mt-1 text-xs text-ink-3">
														{flag.expected_value && (
															<span>
																Expected:{" "}
																<span className="font-mono">
																	{flag.expected_value}
																</span>
															</span>
														)}
														{flag.actual_value && (
															<span>
																Actual:{" "}
																<span className="font-mono">
																	{flag.actual_value}
																</span>
															</span>
														)}
													</div>
												)}
											</div>
										</div>
									))}
								</div>
							</div>
						);
					})}
				</div>
			)}
		</div>
	);
}
