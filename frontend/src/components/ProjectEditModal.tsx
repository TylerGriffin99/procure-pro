import { useForm } from "react-hook-form";
import { yupResolver } from "@hookform/resolvers/yup";
import * as yup from "yup";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { FormField } from "@/components/form-field";

const schema = yup.object({
	name: yup.string().required("Project name is required"),
	project_number: yup.string().default(""),
	client_name: yup.string().required("Client name is required"),
	client_contact: yup.string().default(""),
	contractor_name: yup.string().required("Contractor name is required"),
	contract_sum: yup.string().required("Contract sum is required"),
	gst_rate: yup.string().required("GST rate is required"),
	end_client_name: yup.string().default(""),
	end_client_representative: yup.string().default(""),
	end_client_address: yup.string().default(""),
	landlord_split_pct: yup.string().default(""),
	operator_split_pct: yup.string().default(""),
	provisional_sum_total: yup.string().default(""),
});

type FormValues = yup.InferType<typeof schema>;

interface ProjectEditModalProps {
	project: {
		id: string;
		name: string;
		project_number: string | null;
		client_name: string;
		contractor_name: string;
		contract_sum: string;
		gst_rate: string;
		end_client_name?: string | null;
		end_client_representative?: string | null;
		end_client_address?: string | null;
		landlord_split_pct?: string | null;
		operator_split_pct?: string | null;
		provisional_sum_total?: string | null;
		client_contact?: string | null;
	};
	onSave: (data: Record<string, string | number | null>) => void;
	onClose: () => void;
	isSaving: boolean;
}

export default function ProjectEditModal({ project, onSave, onClose, isSaving }: ProjectEditModalProps) {
	const {
		register,
		handleSubmit,
		formState: { errors },
	} = useForm<FormValues>({
		resolver: yupResolver(schema),
		defaultValues: {
			name: project.name || "",
			project_number: project.project_number || "",
			client_name: project.client_name || "",
			client_contact: project.client_contact || "",
			contractor_name: project.contractor_name || "",
			contract_sum: project.contract_sum || "",
			gst_rate: project.gst_rate || "0.15",
			end_client_name: project.end_client_name || "",
			end_client_representative: project.end_client_representative || "",
			end_client_address: project.end_client_address || "",
			landlord_split_pct: project.landlord_split_pct
				? String(Number(project.landlord_split_pct) * 100)
				: "",
			operator_split_pct: project.operator_split_pct
				? String(Number(project.operator_split_pct) * 100)
				: "",
			provisional_sum_total: project.provisional_sum_total || "",
		},
	});

	const onSubmit = (form: FormValues) => {
		const data: Record<string, string | number | null> = {};
		for (const [key, value] of Object.entries(form)) {
			if (["landlord_split_pct", "operator_split_pct"].includes(key)) {
				data[key] = value ? Number(value) / 100 : null;
			} else if (["contract_sum", "gst_rate", "provisional_sum_total"].includes(key)) {
				data[key] = value ? Number(value) : null;
			} else {
				data[key] = value || null;
			}
		}
		onSave(data);
	};

	return (
		<Dialog open onClose={onClose}>
			<DialogContent>
				<DialogHeader onClose={onClose}>
					<DialogTitle>Edit Project</DialogTitle>
				</DialogHeader>

				<form onSubmit={handleSubmit(onSubmit)} className="px-6 py-4 space-y-5">
					{/* Project Info */}
					<div>
						<h3 className="text-sm font-semibold text-foreground mb-3">Project Info</h3>
						<div className="grid grid-cols-2 gap-4">
							<FormField label="Project Name" required error={errors.name}>
								<Input {...register("name")} />
							</FormField>
							<FormField label="Project Number" error={errors.project_number}>
								<Input {...register("project_number")} />
							</FormField>
							<FormField label="Contract Sum" required error={errors.contract_sum}>
								<Input type="number" step="0.01" {...register("contract_sum")} />
							</FormField>
							<FormField label="GST Rate" required error={errors.gst_rate}>
								<Input type="number" step="0.0001" {...register("gst_rate")} />
							</FormField>
							<FormField label="Provisional Sum Total" error={errors.provisional_sum_total}>
								<Input type="number" step="0.01" {...register("provisional_sum_total")} />
							</FormField>
						</div>
					</div>

					{/* Client */}
					<div>
						<h3 className="text-sm font-semibold text-foreground mb-3">Client</h3>
						<div className="grid grid-cols-2 gap-4">
							<FormField label="Client Name (QS Firm)" required error={errors.client_name}>
								<Input {...register("client_name")} />
							</FormField>
							<FormField label="Client Contact" error={errors.client_contact}>
								<Input {...register("client_contact")} />
							</FormField>
							<FormField label="End Client (Principal)" error={errors.end_client_name}>
								<Input {...register("end_client_name")} />
							</FormField>
							<FormField label="End Client Representative" error={errors.end_client_representative}>
								<Input {...register("end_client_representative")} />
							</FormField>
							<FormField label="End Client Address" className="col-span-2" error={errors.end_client_address}>
								<Textarea className="h-20" {...register("end_client_address")} />
							</FormField>
						</div>
					</div>

					{/* Contractor */}
					<div>
						<h3 className="text-sm font-semibold text-foreground mb-3">Contractor</h3>
						<FormField label="Contractor Name" required error={errors.contractor_name}>
							<Input {...register("contractor_name")} />
						</FormField>
					</div>

					{/* Payment Split */}
					<div>
						<h3 className="text-sm font-semibold text-foreground mb-3">Payment Split</h3>
						<div className="grid grid-cols-2 gap-4">
							<FormField label="Landlord Split %" error={errors.landlord_split_pct}>
								<Input type="number" step="0.01" min="0" max="100" {...register("landlord_split_pct")} />
							</FormField>
							<FormField label="Operator Split %" error={errors.operator_split_pct}>
								<Input type="number" step="0.01" min="0" max="100" {...register("operator_split_pct")} />
							</FormField>
						</div>
					</div>

					<DialogFooter>
						<Button type="button" variant="ghost" onClick={onClose}>
							Cancel
						</Button>
						<Button type="submit" disabled={isSaving}>
							{isSaving ? "Saving..." : "Save Changes"}
						</Button>
					</DialogFooter>
				</form>
			</DialogContent>
		</Dialog>
	);
}
