import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "@/api/client";

interface AssessmentLineItem {
	id: string;
	claim_line_item_id: string | null;
	description: string;
	contractor_claim_to_date: string;
	total_recommended: string;
	percentage: string;
	variance_to_claim: string;
	previously_paid: string;
	recommended_this_period: string;
	status: "unapproved" | "approved" | "interim";
	comments: string | null;
	wbs_code_id: string | null;
	sort_order: number;
	adjustment_type: string | null;
	source_assessment_id: string | null;
}

interface AssessmentVariationItem {
	id: string;
	variation_id: string;
	claim_line_item_id: string | null;
	contractor_ref: string;
	description: string;
	contractor_submission: string;
	contractor_claim_to_date: string;
	total_recommended: string;
	previously_paid: string;
	recommended_this_period: string;
	variance_to_claim: string;
	percentage: string;
	status: "unapproved" | "approved" | "interim";
	comments: string | null;
	adjustment_type: string | null;
	source_assessment_id: string | null;
}

interface AssessmentProvisionalSumItem {
	id: string;
	provisional_sum_id: string;
	claim_line_item_id: string | null;
	ps_number: number;
	description: string;
	contract_sum: string;
	contractor_claim_to_date: string;
	total_recommended: string;
	previously_paid: string;
	recommended_this_period: string;
	variance_to_claim: string;
	percentage: string;
	status: "unapproved" | "approved" | "interim";
	comments: string | null;
	adjustment_type: string | null;
	source_assessment_id: string | null;
}

export interface AggregatedWBSGroup {
	wbs_code_id: string;
	description: string;
	contract_sum: string;
	previously_paid: string;
	recommended_this_period: string;
	total_recommended: string;
	contractor_claim_to_date: string;
	variance_to_claim: string;
	percentage: string;
	history_row: AssessmentLineItem | null;
	child_rows: AssessmentLineItem[];
}

export interface AggregatedVariationGroup {
	variation_id: string;
	contractor_ref: string;
	description: string;
	contractor_submission: string;
	previously_paid: string;
	recommended_this_period: string;
	total_recommended: string;
	contractor_claim_to_date: string;
	variance_to_claim: string;
	percentage: string;
	history_row: AssessmentVariationItem | null;
	child_rows: AssessmentVariationItem[];
}

export interface AggregatedPSGroup {
	provisional_sum_id: string;
	ps_number: number;
	description: string;
	contract_sum: string;
	previously_paid: string;
	recommended_this_period: string;
	total_recommended: string;
	contractor_claim_to_date: string;
	variance_to_claim: string;
	percentage: string;
	history_row: AssessmentProvisionalSumItem | null;
	child_rows: AssessmentProvisionalSumItem[];
}

interface Assessment {
	id: string;
	claim_id: string;
	project_id: string;
	version: number;
	status: "draft" | "finalised";
	contract_sum: string | null;
	total_recommended: string | null;
	recommended_this_period: string | null;
	total_including_gst: string | null;
	line_items: AssessmentLineItem[];
	variation_items: AssessmentVariationItem[];
	provisional_sum_items: AssessmentProvisionalSumItem[];
	wbs_groups: AggregatedWBSGroup[];
	variation_groups: AggregatedVariationGroup[];
	ps_groups: AggregatedPSGroup[];
}

interface PriorInterimItem {
	parent_id: string;
	previously_paid: string;
	comments: string | null;
}

interface PriorInterims {
	wbs_interims: PriorInterimItem[];
	variation_interims: PriorInterimItem[];
	ps_interims: PriorInterimItem[];
}

export function usePriorInterims(projectId: string, assessmentId: string) {
	return useQuery<PriorInterims>({
		queryKey: ["prior-interims", projectId, assessmentId],
		queryFn: () =>
			api.get(`/projects/${projectId}/assessments/${assessmentId}/prior-interims`).then((r) => r.data),
	});
}

export function useAssessment(projectId: string, assessmentId: string) {
	return useQuery<Assessment>({
		queryKey: ["assessment", projectId, assessmentId],
		queryFn: () => api.get(`/projects/${projectId}/assessments/${assessmentId}`).then((r) => r.data),
	});
}

export function useUpdateLineItem(projectId: string, assessmentId: string) {
	const queryClient = useQueryClient();

	return useMutation({
		mutationFn: (params: { lineItemId: string; data: Partial<AssessmentLineItem> }) =>
			api.patch(
				`/projects/${projectId}/assessments/${assessmentId}/line-items/${params.lineItemId}`,
				params.data
			).then((r) => r.data),
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["assessment", projectId, assessmentId] });
			queryClient.invalidateQueries({ queryKey: ["assessment-by-claim"] });
		},
	});
}

