import { useState } from "react";
import { useQuery, useQueryClient, useMutation } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { yupResolver } from "@hookform/resolvers/yup";
import * as yup from "yup";
import { Plus, Pencil, Lock, AlertTriangle } from "lucide-react";
import api from "@/api/client";
import Layout from "@/components/Layout";
import { PageHeader } from "@/components/page-header";
import { FormSection } from "@/components/form-section";
import { FormField } from "@/components/form-field";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import type { WBSCode, Project } from "@/types/domain";

const schema = yup.object({
	name: yup.string().required("Project name is required"),
	projectNumber: yup.string().default(""),
	clientName: yup.string().required("Client name is required"),
	clientContact: yup.string().default(""),
	contractorName: yup.string().required("Contractor name is required"),
	contractSum: yup.string().required("Contract sum is required"),
	gstRate: yup.string().default("0.15"),
	endClientName: yup.string().default(""),
	endClientRepresentative: yup.string().default(""),
	endClientAddress: yup.string().default(""),
	landlordSplitPct: yup.string().default(""),
	operatorSplitPct: yup.string().default(""),
	provisionalSumTotal: yup.string().default(""),
});

type FormValues = yup.InferType<typeof schema>;

export default function EditProject({ projectId }: { projectId: string }) {
	const { data: project, isLoading } = useQuery<Project>({
		queryKey: ["project", projectId],
		queryFn: () => api.get(`/projects/${projectId}`).then((r) => r.data),
	});

	if (isLoading) return <Layout><p>Loading project...</p></Layout>;
	if (!project) return <Layout><p>Project not found.</p></Layout>;

	return (
		<Layout>
			<div className="max-w-4xl mx-auto">
				<PageHeader
					title={`Edit: ${project.name}`}
					backHref={`/projects/${projectId}`}
					backLabel="Back to Project"
				/>
				<EditProjectForm project={project} projectId={projectId} />
			</div>
		</Layout>
	);
}

