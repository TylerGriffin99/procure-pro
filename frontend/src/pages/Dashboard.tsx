import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/api/client";
import Layout from "@/components/Layout";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Plus, ChevronRight, Trash2, Search, SlidersHorizontal } from "lucide-react";
import type { Project } from "@/types/domain";

type SortMode = "recent" | "value" | "az";

export default function Dashboard() {
	const queryClient = useQueryClient();
	const { data: projects = [], isLoading } = useQuery<Project[]>({
		queryKey: ["projects"],
		queryFn: () => api.get("/projects").then((r) => r.data),
	});

	const deleteProject = useMutation({
		mutationFn: (projectId: string) => api.delete(`/projects/${projectId}`),
		onSuccess: () => queryClient.invalidateQueries({ queryKey: ["projects"] }),
	});

	const [search, setSearch] = useState("");
	const [sort, setSort] = useState<SortMode>("recent");

	const activeProjects = projects.filter((p) => p.status !== "closeout").length;
	const totalContract = projects.reduce((s, p) => s + Number(p.contract_sum || 0), 0);

	const filtered = useMemo(() => {
		let list = projects;
		if (search.trim()) {
			const q = search.toLowerCase();
			list = list.filter(
				(p) =>
					p.name.toLowerCase().includes(q) ||
					p.client_name.toLowerCase().includes(q) ||
					p.contractor_name.toLowerCase().includes(q) ||
					(p.project_number && p.project_number.toLowerCase().includes(q))
			);
		}
		const sorted = [...list];
		switch (sort) {
			case "value":
				sorted.sort((a, b) => Number(b.contract_sum || 0) - Number(a.contract_sum || 0));
				break;
			case "az":
				sorted.sort((a, b) => a.name.localeCompare(b.name));
				break;
			default:
				break;
		}
		return sorted;
	}, [projects, search, sort]);

	const fmtCompact = (n: number) => {
		if (n >= 1_000_000) return "$" + (n / 1_000_000).toFixed(2) + "M";
		if (n >= 1_000) return "$" + (n / 1_000).toFixed(0) + "k";
		return "$" + n.toFixed(0);
	};

	return (
		<Layout breadcrumbs={[{ label: "Projects" }]}>
			{/* Page header */}
			<header className="flex items-start justify-between gap-6 pb-6 mb-8">
				<div className="min-w-0 flex-1">
					<div className="eyebrow mb-2">Workspace</div>
					<h1 className="font-display text-[40px] leading-tight tracking-tight text-ink">
						Projects
					</h1>
					<p className="mt-2 text-[13px] text-ink-3">
						{activeProjects} active{" "}
						{projects.length > 0 && (
							<>&middot; {fmtCompact(totalContract)} under review</>
						)}
					</p>
				</div>
				<div className="flex items-center gap-2 shrink-0 pt-2">
					<Button variant="outline" size="md">
						<SlidersHorizontal className="h-3.5 w-3.5" />
						Filter
					</Button>
					<a href="/projects/new">
						<Button variant="primary" size="md">
							<Plus className="h-3.5 w-3.5" />
							New project
						</Button>
					</a>
				</div>
			</header>

			{/* Headline metrics */}
			<section className="grid grid-cols-4 mb-8 border border-line rounded-[var(--radius-lg)] bg-surface overflow-hidden">
				<MetricCell label="Contract value under review">
					<span className="font-display text-[38px] tracking-tight leading-none">
						{fmtCompact(totalContract)}
					</span>
				</MetricCell>
				<MetricCell label="Active projects" border>
					<span className="font-display text-[38px] tracking-tight leading-none">
						{activeProjects}
					</span>
				</MetricCell>
				<MetricCell label="Claims processed" border>
					<span className="font-display text-[38px] tracking-tight leading-none">
						{/* Will show real count when claims endpoint returns aggregate */}
						&mdash;
					</span>
				</MetricCell>
				<MetricCell label="Open flags" border>
					<span className="font-display text-[38px] tracking-tight leading-none">
						&mdash;
					</span>
				</MetricCell>
			</section>

			{/* Search + sort */}
			<div className="flex items-center justify-between gap-4 mb-5">
				<div className="relative w-80">
					<Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-ink-4" />
					<Input
						value={search}
						onChange={(e) => setSearch(e.target.value)}
						placeholder="Search projects, contractors, clients..."
						className="pl-9 h-[34px] text-[13px]"
					/>
				</div>
				<div className="flex items-center gap-0.5 border border-line rounded-[var(--radius-md)] bg-surface p-0.5">
					{(["recent", "value", "az"] as SortMode[]).map((mode) => (
						<button
							key={mode}
							onClick={() => setSort(mode)}
							className={`px-2.5 py-1 text-xs font-medium rounded-[var(--radius-sm)] transition-colors ${
								sort === mode
									? "bg-paper-2 text-ink"
									: "text-ink-3 hover:text-ink-2"
							}`}
						>
							{mode === "recent"
								? "Recent"
								: mode === "value"
									? "Value"
									: "A\u2192Z"}
						</button>
					))}
				</div>
			</div>

			{/* Project table */}
			{isLoading ? (
				<p className="text-ink-3">Loading...</p>
			) : projects.length === 0 ? (
				<p className="text-ink-3">No projects yet. Create your first project to get started.</p>
			) : (
				<div className="border border-line rounded-[var(--radius-lg)] bg-surface overflow-hidden">
					{/* Header */}
					<div
						className="grid gap-x-4 px-5 py-2.5 border-b border-line bg-paper-2 eyebrow"
						style={{
							gridTemplateColumns:
								"minmax(0, 2.4fr) 1.2fr 1.2fr 80px 110px 130px 44px",
						}}
					>
						<div>Project</div>
						<div>Client</div>
						<div>Contractor</div>
						<div className="text-center">Claims</div>
						<div className="text-right">Contract</div>
						<div>Progress</div>
						<div />
					</div>

					{/* Rows */}
					{filtered.map((p) => (
						<ProjectRow
							key={p.id}
							p={p}
							onDelete={() => {
								if (confirm(`Delete project "${p.name}" and all its data?`)) {
									deleteProject.mutate(p.id);
								}
							}}
						/>
					))}
				</div>
			)}
		</Layout>
	);
}

