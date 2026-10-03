import { useState, useRef, useEffect } from "react";
import { useForm } from "react-hook-form";
import { yupResolver } from "@hookform/resolvers/yup";
import * as yup from "yup";
import { useMutation } from "@tanstack/react-query";
import { Plus, X, Check, Upload } from "lucide-react";
import api from "@/api/client";
import { useAuth } from "@/hooks/useAuth";
import Layout from "@/components/Layout";
import { FormField } from "@/components/form-field";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select } from "@/components/ui/select";
import { Button, buttonVariants } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Card, CardContent } from "@/components/ui/card";

import type { RetentionTier } from "@/types/domain";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface WBSEntry {
	code: string;
	description: string;
	level: "category" | "subcategory";
	parent_code: string | null;
	sort_order: number;
	contract_sum?: number | null;
}

// ---------------------------------------------------------------------------
// Template data
// ---------------------------------------------------------------------------

const GILMOURS_WBS: WBSEntry[] = [
	// Demolition
	{ code: "DM", description: "Demolition", level: "category", parent_code: null, sort_order: 0 },
	{ code: "DM-01", description: "Demolition existing structure", level: "subcategory", parent_code: "DM", sort_order: 1, contract_sum: 120480.00 },
	{ code: "DM-02", description: "Removal and reinstatement of PIR", level: "subcategory", parent_code: "DM", sort_order: 2, contract_sum: 27944.00 },
	{ code: "DM-03", description: "Removal and reinstatement of chiller units", level: "subcategory", parent_code: "DM", sort_order: 3, contract_sum: 6490.25 },
	{ code: "DM-04", description: "Temp lighting to birdcage - setup", level: "subcategory", parent_code: "DM", sort_order: 4, contract_sum: 14297.75 },
	{ code: "DM-05", description: "Bulk Excavation", level: "subcategory", parent_code: "DM", sort_order: 5, contract_sum: 64504.78 },
	// Drainage
	{ code: "DR", description: "Drainage", level: "category", parent_code: null, sort_order: 10 },
	{ code: "DR-01", description: "Relocation of stormwater, sewer and water", level: "subcategory", parent_code: "DR", sort_order: 11, contract_sum: 156773.92 },
	// Car Park & Yard
	{ code: "CP", description: "Car Park & Yard", level: "category", parent_code: null, sort_order: 20 },
	{ code: "CP-01", description: "Concrete driveway", level: "subcategory", parent_code: "CP", sort_order: 21, contract_sum: 30800.00 },
	{ code: "CP-02", description: "Asphalt prep and hotmix", level: "subcategory", parent_code: "CP", sort_order: 22, contract_sum: 24860.00 },
	// Substructure
	{ code: "SS", description: "Substructure", level: "category", parent_code: null, sort_order: 30 },
	{ code: "SS-01", description: "General substructure works", level: "subcategory", parent_code: "SS", sort_order: 31, contract_sum: 256840.78 },
	{ code: "SS-02", description: "Pile drilling", level: "subcategory", parent_code: "SS", sort_order: 32, contract_sum: 62257.00 },
	{ code: "SS-03", description: "Reinforcing steel", level: "subcategory", parent_code: "SS", sort_order: 33, contract_sum: 104865.35 },
	// Frame
	{ code: "FR", description: "Frame", level: "category", parent_code: null, sort_order: 40 },
	{ code: "FR-01", description: "Steel", level: "subcategory", parent_code: "FR", sort_order: 41, contract_sum: 1184000.00 },
	// External Walls and Exterior Finishes
	{ code: "EW", description: "External Walls and Exterior Finishes", level: "category", parent_code: null, sort_order: 50 },
	{ code: "EW-01", description: "Works to external walls", level: "subcategory", parent_code: "EW", sort_order: 51, contract_sum: 47537.47 },
	// Internal Partitions & Doors
	{ code: "IP", description: "Internal Partitions & Doors", level: "category", parent_code: null, sort_order: 60 },
	{ code: "IP-01", description: "Redecoration", level: "subcategory", parent_code: "IP", sort_order: 61, contract_sum: 18344.00 },
	// Ceiling Finishes
	{ code: "CF", description: "Ceiling Finishes", level: "category", parent_code: null, sort_order: 70 },
	{ code: "CF-01", description: "Suspended ceilings", level: "subcategory", parent_code: "CF", sort_order: 71, contract_sum: 68026.70 },
	// HVAC
	{ code: "HV", description: "HVAC", level: "category", parent_code: null, sort_order: 80 },
	{ code: "HV-01", description: "Removal and reinstatement of aircon units", level: "subcategory", parent_code: "HV", sort_order: 81, contract_sum: 14298.00 },
	// Fire Protection
	{ code: "FP", description: "Fire Protection", level: "category", parent_code: null, sort_order: 90 },
	{ code: "FP-01", description: "Fire Sprinkler Alteration", level: "subcategory", parent_code: "FP", sort_order: 91, contract_sum: 200000.00 },
	// Preliminaries
	{ code: "PL", description: "Preliminaries", level: "category", parent_code: null, sort_order: 100 },
	{ code: "PL-01", description: "General", level: "subcategory", parent_code: "PL", sort_order: 101, contract_sum: 250000.00 },
	{ code: "PL-02", description: "Temp fencing and hoarding", level: "subcategory", parent_code: "PL", sort_order: 102, contract_sum: 40160.00 },
	{ code: "PL-03", description: "Scaffolding and Encapsulation", level: "subcategory", parent_code: "PL", sort_order: 103, contract_sum: 893343.50 },
	{ code: "PL-04", description: "Ply barriers to birdcage", level: "subcategory", parent_code: "PL", sort_order: 104, contract_sum: 22500.00 },
	{ code: "PL-05", description: "Temp ablution blocks", level: "subcategory", parent_code: "PL", sort_order: 105, contract_sum: 54865.97 },
	{ code: "PL-06", description: "Temp office", level: "subcategory", parent_code: "PL", sort_order: 106, contract_sum: 37607.20 },
	{ code: "PL-07", description: "Temp driveway", level: "subcategory", parent_code: "PL", sort_order: 107, contract_sum: 50565.00 },
	{ code: "PL-08", description: "Temp lighting to birdcage - setup", level: "subcategory", parent_code: "PL", sort_order: 108, contract_sum: 21131.25 },
	// Margin
	{ code: "MG", description: "Margin", level: "category", parent_code: null, sort_order: 110 },
	{ code: "MG-01", description: "General Margin", level: "subcategory", parent_code: "MG", sort_order: 111, contract_sum: 250000.00 },
	// Provisional Sums
	{ code: "PS", description: "Provisional Sums", level: "category", parent_code: null, sort_order: 120 },
	{ code: "PS-01", description: "Provisional Sums", level: "subcategory", parent_code: "PS", sort_order: 121, contract_sum: 150000.00 },
	// Variations
	{ code: "VR", description: "Variations", level: "category", parent_code: null, sort_order: 130 },
	{ code: "VR-01", description: "Variations", level: "subcategory", parent_code: "VR", sort_order: 131, contract_sum: 0 },
];

