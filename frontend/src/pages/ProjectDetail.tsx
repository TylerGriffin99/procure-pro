import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, useEffect, useRef, useCallback, type DragEvent, type ChangeEvent } from "react";
import { Pencil, ArrowLeft, Upload, ChevronRight, Trash2 } from "lucide-react";
import api from "@/api/client";
import { Nav } from "@/components/nav";
import type { Breadcrumb } from "@/components/nav";
import HarnessPanel from "@/components/HarnessPanel";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { Project, ClaimListItem } from "@/types/domain";
import { useRevertAssessmentToDraft } from "@/hooks/useAssessments";

/* ── Helpers ────────────────────────────────────────────────── */
function fmt(v: string | number | null | undefined) {
	if (v == null) return "-";
	return `$${Number(v).toLocaleString(undefined, { minimumFractionDigits: 2 })}`;
}

/* ── InlineMeta ─────────────────────────────────────────────── */
function InlineMeta({ label, value }: { label: string; value: React.ReactNode }) {
	return (
		<div>
			<div className="eyebrow mb-1">{label}</div>
			<div className="text-[13px] text-ink">{value}</div>
		</div>
	);
}

/* ── SectionHead ────────────────────────────────────────────── */
function SectionHead({ title, eyebrow, right }: { title: string; eyebrow?: string; right?: React.ReactNode }) {
	return (
		<div className="flex items-end justify-between mb-3.5">
			<div>
				{eyebrow && <div className="eyebrow mb-1">{eyebrow}</div>}
				<h2 className="text-[16px] font-medium tracking-[-0.01em]">{title}</h2>
			</div>
			{right}
		</div>
	);
}

/* ── CompactDropzone ────────────────────────────────────────── */
function CompactDropzone({ onFileSelect, disabled, isUploading }: {
	onFileSelect: (file: File) => void;
	disabled: boolean;
	isUploading: boolean;
}) {
	const [dragOver, setDragOver] = useState(false);
	const fileInputRef = useRef<HTMLInputElement>(null);

	const handleDragOver = useCallback((e: DragEvent) => {
		e.preventDefault();
		if (!disabled) setDragOver(true);
	}, [disabled]);

	const handleDragLeave = useCallback((e: DragEvent) => {
		e.preventDefault();
		setDragOver(false);
	}, []);

	const handleDrop = useCallback((e: DragEvent) => {
		e.preventDefault();
		setDragOver(false);
		if (disabled) return;
		const files = e.dataTransfer.files;
		if (files.length > 0) onFileSelect(files[0]);
	}, [onFileSelect, disabled]);

	const handleFileInput = (e: ChangeEvent<HTMLInputElement>) => {
		const file = e.target.files?.[0];
		if (file) onFileSelect(file);
	};

	return (
		<div
			onDragOver={handleDragOver}
			onDragLeave={handleDragLeave}
			onDrop={handleDrop}
			className={cn(
				"relative p-7 border border-dashed rounded-[var(--radius-lg)] flex items-center gap-6 transition-all",
				dragOver ? "border-brand bg-brand-tint" : "border-line-2",
				disabled ? "bg-paper-2 opacity-70" : "bg-surface",
			)}
		>
			{/* Folded paper SVG */}
			<div className="w-14 h-14 shrink-0 inline-flex items-center justify-center bg-paper-2 rounded-[var(--radius-md)]">
				<svg viewBox="0 0 40 40" width="36" height="36">
					<path d="M8 4 L28 4 L32 8 L32 36 L8 36 Z" fill="white" stroke="var(--color-ink-3)" strokeWidth="1" />
					<path d="M28 4 L28 8 L32 8" fill="none" stroke="var(--color-ink-3)" strokeWidth="1" />
					<path d="M12 16 L26 16 M12 20 L26 20 M12 24 L22 24 M12 28 L26 28" stroke="var(--color-ink-4)" strokeWidth="0.7" />
				</svg>
			</div>
			<div className="flex-1 min-w-0">
				<h3 className="text-[15px] font-medium mb-1">
					{disabled ? "Finalise current draft before uploading" : "Drop the contractor's progress claim PDF"}
				</h3>
				<p className="text-xs text-ink-3">
					{disabled
						? "Finalise or delete the current draft claim before uploading a new one."
						: "Procure AI will parse, categorise and reconcile against contract & history."}
				</p>
			</div>
			<button
				onClick={() => fileInputRef.current?.click()}
				disabled={disabled || isUploading}
				className={cn(
					"px-4 py-2 rounded-[var(--radius-md)] text-[13px] font-medium border-none inline-flex items-center gap-1.5 whitespace-nowrap",
					disabled
						? "bg-paper-3 text-ink-3 cursor-not-allowed"
						: "bg-brand text-white cursor-pointer",
				)}
			>
				<Upload className="w-3.5 h-3.5" />
				{isUploading ? "Streaming\u2026" : "Choose file"}
			</button>
			<input
				ref={fileInputRef}
				type="file"
				accept="application/pdf"
				onChange={handleFileInput}
				className="hidden"
			/>
		</div>
	);
}