export function useUpdateVariationItem(projectId: string, assessmentId: string) {
	const queryClient = useQueryClient();

	return useMutation({
		mutationFn: (params: { itemId: string; data: Partial<AssessmentVariationItem> }) =>
			api.patch(
				`/projects/${projectId}/assessments/${assessmentId}/variation-items/${params.itemId}`,
				params.data
			).then((r) => r.data),
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["assessment", projectId, assessmentId] });
			queryClient.invalidateQueries({ queryKey: ["assessment-by-claim"] });
		},
	});
}

export function useUpdateProvisionalSumItem(projectId: string, assessmentId: string) {
	const queryClient = useQueryClient();

	return useMutation({
		mutationFn: (params: { itemId: string; data: Partial<AssessmentProvisionalSumItem> }) =>
			api.patch(
				`/projects/${projectId}/assessments/${assessmentId}/provisional-sum-items/${params.itemId}`,
				params.data
			).then((r) => r.data),
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["assessment", projectId, assessmentId] });
			queryClient.invalidateQueries({ queryKey: ["assessment-by-claim"] });
		},
	});
}

export function useFinaliseAssessment(projectId: string, assessmentId: string) {
	const queryClient = useQueryClient();

	return useMutation({
		mutationFn: () =>
			api.post(`/projects/${projectId}/assessments/${assessmentId}/finalise`).then((r) => r.data),
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["assessment", projectId, assessmentId] });
			queryClient.invalidateQueries({ queryKey: ["assessment-by-claim"] });
			queryClient.invalidateQueries({ queryKey: ["claims", projectId] });
		},
	});
}

export function useRevertAssessmentToDraft(projectId: string, assessmentId: string) {
	const queryClient = useQueryClient();

	return useMutation({
		mutationFn: () =>
			api.post(`/projects/${projectId}/assessments/${assessmentId}/revert-to-draft`).then((r) => r.data),
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["assessment", projectId, assessmentId] });
			queryClient.invalidateQueries({ queryKey: ["assessment-by-claim"] });
			queryClient.invalidateQueries({ queryKey: ["claims", projectId] });
		},
		onError: (error: unknown) => {
			const detail = (error as { response?: { data?: { detail?: string } } })
				?.response?.data?.detail;
			alert(detail ?? "Failed to revert assessment. Please try again.");
		},
	});
}

interface ReclassifyParams {
	source_item_id: string;
	source_type: "line-item" | "variation" | "provisional-sum";
	target_type: "line-item" | "variation" | "provisional-sum";
	target_id?: string | null;
	target_wbs_code_id?: string | null;
	new_record?: { description: string } | null;
}

export function useReclassifyItem(projectId: string, assessmentId: string) {
	const queryClient = useQueryClient();

	return useMutation({
		mutationFn: (params: ReclassifyParams) =>
			api.post(
				`/projects/${projectId}/assessments/${assessmentId}/reclassify`,
				params
			).then((r) => r.data),
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["assessment", projectId, assessmentId] });
			queryClient.invalidateQueries({ queryKey: ["assessment-by-claim"] });
		},
	});
}

interface InterimAdjustParams {
	item_type: "line-item" | "variation" | "provisional-sum";
	parent_id: string;
	agreed_total: number;
	comments?: string | null;
}

export function useCreateInterimAdjustment(projectId: string, assessmentId: string) {
	const queryClient = useQueryClient();

	return useMutation({
		mutationFn: (params: InterimAdjustParams) =>
			api.post(
				`/projects/${projectId}/assessments/${assessmentId}/interim-adjust`,
				params
			).then((r) => r.data),
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["assessment", projectId, assessmentId] });
			queryClient.invalidateQueries({ queryKey: ["assessment-by-claim"] });
			queryClient.invalidateQueries({ queryKey: ["prior-interims", projectId, assessmentId] });
		},
	});
}

interface CloseOutParams {
	item_type: "line-item" | "variation" | "provisional-sum";
	parent_id: string;
}

export function useCloseOutItem(projectId: string, assessmentId: string) {
	const queryClient = useQueryClient();

	return useMutation({
		mutationFn: (params: CloseOutParams) =>
			api.post(
				`/projects/${projectId}/assessments/${assessmentId}/close-out`,
				params
			).then((r) => r.data),
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["assessment", projectId, assessmentId] });
			queryClient.invalidateQueries({ queryKey: ["assessment-by-claim"] });
			queryClient.invalidateQueries({ queryKey: ["prior-interims", projectId, assessmentId] });
		},
	});
}

export type { Assessment, AssessmentLineItem, AssessmentVariationItem, AssessmentProvisionalSumItem, PriorInterims, PriorInterimItem };