function EditProjectForm({ project, projectId }: { project: Project; projectId: string }) {
	const {
		register,
		handleSubmit,
		watch,
		setValue,
		formState: { errors },
	} = useForm<FormValues>({
		resolver: yupResolver(schema),
		defaultValues: {
			name: project.name || "",
			projectNumber: project.project_number || "",
			clientName: project.client_name || "",
			clientContact: project.client_contact || "",
			contractorName: project.contractor_name || "",
			contractSum: project.contract_sum || "",
			gstRate: project.gst_rate || "0.15",
			endClientName: project.end_client_name || "",
			endClientRepresentative: project.end_client_representative || "",
			endClientAddress: project.end_client_address || "",
			landlordSplitPct: project.landlord_split_pct
				? String(Number(project.landlord_split_pct) * 100)
				: "",
			operatorSplitPct: project.operator_split_pct
				? String(Number(project.operator_split_pct) * 100)
				: "",
			provisionalSumTotal: project.provisional_sum_total || "",
		},
	});

	const landlordSplitPct = watch("landlordSplitPct");
	const operatorSplitPct = watch("operatorSplitPct");

	const updateProject = useMutation({
		mutationFn: (data: Record<string, string | number | null>) =>
			api.patch(`/projects/${projectId}`, data).then((r) => r.data),
		onSuccess: () => {},
	});

	const onSubmit = (form: FormValues) => {
		const data: Record<string, string | number | null> = {};
		for (const [key, value] of Object.entries(form)) {
			const snakeKey = key.replace(/[A-Z]/g, (m) => `_${m.toLowerCase()}`);
			if (["landlord_split_pct", "operator_split_pct"].includes(snakeKey)) {
				data[snakeKey] = value ? Number(value) / 100 : null;
			} else if (["contract_sum", "gst_rate", "provisional_sum_total"].includes(snakeKey)) {
				data[snakeKey] = value ? Number(value) : null;
			} else {
				data[snakeKey] = value || null;
			}
		}
		updateProject.mutate(data);
	};

	const splitTotal =
		landlordSplitPct && operatorSplitPct
			? Number(landlordSplitPct) + Number(operatorSplitPct)
			: null;

	const fmt = (v: string | null | undefined) =>
		v ? `$${Number(v).toLocaleString(undefined, { minimumFractionDigits: 2 })}` : "-";

	return (
		<div className="space-y-6">
			<form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
				<FormSection title="Project Details">
					<FormField label="Project Name" required error={errors.name}>
						<Input {...register("name")} />
					</FormField>
					<FormField label="Project Number" error={errors.projectNumber}>
						<Input {...register("projectNumber")} />
					</FormField>
					<FormField label="Client Name" required error={errors.clientName}>
						<Input {...register("clientName")} />
					</FormField>
					<FormField label="Client Contact" error={errors.clientContact}>
						<Input {...register("clientContact")} />
					</FormField>
					<FormField label="Contractor Name" required error={errors.contractorName}>
						<Input {...register("contractorName")} />
					</FormField>
					<FormField label="Contract Sum" required error={errors.contractSum}>
						<Input type="number" step="0.01" {...register("contractSum")} />
					</FormField>
					<FormField label="GST Rate" error={errors.gstRate}>
						<Input type="number" step="0.01" {...register("gstRate")} />
					</FormField>
					<FormField label="Provisional Sum Total" error={errors.provisionalSumTotal}>
						<Input type="number" step="0.01" {...register("provisionalSumTotal")} />
					</FormField>
				</FormSection>

				<FormSection title="End Client / Principal Details">
					<FormField label="End Client Name" error={errors.endClientName}>
						<Input {...register("endClientName")} />
					</FormField>
					<FormField label="End Client Representative" error={errors.endClientRepresentative}>
						<Input {...register("endClientRepresentative")} />
					</FormField>
					<FormField label="End Client Address" className="col-span-2" error={errors.endClientAddress}>
						<Textarea {...register("endClientAddress")} rows={4} />
					</FormField>
				</FormSection>

				<FormSection title="Landlord / Operator Split" description="Leave blank if not applicable. Values must total 100%." columns={2}>
					<FormField label="Landlord %" error={errors.landlordSplitPct}>
						<Input
							type="number" step="0.01" min="0" max="100"
							{...register("landlordSplitPct", {
								onChange: (e) => {
									const val = e.target.value;
									setValue("operatorSplitPct", val ? (100 - Number(val)).toFixed(2) : "");
								},
							})}
						/>
					</FormField>
					<FormField label="Operator %" error={errors.operatorSplitPct}>
						<Input
							type="number" step="0.01" min="0" max="100"
							{...register("operatorSplitPct", {
								onChange: (e) => {
									const val = e.target.value;
									setValue("landlordSplitPct", val ? (100 - Number(val)).toFixed(2) : "");
								},
							})}
						/>
					</FormField>
					{splitTotal !== null && (
						<div className="col-span-2">
							{Math.abs(splitTotal - 100) < 0.01 ? (
								<span className="text-sm font-medium text-ok">Total: 100%</span>
							) : (
								<span className="text-sm font-medium text-destructive">
									Total: {splitTotal.toFixed(2)}% (must be 100%)
								</span>
							)}
						</div>
					)}
				</FormSection>

				<div className="flex gap-4">
					<Button type="submit" disabled={updateProject.isPending}>
						{updateProject.isPending ? "Saving..." : "Save Project Details"}
					</Button>
					{updateProject.isSuccess && (
						<span className="text-sm text-ok self-center">Saved successfully</span>
					)}
				</div>

				{updateProject.isError && (
					<Alert variant="error">
						<AlertDescription>Failed to save project details.</AlertDescription>
					</Alert>
				)}
			</form>

			<WBSSection projectId={projectId} wbsCodes={project.wbs_codes ?? []} />

			{/* Retention Tiers (read-only) */}
			<FormSection title="Retention Tiers" columns={1}>
				{(project.retention_tiers ?? []).length > 0 ? (
					<div className="space-y-1">
						{(project.retention_tiers ?? []).map((t) => (
							<div key={t.id} className="text-sm text-muted-foreground">
								Tier {t.tier_order}: {(Number(t.percentage) * 100).toFixed(2)}%
								{t.up_to_amount ? ` up to ${fmt(t.up_to_amount)}` : " on remainder"}
							</div>
						))}
					</div>
				) : (
					<p className="text-sm text-muted-foreground">No retention tiers configured.</p>
				)}
			</FormSection>
		</div>
	);
}