/* ── ClaimRow ───────────────────────────────────────────────── */
function ClaimRow({ claim, projectId, maxClaimNumber }: {
	claim: ClaimListItem;
	projectId: string;
	maxClaimNumber: number;
}) {
	const queryClient = useQueryClient();
	const isFinalised = claim.assessment_status === "finalised";
	const revertMutation = useRevertAssessmentToDraft(projectId, claim.assessment_id ?? "");

	const deleteMutation = useMutation({
		mutationFn: (claimId: string) =>
			api.delete(`/projects/${projectId}/claims/${claimId}`),
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["claims", projectId] });
		},
	});

	return (
		<div
			onClick={() => { window.location.href = `/projects/${projectId}/claims/${claim.id}/review`; }}
			className="grid items-center gap-x-4 px-4 py-3.5 border-b border-line cursor-pointer transition-colors hover:bg-paper-2"
			style={{ gridTemplateColumns: "70px 1fr 1fr 130px 110px 180px" }}
		>
			<div className="font-mono-nums text-[13px] text-ink font-medium">#{claim.claim_number}</div>
			<div className="text-xs text-ink-2 font-mono">
				{claim.period_from && claim.period_to
					? `${claim.period_from} \u2192 ${claim.period_to}`
					: "\u2014"}
			</div>
			<div className="text-xs text-ink-3 font-mono">{claim.payment_due || "\u2014"}</div>
			<div className="font-mono-nums text-right text-xs">{fmt(claim.summary.claimed_amount)}</div>
			<div>
				<span className="inline-flex items-center gap-[5px] text-[11px] font-medium">
					<span className={cn("w-[7px] h-[7px] rounded-full", isFinalised ? "bg-ok" : "bg-warn")} />
					<span className={isFinalised ? "text-ok" : "text-ink-3"}>
						{isFinalised ? "Finalised" : "Draft"}
					</span>
				</span>
			</div>
			<div className="text-right flex gap-1.5 items-center" onClick={(e) => e.stopPropagation()}>
				<button
					onClick={() => { window.location.href = `/projects/${projectId}/claims/${claim.id}/review`; }}
					className="inline-flex items-center gap-1 text-xs font-medium text-ink-2 bg-transparent border-none cursor-pointer px-2 py-1 rounded-[var(--radius-md)] hover:text-ink transition-colors"
				>
					{isFinalised ? "View" : "Review"} <ChevronRight className="w-3 h-3" />
				</button>
				{isFinalised && claim.assessment_id && (
					<button
						disabled={claim.claim_number !== maxClaimNumber || revertMutation.isPending}
						onClick={() => {
							if (confirm("Revert this claim to draft? This will unlock the assessment for editing.")) {
								revertMutation.mutate();
							}
						}}
						className={cn(
							"text-[11px] px-2 py-[3px] rounded-[var(--radius-sm)] bg-paper-2 border border-line",
							claim.claim_number !== maxClaimNumber ? "text-ink-4 cursor-not-allowed" : "text-ink-3 cursor-pointer",
						)}
					>
						{revertMutation.isPending ? "Reverting\u2026" : "Revert"}
					</button>
				)}
				<button
					disabled={isFinalised}
					onClick={() => {
						if (confirm("Delete this claim and its assessment? This cannot be undone.")) {
							deleteMutation.mutate(claim.id);
						}
					}}
					title={isFinalised ? "Cannot delete a finalised claim" : "Delete claim"}
					className={cn(
						"w-[26px] h-[26px] rounded-[var(--radius-sm)] inline-flex items-center justify-center",
						isFinalised
							? "bg-transparent border border-line text-ink-4 cursor-not-allowed opacity-50"
							: "bg-err-tint border border-err/15 text-err cursor-pointer",
					)}
				>
					<Trash2 className="w-3 h-3" />
				</button>
			</div>
		</div>
	);
}