const GILMOURS_RETENTION: RetentionTier[] = [
	{ tier_order: 1, percentage: "0.10", up_to_amount: "200000" },
	{ tier_order: 2, percentage: "0.05", up_to_amount: "800000" },
	{ tier_order: 3, percentage: "0.0175", up_to_amount: "" },
];

// ---------------------------------------------------------------------------
// Sections
// ---------------------------------------------------------------------------

const SECTIONS = [
	{ id: "contract", label: "Contract details" },
	{ id: "principal", label: "Principal / end-client" },
	{ id: "landlord", label: "Landlord / operator split" },
	{ id: "wbs", label: "WBS structure" },
	{ id: "retention", label: "Retention tiers" },
] as const;

type SectionId = (typeof SECTIONS)[number]["id"];

// ---------------------------------------------------------------------------
// Form schema
// ---------------------------------------------------------------------------

const schema = yup.object({
	name: yup.string().required("Project name is required"),
	projectNumber: yup.string().default(""),
	clientName: yup.string().required("Client name is required"),
	clientContact: yup.string().default(""),
	contractorName: yup.string().required("Contractor name is required"),
	contractSum: yup.string().required("Contract sum is required"),
	gstRate: yup.string().default("0.15"),
	siteLocation: yup.string().default(""),
	endClientName: yup.string().default(""),
	endClientRepresentative: yup.string().default(""),
	endClientAddress: yup.string().default(""),
	landlordSplitPct: yup.string().default(""),
	operatorSplitPct: yup.string().default(""),
	provisionalSumTotal: yup.string().default(""),
});

