/** Line item approval status */
export type ItemStatus = "unapproved" | "approved" | "interim";

/** WBS (Work Breakdown Structure) code */
export interface WBSCode {
	id: string;
	code: string;
	description: string;
	level: string;
	parent_id: string | null;
	sort_order: number;
	contract_sum?: string | null;
	in_use?: boolean;
	children?: WBSCode[];
}

/** Tiered retention bracket */
export interface RetentionTier {
	id?: string;
	tier_order: number;
	percentage: string;
	up_to_amount: string | null;
}

/** Project */
export interface Project {
	id: string;
	name: string;
	project_number?: string | null;
	client_name: string;
	contractor_name: string;
	contract_sum: string;
	status?: string | null;
	gst_rate?: string;
	wbs_codes?: WBSCode[];
	retention_tiers?: RetentionTier[];
	end_client_name?: string | null;
	end_client_representative?: string | null;
	end_client_address?: string | null;
	landlord_split_pct?: string | null;
	operator_split_pct?: string | null;
	provisional_sum_total?: string | null;
	client_contact?: string | null;
}

/** Claim line item (for review page) */
export interface ClaimLineItem {
	id: string;
	warnings: string[];
	categorisation_confidence: string | null;
}

/** Claim detail (for review page) */
export interface Claim {
	id: string;
	claim_number: number;
	period_from: string | null;
	period_to: string | null;
	payment_due: string | null;
	claim_received: string | null;
	provisional_payment_schedule_due: string | null;
	payment_schedule_due: string | null;
	validation_warnings: string[];
	line_items: ClaimLineItem[];
	summary?: ClaimSummary | null;
}

/** Claim summary totals */
export interface ClaimSummary {
	original_contract_total: string | null;
	variations_total: string | null;
	revised_contract_total: string | null;
	retention_amount: string | null;
	claimed_amount: string | null;
}

/** Claim list item (for project detail page, includes assessment info) */
export interface ClaimListItem {
	id: string;
	project_id: string;
	claim_number: number;
	period_from: string | null;
	period_to: string | null;
	payment_due: string | null;
	claim_received: string | null;
	provisional_payment_schedule_due: string | null;
	payment_schedule_due: string | null;
	parsed_at: string | null;
	assessment_id: string | null;
	assessment_status: string | null;
	summary: ClaimSummary;
}