/* ── Retention tier row ─────────────────────────────────────── */
function RetentionTierRow({ tier, pct, cap, filled }: {
	tier: number; pct: string; cap: string; filled: boolean;
}) {
	return (
		<div className={cn("grid items-center gap-2 py-1.5", tier > 1 && "border-t border-dashed border-line")}
			style={{ gridTemplateColumns: "24px 1fr auto" }}>
			<span className={cn(
				"w-[18px] h-[18px] rounded-[3px] inline-flex items-center justify-center text-[10px] font-semibold font-mono",
				filled ? "bg-brand text-white" : "bg-paper-3 text-ink-3",
			)}>
				{tier}
			</span>
			<span className="text-xs text-ink-2">{cap}</span>
			<span className="font-mono-nums text-xs text-ink">{pct}</span>
		</div>
	);
}

/* ── Main page ──────────────────────────────────────────────── */
export default function ProjectDetail({ projectId }: { projectId: string }) {
	const queryClient = useQueryClient();
	const [uploadStatus, setUploadStatus] = useState<string | null>(null);
	const [harnessSessionId, setHarnessSessionId] = useState<string | null>(() => {
		const params = new URLSearchParams(window.location.search);
		return params.get("harness");
	});
	const [completedClaimId, setCompletedClaimId] = useState<string | null>(null);

	// Clean up ?harness= from URL after reading it
	useEffect(() => {
		const params = new URLSearchParams(window.location.search);
		if (params.has("harness")) {
			params.delete("harness");
			const newUrl = params.toString()
				? `${window.location.pathname}?${params}`
				: window.location.pathname;
			window.history.replaceState({}, "", newUrl);
		}
	}, []);

	const {
		data: project,
		isLoading: projectLoading,
		isError: projectIsError,
		error: projectError,
	} = useQuery<Project>({
		queryKey: ["project", projectId],
		queryFn: () => api.get(`/projects/${projectId}`).then((r) => r.data),
		// Don't retry a genuine 404 — only transient errors.
		retry: (count, err) =>
			(err as { response?: { status?: number } })?.response?.status !== 404 && count < 2,
	});

	const {
		data: claims = [],
		isLoading: claimsLoading,
		isError: claimsIsError,
	} = useQuery<ClaimListItem[]>({
		queryKey: ["claims", projectId],
		queryFn: () => api.get(`/projects/${projectId}/claims`).then((r) => r.data),
	});

	const uploadMutation = useMutation({
		mutationFn: async (file: File) => {
			const formData = new FormData();
			formData.append("file", file);
			return api.post(`/projects/${projectId}/claims/upload`, formData).then((r) => r.data);
		},
		onSuccess: (data) => {
			if (data.harness_session_id) {
				setHarnessSessionId(data.harness_session_id);
				setUploadStatus(null);
			}
		},
		onError: () => {
			setUploadStatus("Failed to upload/parse claim. Please try again.");
		},
	});

	const rerunMutation = useMutation({
		mutationFn: (sessionId: string) =>
			api.post(`/harness/sessions/${sessionId}/rerun`).then((r) => r.data),
		onSuccess: (data) => {
			if (data.harness_session_id) {
				setHarnessSessionId(data.harness_session_id);
				setUploadStatus(null);
			}
		},
		onError: () => {
			setUploadStatus("Re-run failed. Please try again.");
		},
	});

	const handleFileSelect = (file: File) => {
		setUploadStatus("Uploading and parsing...");
		uploadMutation.mutate(file);
	};

	const handleHarnessComplete = (claimId: string) => {
		setCompletedClaimId(claimId);
		queryClient.invalidateQueries({ queryKey: ["claims", projectId] });
	};

	const handleReviewClaim = () => {
		if (completedClaimId) {
			window.location.href = `/projects/${projectId}/claims/${completedClaimId}/review`;
		}
	};

	const handleHarnessError = (error: string) => {
		setUploadStatus(`Processing failed: ${error}`);
	};

	const hasDraftClaims = claimsLoading || claims.some((c) => c.assessment_status !== "finalised");
	const maxClaimNumber = claims.length > 0 ? Math.max(...claims.map((c) => c.claim_number)) : 0;
	const harnessActive = !!harnessSessionId;

	const breadcrumbs: Breadcrumb[] = [
		{ label: "Projects", href: "/" },
		...(project ? [{ label: project.name }] : []),
	];

	if (projectLoading) {
		return (
			<div className="min-h-screen bg-paper flex flex-col">
				<Nav breadcrumbs={breadcrumbs} />
				<div className="w-full px-8 py-7"><p className="text-ink-3">Loading project...</p></div>
			</div>
		);
	}
	if (projectIsError || !project) {
		const status = (projectError as { response?: { status?: number } } | null)?.response?.status;
		const notFound = status === 404;
		if (!notFound) console.error("Failed to load project", projectError);
		return (
			<div className="min-h-screen bg-paper flex flex-col">
				<Nav breadcrumbs={breadcrumbs} />
				<div className="w-full px-8 py-7">
					{notFound ? (
						<p className="text-ink-3">Project not found.</p>
					) : (
						<div className="text-ink-3">
							<p className="text-err">Failed to load project{status ? ` (HTTP ${status})` : ""}.</p>
							<button className="mt-2 underline" onClick={() => window.location.reload()}>Retry</button>
						</div>
					)}
				</div>
			</div>
		);
	}

	const retentionTiers = project.retention_tiers ?? [];
	const wbsCodes = (project.wbs_codes ?? []).filter((w) => w.level === "category").sort((a, b) => a.sort_order - b.sort_order);

	return (
		<div className="min-h-screen bg-paper flex flex-col">
			<Nav breadcrumbs={breadcrumbs} />
			<main className="w-full px-8 pt-7 pb-20">
				{/* Header */}
				<header className="pb-8 mb-7 border-b border-line">
					<a href="/" className="inline-flex items-center gap-1.5 text-xs text-ink-3 hover:text-ink mb-4 transition-colors no-underline">
						<ArrowLeft className="h-3.5 w-3.5" /> Back to Projects
					</a>

					<div className="grid gap-12 items-end" style={{ gridTemplateColumns: "1.6fr 1fr" }}>
						<div>
							{project.project_number && (
								<div className="eyebrow mb-3">Project {project.project_number}</div>
							)}
							<h1 className="font-display text-[42px] tracking-tight leading-[1.05] max-w-[720px]">
								{project.name}
							</h1>
							<div className="flex gap-7 mt-[18px] flex-wrap">
								<InlineMeta label="Client" value={project.client_name} />
								<InlineMeta label="Contractor" value={project.contractor_name} />
								<InlineMeta label="GST" value={`${(Number(project.gst_rate || 0) * 100).toFixed(0)}%`} />
								<InlineMeta label="Status" value={
									<Badge variant={project.status === "active" ? "approved" : "muted"}>
										{project.status === "active" ? "Active" : project.status || "Active"}
									</Badge>
								} />
							</div>
						</div>

						<div className="flex flex-col gap-4 items-end">
							<div className="flex gap-1.5">
								<Button variant="ghost" size="sm" onClick={() => (window.location.href = `/projects/${projectId}/edit`)}>
									<Pencil className="h-3.5 w-3.5" /> Edit
								</Button>
							</div>
							<div className="text-right">
								<div className="eyebrow mb-1">Contract sum</div>
								<div className="font-display text-[28px] tracking-tight">{fmt(project.contract_sum)}</div>
							</div>
						</div>
					</div>
				</header>

				{/* Body grid */}
				<div
					className="grid gap-8 transition-all duration-300"
					style={{
						gridTemplateColumns: harnessActive ? "minmax(0, 1fr) 380px" : "minmax(0, 1fr) 320px",
					}}
				>
					{/* Main column */}
					<div className="min-w-0">
						{/* Upload section */}
						<section className="mb-8">
							<SectionHead title="Upload progress claim" eyebrow="Reconciliation" />
							<p className="text-xs text-ink-3 mb-3.5 -mt-1">
								Validate totals, match variations against the contract, categorise line items into WBS, and flag exceptions.
							</p>

							<CompactDropzone
								onFileSelect={handleFileSelect}
								disabled={hasDraftClaims || harnessActive}
								isUploading={uploadMutation.isPending || harnessActive}
							/>
							{uploadStatus && !harnessActive && (
								<p className={cn("mt-2 text-xs", uploadMutation.isError ? "text-err" : "text-ok")}>
									{uploadStatus}
								</p>
							)}
						</section>

						{/* Claims table */}
						<section>
							<SectionHead
								title="Progress claims"
								eyebrow="History"
								right={<span className="text-xs text-ink-3">{claims.length} claim{claims.length !== 1 ? "s" : ""}</span>}
							/>
							{claimsLoading ? (
								<p className="text-xs text-ink-3">Loading claims...</p>
							) : claimsIsError ? (
								<p className="text-xs text-err">Failed to load claims. Refresh to retry.</p>
							) : claims.length === 0 ? (
								<p className="text-xs text-ink-3">No claims yet. Upload a contractor claim PDF to get started.</p>
							) : (
								<div className="overflow-hidden rounded-[var(--radius-lg)] border border-line bg-surface">
									{/* Table header */}
									<div
										className="grid gap-x-4 px-4 py-2.5 border-b border-line bg-paper-2 text-[10px] tracking-[0.08em] uppercase text-ink-3 font-medium"
										style={{ gridTemplateColumns: "70px 1fr 1fr 130px 110px 180px" }}
									>
										<div>#</div>
										<div>Period</div>
										<div>Payment due</div>
										<div className="text-right">Claimed</div>
										<div>Status</div>
										<div />
									</div>
									{claims.map((claim) => (
										<ClaimRow key={claim.id} claim={claim} projectId={projectId} maxClaimNumber={maxClaimNumber} />
									))}
								</div>
							)}
						</section>
					</div>

					{/* Side rail */}
					{harnessActive ? (
						<HarnessPanel
							key={harnessSessionId!}
							sessionId={harnessSessionId!}
							onComplete={handleHarnessComplete}
							onError={handleHarnessError}
							onClose={() => setHarnessSessionId(null)}
							onRestart={() => { setHarnessSessionId(null); setUploadStatus(null); }}
							onReview={handleReviewClaim}
							onRerun={() => harnessSessionId && rerunMutation.mutate(harnessSessionId)}
						/>
					) : (
						<aside className="flex flex-col gap-5">
							{/* Retention */}
							{retentionTiers.length > 0 && (
								<div className="p-[18px] rounded-[var(--radius-lg)] border border-line bg-surface">
									<div className="eyebrow mb-3">Retention held</div>
									<div className="flex flex-col gap-1.5">
										{retentionTiers
											.sort((a, b) => a.tier_order - b.tier_order)
											.map((t) => (
												<RetentionTierRow
													key={t.tier_order}
													tier={t.tier_order}
													pct={`${(Number(t.percentage) * 100).toFixed(2)}%`}
													cap={t.up_to_amount ? `up to ${fmt(t.up_to_amount)}` : "on remainder"}
													filled={true}
												/>
											))}
									</div>
								</div>
							)}

							{/* WBS quick view */}
							{wbsCodes.length > 0 && (
								<div className="p-[18px] rounded-[var(--radius-lg)] border border-line bg-surface">
									<div className="flex justify-between items-center mb-3">
										<div className="eyebrow">Work breakdown</div>
									</div>
									<div className="flex flex-col gap-1">
										{wbsCodes.slice(0, 7).map((w) => (
											<div key={w.id} className="flex justify-between text-xs">
												<span className="flex gap-2 items-center">
													<span className="font-mono-nums text-ink-4 text-[10px] w-[22px]">{w.code}</span>
													<span className="text-ink-2">{w.description}</span>
												</span>
												{w.contract_sum && (
													<span className="font-mono-nums text-ink-3">{fmt(w.contract_sum)}</span>
												)}
											</div>
										))}
										{wbsCodes.length > 7 && (
											<span className="text-[11px] text-ink-3 mt-1">+ {wbsCodes.length - 7} more categories</span>
										)}
									</div>
								</div>
							)}

							{/* Project config */}
							<details className="rounded-[var(--radius-lg)] border border-line bg-surface">
								<summary className="px-[18px] py-3.5 cursor-pointer text-xs font-medium text-ink-2">
									Project Configuration
								</summary>
								<div className="px-[18px] pb-[18px]">
									<div className="mt-2">
										<div className="eyebrow mb-2">WBS Structure</div>
										{wbsCodes.map((cat) => (
											<div key={cat.id} className="mb-2">
												<div className="text-xs font-medium text-ink">{cat.code} - {cat.description}</div>
												<div className="ml-4">
													{(project.wbs_codes ?? [])
														.filter((w) => w.parent_id === cat.id)
														.sort((a, b) => a.sort_order - b.sort_order)
														.map((sub) => (
															<div key={sub.id} className="text-[11px] text-ink-3 py-0.5">
																{sub.code} - {sub.description}
															</div>
														))}
												</div>
											</div>
										))}
									</div>
								</div>
							</details>
						</aside>
					)}
				</div>
			</main>
		</div>
	);
}