type FormValues = yup.InferType<typeof schema>;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function CreateProject() {
	const { user } = useAuth();
	const [wbsCodes, setWbsCodes] = useState<WBSEntry[]>([]);
	const [retentionTiers, setRetentionTiers] = useState<RetentionTier[]>([]);
	const [activeSection, setActiveSection] = useState<SectionId>("contract");
	const [showWbsAdd, setShowWbsAdd] = useState(false);
	const [showRetentionAdd, setShowRetentionAdd] = useState(false);

	// WBS add form fields
	const [newWbsCode, setNewWbsCode] = useState("");
	const [newWbsDesc, setNewWbsDesc] = useState("");
	const [newWbsLevel, setNewWbsLevel] = useState<"category" | "subcategory">("subcategory");
	const [newWbsParent, setNewWbsParent] = useState("");
	const [newWbsContractSum, setNewWbsContractSum] = useState("");

	// Retention add form fields
	const [newRetPct, setNewRetPct] = useState("");
	const [newRetAmt, setNewRetAmt] = useState("");

	// Section refs for scroll tracking
	const sectionRefs = useRef<Record<string, HTMLElement | null>>({});

	const {
		register,
		handleSubmit,
		reset,
		watch,
		setValue,
		formState: { errors },
	} = useForm<FormValues>({
		resolver: yupResolver(schema),
		defaultValues: {
			name: "",
			projectNumber: "",
			clientName: "",
			clientContact: "",
			contractorName: "",
			contractSum: "",
			gstRate: "0.15",
			siteLocation: "",
			endClientName: "",
			endClientRepresentative: "",
			endClientAddress: "",
			landlordSplitPct: "",
			operatorSplitPct: "",
			provisionalSumTotal: "",
		},
	});

	const landlordSplitPct = watch("landlordSplitPct");
	const operatorSplitPct = watch("operatorSplitPct");

	// Track which section is visible via IntersectionObserver
	useEffect(() => {
		const observers: IntersectionObserver[] = [];
		const entries = new Map<string, boolean>();

		SECTIONS.forEach(({ id }) => {
			const el = sectionRefs.current[id];
			if (!el) return;
			const obs = new IntersectionObserver(
				([entry]) => {
					entries.set(id, entry.isIntersecting);
					// Pick the first visible section
					for (const s of SECTIONS) {
						if (entries.get(s.id)) {
							setActiveSection(s.id);
							break;
						}
					}
				},
				{ rootMargin: "-80px 0px -60% 0px", threshold: 0 }
			);
			obs.observe(el);
			observers.push(obs);
		});

		return () => observers.forEach((o) => o.disconnect());
	}, []);

	const createProject = useMutation({
		mutationFn: (data: Record<string, unknown>) =>
			api.post("/projects", data).then((r) => r.data),
		onSuccess: (data) => {
			window.location.href = `/projects/${data.id}`;
		},
	});

	const loadGilmoursTemplate = () => {
		reset({
			name: "Gilmours Central Seismic Strengthening",
			projectNumber: "S-02314",
			clientName: "Foodstuffs North Island",
			clientContact: "Project Manager",
			contractorName: "Kynoch Construction Ltd",
			contractSum: "4172492.92",
			gstRate: "0.15",
			siteLocation: "Ellerslie, Auckland",
			endClientName: "Foodstuffs North Island",
			endClientRepresentative: "Owen Sanders",
			endClientAddress: "Hope River\n251A Main Highway\nEllerslie\nAUCKLAND\n1060",
			landlordSplitPct: "100.00",
			operatorSplitPct: "0.00",
			provisionalSumTotal: "150000",
		});
		setWbsCodes(GILMOURS_WBS);
		setRetentionTiers(GILMOURS_RETENTION);
	};

	const addWbsCode = () => {
		if (!newWbsCode || !newWbsDesc) return;
		setWbsCodes([
			...wbsCodes,
			{
				code: newWbsCode,
				description: newWbsDesc,
				level: newWbsLevel,
				parent_code: newWbsLevel === "subcategory" ? newWbsParent || null : null,
				sort_order: wbsCodes.length,
				contract_sum: newWbsContractSum ? Number(newWbsContractSum) : null,
			},
		]);
		setNewWbsCode("");
		setNewWbsDesc("");
		setNewWbsContractSum("");
	};

	const removeWbs = (idx: number) => setWbsCodes(wbsCodes.filter((_, i) => i !== idx));

	const addRetentionTier = () => {
		if (!newRetPct) return;
		setRetentionTiers([
			...retentionTiers,
			{
				tier_order: retentionTiers.length + 1,
				percentage: newRetPct,
				up_to_amount: newRetAmt,
			},
		]);
		setNewRetPct("");
		setNewRetAmt("");
	};

	const removeRetention = (idx: number) =>
		setRetentionTiers(retentionTiers.filter((_, i) => i !== idx));

	const onSubmit = (form: FormValues) => {
		createProject.mutate({
			name: form.name,
			project_number: form.projectNumber || null,
			client_name: form.clientName,
			client_contact: form.clientContact || null,
			contractor_name: form.contractorName,
			contract_sum: form.contractSum,
			gst_rate: form.gstRate,
			end_client_name: form.endClientName || null,
			end_client_representative: form.endClientRepresentative || null,
			end_client_address: form.endClientAddress || null,
			landlord_split_pct: form.landlordSplitPct
				? (Number(form.landlordSplitPct) / 100).toString()
				: null,
			operator_split_pct: form.operatorSplitPct
				? (Number(form.operatorSplitPct) / 100).toString()
				: null,
			provisional_sum_total: form.provisionalSumTotal || null,
			wbs_codes: wbsCodes.map((w) => ({
				...w,
				contract_sum: w.contract_sum ?? null,
			})),
			retention_tiers: retentionTiers.map((t) => ({
				tier_order: t.tier_order,
				percentage: t.percentage,
				up_to_amount: t.up_to_amount || null,
			})),
		});
	};

	const categories = wbsCodes.filter((w) => w.level === "category");

	const splitTotal =
		landlordSplitPct && operatorSplitPct
			? Number(landlordSplitPct) + Number(operatorSplitPct)
			: null;

	const scrollToSection = (id: SectionId) => {
		sectionRefs.current[id]?.scrollIntoView({ behavior: "smooth", block: "start" });
	};

	// Determine completed sections (heuristic: has any data filled)
	const sectionFilled = (id: SectionId): boolean => {
		const vals = watch();
		switch (id) {
			case "contract":
				return !!(vals.name || vals.clientName || vals.contractorName);
			case "principal":
				return !!(vals.endClientName || vals.endClientRepresentative);
			case "landlord":
				return !!(vals.landlordSplitPct || vals.operatorSplitPct);
			case "wbs":
				return wbsCodes.length > 0;
			case "retention":
				return retentionTiers.length > 0;
		}
	};

	return (
		<Layout breadcrumbs={[{ label: "Projects", href: "/" }, { label: "New Project" }]}>
			<div className="max-w-[1100px] mx-auto">
			{/* Page header */}
			<header className="flex items-start justify-between gap-6 pb-5 mb-8 border-b border-line">
				<div>
					<div className="eyebrow mb-2">Setup &middot; Step 1 of 1</div>
					<h1 className="font-display text-[36px] leading-tight tracking-tight text-ink">
						New project
					</h1>
					<p className="mt-2 text-[13px] text-ink-3">
						Establish the contract baseline. Claims uploaded later will reconcile against this configuration.
					</p>
				</div>
				<div className="flex items-center gap-3 shrink-0 pt-2">
					<a href="/" className="text-[13px] text-ink-2 hover:text-ink transition-colors">
						Cancel
					</a>
					<Button
						type="button"
						variant="primary"
						size="md"
						onClick={handleSubmit(onSubmit)}
						disabled={createProject.isPending}
					>
						{createProject.isPending ? "Creating..." : "Create project"}
					</Button>
				</div>
			</header>

			<div className="flex gap-12">
				{/* ── Left sidebar ── */}
				<aside className="w-48 shrink-0 sticky top-20 self-start">
					<nav className="space-y-0.5 mb-8">
						{SECTIONS.map(({ id, label }) => {
							const filled = sectionFilled(id);
							const active = activeSection === id;
							return (
								<button
									key={id}
									onClick={() => scrollToSection(id)}
									className={`flex items-center gap-3 w-full text-left px-1 py-2 text-[13px] transition-colors ${
										active
											? "text-ink font-medium"
											: "text-ink-3 hover:text-ink-2"
									}`}
								>
									<span
										className={`w-[22px] h-[22px] rounded-full flex items-center justify-center shrink-0 transition-colors ${
											filled
												? "bg-brand text-white"
												: "border border-line-2"
										}`}
									>
										{filled && <Check className="h-3 w-3" strokeWidth={2.5} />}
									</span>
									{label}
								</button>
							);
						})}
					</nav>

					{/* Quick Start */}
					<Card className="bg-paper">
						<CardContent className="p-4">
							<div className="eyebrow mb-2">Quick start</div>
							<p className="text-[12px] text-ink-3 mb-3 leading-relaxed">
								Skip the form by loading a template from a similar project.
							</p>
							<Button
								type="button"
								variant="outline"
								size="sm"
								className="w-full"
								onClick={loadGilmoursTemplate}
							>
								Load template...
							</Button>
						</CardContent>
					</Card>
				</aside>

				{/* ── Main form ── */}
				<form onSubmit={handleSubmit(onSubmit)} className="flex-1 min-w-0 max-w-[720px] space-y-12 pb-20">
					{/* 01 — Contract details */}
					<section ref={(el) => { sectionRefs.current.contract = el; }}>
						<SectionHeading num="01" title="Contract details" desc="Identifying information and the contract sum used as the reconciliation baseline." />
						<div className="grid grid-cols-2 gap-4 mt-5">
							<FormField label="Project Name" required error={errors.name}>
								<Input {...register("name")} placeholder="e.g. Seismic Strengthening Works" />
							</FormField>
							<FormField label="Project Number" error={errors.projectNumber}>
								<Input {...register("projectNumber")} placeholder="e.g. S-02314" />
							</FormField>
							<FormField label="Client" required error={errors.clientName}>
								<Input {...register("clientName")} placeholder="e.g. Foodstuffs North Island" />
							</FormField>
							<FormField label="Head Contractor" required error={errors.contractorName}>
								<Input {...register("contractorName")} placeholder="e.g. Kynoch Construction Ltd" />
							</FormField>
							<FormField label={`Contract Sum (${user?.currency ?? "NZD"})`} required error={errors.contractSum}>
								<Input type="number" step="0.01" {...register("contractSum")} placeholder="$ 0.00" />
							</FormField>
							<FormField label="GST Rate" error={errors.gstRate}>
								<Input type="number" step="0.01" {...register("gstRate")} />
							</FormField>
							<FormField label="Site Location" error={undefined}>
								<Input {...register("siteLocation")} placeholder="e.g. Ellerslie, Auckland" />
							</FormField>
						</div>
					</section>

					{/* 02 — Principal & end-client */}
					<section ref={(el) => { sectionRefs.current.principal = el; }}>
						<SectionHeading num="02" title="Principal & end-client" />
						<div className="grid grid-cols-2 gap-4 mt-5">
							<FormField label="End Client / Principal" error={errors.endClientName}>
								<Input {...register("endClientName")} placeholder="e.g. Foodstuffs North Island" />
							</FormField>
							<FormField label="Representative" error={errors.endClientRepresentative}>
								<Input {...register("endClientRepresentative")} placeholder="e.g. Owen Sanders" />
							</FormField>
							<FormField label="Address" className="col-span-2" error={errors.endClientAddress}>
								<Textarea
									{...register("endClientAddress")}
									rows={3}
									placeholder={"Company Name\nStreet Address\nSuburb\nCity\nPostcode"}
								/>
							</FormField>
						</div>
					</section>

					{/* 03 — Landlord / operator split */}
					<section ref={(el) => { sectionRefs.current.landlord = el; }}>
						<SectionHeading num="03" title="Landlord / operator split" desc="Leave blank if not applicable. Values must total 100%." />
						<div className="grid grid-cols-2 gap-4 mt-5">
							<FormField label="Landlord %" error={errors.landlordSplitPct}>
								<Input
									type="number"
									step="0.01"
									min="0"
									max="100"
									placeholder="0.00"
									{...register("landlordSplitPct", {
										onChange: (e) => {
											const val = e.target.value;
											if (val) {
												setValue("operatorSplitPct", (100 - Number(val)).toFixed(2));
											} else {
												setValue("operatorSplitPct", "");
											}
										},
									})}
								/>
							</FormField>
							<FormField label="Operator %" error={errors.operatorSplitPct}>
								<Input
									type="number"
									step="0.01"
									min="0"
									max="100"
									placeholder="0.00"
									{...register("operatorSplitPct", {
										onChange: (e) => {
											const val = e.target.value;
											if (val) {
												setValue("landlordSplitPct", (100 - Number(val)).toFixed(2));
											} else {
												setValue("landlordSplitPct", "");
											}
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
						</div>
					</section>

					{/* 04 — WBS structure */}
					<section ref={(el) => { sectionRefs.current.wbs = el; }}>
						<SectionHeading num="04" title="WBS structure" desc="Claims line items will be auto-categorised into these codes." />

						{/* WBS table */}
						{wbsCodes.length > 0 && (
							<div className="mt-5 border border-line rounded-[var(--radius-lg)] overflow-hidden">
								{/* Table header */}
								<div
									className="grid gap-x-3 px-4 py-2 bg-paper-2 eyebrow"
									style={{ gridTemplateColumns: "72px 1fr 120px 32px" }}
								>
									<div>Code</div>
									<div>Description</div>
									<div className="text-right">Contract</div>
									<div />
								</div>

								{/* Table rows */}
								{categories.map((cat) => {
									const subs = wbsCodes.filter(
										(w) => w.level === "subcategory" && w.parent_code === cat.code
									);
									return (
										<div key={cat.code}>
											{/* Category row */}
											<div
												className="grid gap-x-3 items-center px-4 py-2.5 border-t border-line"
												style={{ gridTemplateColumns: "72px 1fr 120px 32px" }}
											>
												<span className="font-mono text-[13px] text-ink font-semibold">{cat.code}</span>
												<span className="text-[13px] text-ink font-semibold">{cat.description}</span>
												<div className="text-right text-ink-4">&mdash;</div>
												<button
													type="button"
													onClick={() => removeWbs(wbsCodes.indexOf(cat))}
													className="text-ink-4 hover:text-err transition-colors justify-self-center"
												>
													<X className="h-3.5 w-3.5" />
												</button>
											</div>

											{/* Subcategory rows */}
											{subs.map((sub) => (
												<div
													key={sub.code}
													className="grid gap-x-3 items-center px-4 py-2 border-t border-line"
													style={{ gridTemplateColumns: "72px 1fr 120px 32px" }}
												>
													<span className="font-mono text-[13px] text-ink-3">{sub.code}</span>
													<span className="text-[13px] text-ink-2">{sub.description}</span>
													<span className="font-mono-nums text-[13px] text-ink-2 text-right">
														{sub.contract_sum != null
															? `$${Number(sub.contract_sum).toLocaleString(undefined, {
																	minimumFractionDigits: 2,
																	maximumFractionDigits: 2,
																})}`
															: ""}
													</span>
													<button
														type="button"
														onClick={() => removeWbs(wbsCodes.indexOf(sub))}
														className="text-ink-4 hover:text-err transition-colors justify-self-center"
													>
														<X className="h-3.5 w-3.5" />
													</button>
												</div>
											))}
										</div>
									);
								})}

								{/* Total row */}
								<div
									className="grid gap-x-3 items-center px-4 py-2.5 border-t border-line bg-paper-2"
									style={{ gridTemplateColumns: "72px 1fr 120px 32px" }}
								>
									<span className="text-ink-4">&mdash;</span>
									<span className="text-[13px] text-ink font-semibold">Total contract works</span>
									<span className="font-mono-nums text-[13px] text-ink font-semibold text-right">
										$
										{wbsCodes
											.filter((w) => w.level === "subcategory")
											.reduce((sum, s) => sum + (s.contract_sum ?? 0), 0)
											.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
									</span>
									<div />
								</div>
							</div>
						)}

						{/* Add actions */}
						<div className="flex items-center gap-4 mt-4">
							<button
								type="button"
								onClick={() => setShowWbsAdd(true)}
								className="inline-flex items-center gap-1.5 text-[13px] text-ink-3 hover:text-ink transition-colors"
							>
								<Plus className="h-3.5 w-3.5" />
								Add category
							</button>
							<button
								type="button"
								className="inline-flex items-center gap-1.5 text-[13px] text-ink-3 hover:text-ink transition-colors"
							>
								<Upload className="h-3.5 w-3.5" />
								Import from CSV
							</button>
						</div>

						{/* Inline add form */}
						{showWbsAdd && (
							<div className="mt-3 p-4 border border-line rounded-[var(--radius-lg)] bg-surface space-y-3">
								<div className="flex flex-wrap gap-3 items-end">
									<div className="flex flex-col gap-1">
										<label className="text-[11px] text-ink-3 font-medium tracking-[0.04em] uppercase">Level</label>
										<Select
											value={newWbsLevel}
											onChange={(e) => setNewWbsLevel(e.target.value as "category" | "subcategory")}
											className="w-32"
										>
											<option value="category">Category</option>
											<option value="subcategory">Subcategory</option>
										</Select>
									</div>
									<div className="flex flex-col gap-1">
										<label className="text-[11px] text-ink-3 font-medium tracking-[0.04em] uppercase">Code</label>
										<Input
											value={newWbsCode}
											onChange={(e) => setNewWbsCode(e.target.value)}
											className="w-24"
											placeholder="PG-01"
										/>
									</div>
									<div className="flex flex-col gap-1 flex-1 min-w-40">
										<label className="text-[11px] text-ink-3 font-medium tracking-[0.04em] uppercase">Description</label>
										<Input
											value={newWbsDesc}
											onChange={(e) => setNewWbsDesc(e.target.value)}
											placeholder="Preliminary & General"
										/>
									</div>
									{newWbsLevel === "subcategory" && (
										<div className="flex flex-col gap-1">
											<label className="text-[11px] text-ink-3 font-medium tracking-[0.04em] uppercase">Parent</label>
											<Select
												value={newWbsParent}
												onChange={(e) => setNewWbsParent(e.target.value)}
												className="w-44"
											>
												<option value="">Select parent...</option>
												{categories.map((c) => (
													<option key={c.code} value={c.code}>
														{c.code} - {c.description}
													</option>
												))}
											</Select>
										</div>
									)}
									<div className="flex flex-col gap-1">
										<label className="text-[11px] text-ink-3 font-medium tracking-[0.04em] uppercase">Contract Sum</label>
										<Input
											type="number"
											step="0.01"
											value={newWbsContractSum}
											onChange={(e) => setNewWbsContractSum(e.target.value)}
											className="w-28"
											placeholder="0.00"
										/>
									</div>
								</div>
								<div className="flex gap-2">
									<Button type="button" onClick={() => { addWbsCode(); }} size="sm">
										Add
									</Button>
									<Button type="button" variant="ghost" size="sm" onClick={() => setShowWbsAdd(false)}>
										Cancel
									</Button>
								</div>
							</div>
						)}
					</section>

					{/* 05 — Retention tiers */}
					<section ref={(el) => { sectionRefs.current.retention = el; }}>
						<SectionHeading num="05" title="Retention tiers" desc="Tiered retention applied to recommended amounts. Tiers stack from lowest threshold up." />

						{retentionTiers.length > 0 && (
							<div className="space-y-2.5 mt-5">
								{retentionTiers.map((tier, i) => (
									<div
										key={i}
										className="flex items-center gap-5 px-5 py-4 border border-line rounded-[var(--radius-lg)] bg-surface"
									>
										{/* Tier badge */}
										<span className="inline-flex items-center justify-center w-9 h-9 rounded-[var(--radius-md)] bg-brand text-white text-[11px] font-semibold shrink-0">
											T {tier.tier_order}
										</span>

										{/* Rate */}
										<div className="min-w-[80px]">
											<div className="eyebrow mb-0.5">Rate</div>
											<span className="text-[15px] font-semibold text-ink">
												{(Number(tier.percentage) * 100).toFixed(2)}%
											</span>
										</div>

										{/* Threshold / Up to */}
										<div className="min-w-[120px]">
											<div className="eyebrow mb-0.5">
												{tier.up_to_amount ? "Up to" : "Threshold"}
											</div>
											<span className="text-[15px] font-semibold text-ink">
												{tier.up_to_amount
													? `$${Number(tier.up_to_amount).toLocaleString()}`
													: "Remainder"}
											</span>
										</div>

										{/* Remove */}
										<button
											type="button"
											onClick={() => removeRetention(i)}
											className="ml-auto text-ink-4 hover:text-err transition-colors"
										>
											<X className="h-4 w-4" />
										</button>
									</div>
								))}
							</div>
						)}

						{/* Add tier */}
						{showRetentionAdd ? (
							<div className="mt-3 p-4 border border-line rounded-[var(--radius-lg)] bg-surface">
								<div className="flex flex-wrap gap-3 items-end">
									<div className="flex flex-col gap-1">
										<label className="text-[11px] text-ink-3 font-medium tracking-[0.04em] uppercase">Percentage (decimal)</label>
										<Input
											type="number"
											step="0.0001"
											value={newRetPct}
											onChange={(e) => setNewRetPct(e.target.value)}
											className="w-32"
											placeholder="0.10"
										/>
									</div>
									<div className="flex flex-col gap-1">
										<label className="text-[11px] text-ink-3 font-medium tracking-[0.04em] uppercase">Up to amount (blank = remainder)</label>
										<Input
											type="number"
											step="0.01"
											value={newRetAmt}
											onChange={(e) => setNewRetAmt(e.target.value)}
											className="w-40"
											placeholder="200000"
										/>
									</div>
								</div>
								<div className="flex gap-2 mt-3">
									<Button type="button" onClick={() => { addRetentionTier(); }} size="sm">
										Add
									</Button>
									<Button type="button" variant="ghost" size="sm" onClick={() => setShowRetentionAdd(false)}>
										Cancel
									</Button>
								</div>
							</div>
						) : (
							<button
								type="button"
								onClick={() => setShowRetentionAdd(true)}
								className="inline-flex items-center gap-1.5 mt-4 text-[13px] text-ink-3 hover:text-ink transition-colors"
							>
								<Plus className="h-3.5 w-3.5" />
								Add tier
							</button>
						)}
					</section>

					{/* Submit area (bottom) */}
					<div className="flex items-center gap-4 pt-6 border-t border-line">
						<Button type="submit" disabled={createProject.isPending} size="lg">
							{createProject.isPending ? "Creating..." : "Create project"}
						</Button>
						<a href="/" className={buttonVariants({ variant: "ghost", size: "lg" })}>
							Cancel
						</a>
					</div>

					{createProject.isError && (
						<Alert variant="error">
							<AlertDescription>
								Failed to create project. Please check your inputs and try again.
							</AlertDescription>
						</Alert>
					)}
				</form>
			</div>
			</div>
		</Layout>
	);
}

// ---------------------------------------------------------------------------
// Section heading with number
// ---------------------------------------------------------------------------

function SectionHeading({ num, title, desc }: { num: string; title: string; desc?: string }) {
	return (
		<div className="flex gap-4 items-baseline border-b border-line pb-4">
			<span className="text-ink-5 text-[15px] font-mono-nums tabular-nums">{num}</span>
			<div>
				<h2 className="font-semibold text-[17px] text-ink tracking-tight">{title}</h2>
				{desc && <p className="text-[13px] text-ink-3 mt-1">{desc}</p>}
			</div>
		</div>
	);
}