function MetricCell({
	label,
	children,
	border,
	highlight,
}: {
	label: string;
	children: React.ReactNode;
	border?: boolean;
	highlight?: boolean;
}) {
	return (
		<div
			className={`py-[22px] px-6 ${border ? "border-l border-line" : ""} ${
				highlight ? "bg-warn-tint" : ""
			}`}
		>
			<div className="eyebrow mb-3">{label}</div>
			<div className="text-ink">{children}</div>
		</div>
	);
}

function ProjectRow({
	p,
	onDelete,
}: {
	p: Project;
	onDelete: () => void;
}) {
	const fmtCompact = (n: string | number) => {
		const num = Number(n);
		if (num >= 1_000_000) return "$" + (num / 1_000_000).toFixed(1) + "M";
		if (num >= 1_000) return "$" + (num / 1_000).toFixed(0) + "k";
		return "$" + num.toFixed(0);
	};

	return (
		<div
			className="grid gap-x-4 items-center px-5 py-3.5 border-b border-line last:border-b-0 cursor-pointer hover:bg-paper-2 transition-colors"
			style={{
				gridTemplateColumns:
					"minmax(0, 2.4fr) 1.2fr 1.2fr 80px 110px 130px 44px",
			}}
			onClick={() => (window.location.href = `/projects/${p.id}`)}
		>
			{/* Project name + badges */}
			<div className="min-w-0">
				<div className="flex items-center gap-2.5 flex-wrap">
					<span className="text-[13px] font-semibold text-ink truncate">
						{p.name}
					</span>
					{p.status === "closeout" && (
						<Badge variant="outline" className="text-[10px]">
							Closeout
						</Badge>
					)}
				</div>
				{p.project_number && (
					<div className="text-[11px] text-ink-4 mt-0.5 font-mono-nums">
						{p.project_number}
					</div>
				)}
			</div>

			{/* Client */}
			<div className="text-[13px] text-ink-2 truncate">{p.client_name}</div>

			{/* Contractor */}
			<div className="text-[13px] text-ink-2 truncate">{p.contractor_name}</div>

			{/* Claims count */}
			<div className="font-mono-nums text-center text-[13px] text-ink-2">
				&mdash;
			</div>

			{/* Contract value */}
			<div className="font-mono-nums text-right text-[13px] text-ink">
				{fmtCompact(p.contract_sum)}
			</div>

			{/* Progress */}
			<div className="flex items-center gap-2">
				<div className="flex-1 h-[3px] bg-paper-3 rounded-full overflow-hidden">
					{/* placeholder bar */}
				</div>
				<span className="text-[11px] text-ink-4 font-mono-nums">&mdash;</span>
			</div>

			{/* Actions */}
			<div className="flex items-center justify-end gap-1.5">
				<button
					onClick={(e) => {
						e.stopPropagation();
						onDelete();
					}}
					className="text-ink-4 hover:text-err transition-colors p-0.5"
					title="Delete project"
				>
					<Trash2 className="h-3.5 w-3.5" />
				</button>
				<ChevronRight className="h-3.5 w-3.5 text-ink-4" />
			</div>
		</div>
	);
}