function WBSSection({ projectId, wbsCodes: initialWbsCodes }: { projectId: string; wbsCodes: WBSCode[] }) {
	const queryClient = useQueryClient();
	const [editingId, setEditingId] = useState<string | null>(null);
	const [editForm, setEditForm] = useState<{ code: string; description: string; contract_sum: string }>({
		code: "", description: "", contract_sum: "",
	});

	const [newLevel, setNewLevel] = useState<"category" | "subcategory">("subcategory");
	const [newCode, setNewCode] = useState("");
	const [newDesc, setNewDesc] = useState("");
	const [newParent, setNewParent] = useState("");
	const [newContractSum, setNewContractSum] = useState("");

	const [saveStatus, setSaveStatus] = useState<Record<string, "saving" | "saved" | "error">>({});

	const wbsCodes = initialWbsCodes;
	const categories = wbsCodes.filter((w) => w.level === "category").sort((a, b) => a.sort_order - b.sort_order);

	const updateWbs = useMutation({
		mutationFn: ({ wbsId, data }: { wbsId: string; data: Record<string, unknown> }) =>
			api.patch(`/projects/${projectId}/wbs/${wbsId}`, data).then((r) => r.data),
		onMutate: ({ wbsId }) => setSaveStatus((s) => ({ ...s, [wbsId]: "saving" })),
		onSuccess: (_data, { wbsId }) => {
			setSaveStatus((s) => ({ ...s, [wbsId]: "saved" }));
			setEditingId(null);
			queryClient.invalidateQueries({ queryKey: ["project", projectId] });
			setTimeout(() => setSaveStatus((s) => { const next = { ...s }; delete next[wbsId]; return next; }), 2000);
		},
		onError: (_err, { wbsId }) => setSaveStatus((s) => ({ ...s, [wbsId]: "error" })),
	});

	const createWbs = useMutation({
		mutationFn: (data: Record<string, unknown>) =>
			api.post(`/projects/${projectId}/wbs`, data).then((r) => r.data),
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["project", projectId] });
			setNewCode("");
			setNewDesc("");
			setNewContractSum("");
		},
	});

	const startEdit = (wbs: WBSCode) => {
		setEditingId(wbs.id);
		setEditForm({
			code: wbs.code,
			description: wbs.description,
			contract_sum: wbs.contract_sum ?? "",
		});
	};

	const saveEdit = (wbs: WBSCode) => {
		const data: Record<string, unknown> = {};
		if (editForm.description !== wbs.description) data.description = editForm.description;
		if (editForm.contract_sum !== (wbs.contract_sum ?? "")) {
			data.contract_sum = editForm.contract_sum ? Number(editForm.contract_sum) : null;
		}
		if (!wbs.in_use && editForm.code !== wbs.code) data.code = editForm.code;
		if (Object.keys(data).length === 0) {
			setEditingId(null);
			return;
		}
		updateWbs.mutate({ wbsId: wbs.id, data });
	};

	const addWbsCode = () => {
		if (!newCode || !newDesc) return;
		const parentCategory = categories.find((c) => c.id === newParent);
		createWbs.mutate({
			code: newCode,
			description: newDesc,
			level: newLevel,
			parent_id: newLevel === "subcategory" ? newParent || null : null,
			sort_order: newLevel === "category"
				? (categories.length + 1) * 10
				: (parentCategory ? wbsCodes.filter((w) => w.parent_id === parentCategory.id).length + 1 : 0),
			contract_sum: newContractSum ? Number(newContractSum) : null,
		});
	};

	const fmt = (v: string | null | undefined) =>
		v ? `$${Number(v).toLocaleString(undefined, { minimumFractionDigits: 2 })}` : "-";

	const renderWbsRow = (wbs: WBSCode, isSubcategory: boolean) => {
		const isEditing = editingId === wbs.id;

		if (isEditing) {
			return (
				<div key={wbs.id} className={`flex flex-wrap items-center gap-2 px-3 py-2 ${isSubcategory ? "bg-paper-2" : "bg-brand-tint"} rounded`}>
					{wbs.in_use ? (
						<Badge variant="info" className="font-mono">{wbs.code}</Badge>
					) : (
						<Input
							value={editForm.code}
							onChange={(e) => setEditForm((f) => ({ ...f, code: e.target.value }))}
							className="w-24"
						/>
					)}
					<div className="flex-1 min-w-40">
						<Input
							value={editForm.description}
							onChange={(e) => setEditForm((f) => ({ ...f, description: e.target.value }))}
						/>
						{wbs.in_use && (
							<p className="text-xs text-amber-600 mt-1 flex items-center gap-1">
								<AlertTriangle className="h-3 w-3" />
								Changing the description may affect AI categorisation matching
							</p>
						)}
					</div>
					<Input
						type="number"
						step="0.01"
						value={editForm.contract_sum}
						onChange={(e) => setEditForm((f) => ({ ...f, contract_sum: e.target.value }))}
						className="w-36"
						placeholder="0.00"
					/>
					<Button type="button" size="xs" onClick={() => saveEdit(wbs)} disabled={saveStatus[wbs.id] === "saving"}>
						{saveStatus[wbs.id] === "saving" ? "Saving..." : "Save"}
					</Button>
					<Button type="button" variant="ghost" size="xs" onClick={() => setEditingId(null)}>
						Cancel
					</Button>
				</div>
			);
		}

		return (
			<div key={wbs.id} className={`flex items-center gap-2 px-3 py-2 ${isSubcategory ? "bg-paper-2" : "bg-brand-tint"} rounded`}>
				<Badge variant={isSubcategory ? "default" : "info"} className="font-mono">{wbs.code}</Badge>
				<span className={`text-sm ${isSubcategory ? "" : "font-semibold text-brand"}`}>{wbs.description}</span>
				{wbs.in_use && (
					<span title="In use by claims - code locked">
						<Lock className="h-3 w-3 text-muted-foreground" />
					</span>
				)}
				<div className="ml-auto flex items-center gap-2">
					{isSubcategory && (
						<span className="font-mono text-muted-foreground text-sm w-36 text-left">{fmt(wbs.contract_sum)}</span>
					)}
					{saveStatus[wbs.id] === "saved" && <span className="text-xs text-ok">Saved</span>}
					{saveStatus[wbs.id] === "error" && <span className="text-xs text-destructive">Error</span>}
					<Button type="button" variant="ghost" size="icon-sm" onClick={() => startEdit(wbs)} title="Edit WBS code">
						<Pencil className="h-3.5 w-3.5" />
					</Button>
				</div>
			</div>
		);
	};

	return (
		<FormSection title="WBS Codes" columns={1}>
			{categories.length > 0 && (
				<div className="space-y-1 mb-2">
					{categories.map((cat) => {
						const subs = wbsCodes
							.filter((w) => w.parent_id === cat.id)
							.sort((a, b) => a.sort_order - b.sort_order);
						const catTotal = subs.reduce((sum, s) => sum + Number(s.contract_sum ?? 0), 0);

						return (
							<div key={cat.id}>
								{renderWbsRow(cat, false)}
								<div className="ml-6 space-y-0.5">
									{subs.map((sub) => renderWbsRow(sub, true))}
									<div className="flex items-center px-3 py-1.5 border-t border-line text-sm font-semibold">
										<span className="text-ink-2">{cat.description} Total</span>
										<div className="ml-auto w-36 shrink-0">
											<span className="font-mono text-ink-1">
												${catTotal.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
											</span>
										</div>
										<div className="ml-2 w-7 shrink-0" />
									</div>
								</div>
							</div>
						);
					})}

					<div className="flex items-center px-3 py-2 mt-2 border-t-2 border-blue-900 text-sm font-bold">
						<span className="text-blue-900">Overall Total</span>
						<div className="ml-auto w-36 shrink-0">
							<span className="font-mono text-blue-900">
								${wbsCodes
									.filter((w) => w.level === "subcategory")
									.reduce((sum, s) => sum + Number(s.contract_sum ?? 0), 0)
									.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
							</span>
						</div>
						<div className="ml-2 w-7 shrink-0" />
					</div>
				</div>
			)}

			<div className="flex flex-wrap gap-2 items-end">
				<div className="flex flex-col gap-1">
					<label className="text-xs text-muted-foreground">Level</label>
					<Select value={newLevel} onChange={(e) => setNewLevel(e.target.value as "category" | "subcategory")} className="w-32">
						<option value="category">Category</option>
						<option value="subcategory">Subcategory</option>
					</Select>
				</div>

				<div className="flex flex-col gap-1">
					<label className="text-xs text-muted-foreground">Code</label>
					<Input value={newCode} onChange={(e) => setNewCode(e.target.value)} className="w-24" placeholder="PG-01" />
				</div>

				<div className="flex flex-col gap-1 flex-1 min-w-40">
					<label className="text-xs text-muted-foreground">Description</label>
					<Input value={newDesc} onChange={(e) => setNewDesc(e.target.value)} placeholder="Description" />
				</div>

				{newLevel === "subcategory" && (
					<div className="flex flex-col gap-1">
						<label className="text-xs text-muted-foreground">Parent</label>
						<Select value={newParent} onChange={(e) => setNewParent(e.target.value)} className="w-48">
							<option value="">Select parent...</option>
							{categories.map((c) => (
								<option key={c.id} value={c.id}>
									{c.code} - {c.description}
								</option>
							))}
						</Select>
					</div>
				)}

				<div className="flex flex-col gap-1">
					<label className="text-xs text-muted-foreground">Contract Sum</label>
					<Input
						type="number" step="0.01"
						value={newContractSum}
						onChange={(e) => setNewContractSum(e.target.value)}
						className="w-32" placeholder="0.00"
					/>
				</div>

				<Button type="button" onClick={addWbsCode} size="md" disabled={createWbs.isPending}>
					<Plus className="h-4 w-4" />
					{createWbs.isPending ? "Adding..." : "Add"}
				</Button>
			</div>

			{createWbs.isError && (
				<Alert variant="error">
					<AlertDescription>Failed to add WBS code. Check that the code is unique.</AlertDescription>
				</Alert>
			)}
		</FormSection>
	);
}
