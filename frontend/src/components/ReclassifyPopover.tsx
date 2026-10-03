import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Combobox, type ComboboxOption } from "@/components/ui/combobox";
import { cn } from "@/lib/utils";

type TargetType = "line-item" | "variation" | "provisional-sum";

interface ReclassifyPopoverProps {
	sourceItemId: string;
	sourceType: TargetType;
	wbsOptions: ComboboxOption[];
	variationOptions: ComboboxOption[];
	psOptions: ComboboxOption[];
	onConfirm: (params: {
		source_item_id: string;
		source_type: TargetType;
		target_type: TargetType;
		target_id?: string | null;
		target_wbs_code_id?: string | null;
		new_record?: { description: string } | null;
	}) => void;
	onCancel: () => void;
	isPending: boolean;
}

const CREATE_NEW_VALUE = "__create_new__";

export function ReclassifyPopover({
	sourceItemId,
	sourceType,
	wbsOptions,
	variationOptions,
	psOptions,
	onConfirm,
	onCancel,
	isPending,
}: ReclassifyPopoverProps) {
	const [targetType, setTargetType] = useState<TargetType>("line-item");
	const [selectedId, setSelectedId] = useState("");
	const [newDescription, setNewDescription] = useState("");

	const isCreatingNew = selectedId === CREATE_NEW_VALUE;

	const currentOptions: ComboboxOption[] =
		targetType === "line-item"
			? wbsOptions
			: targetType === "variation"
				? [...variationOptions, { value: CREATE_NEW_VALUE, label: "+ Create new" }]
				: [...psOptions, { value: CREATE_NEW_VALUE, label: "+ Create new" }];

	const canConfirm =
		selectedId !== "" && (!isCreatingNew || newDescription.trim() !== "");

	const handleConfirm = () => {
		if (isCreatingNew) {
			onConfirm({
				source_item_id: sourceItemId,
				source_type: sourceType,
				target_type: targetType,
				new_record: { description: newDescription.trim() },
			});
		} else if (targetType === "line-item") {
			onConfirm({
				source_item_id: sourceItemId,
				source_type: sourceType,
				target_type: targetType,
				target_wbs_code_id: selectedId,
			});
		} else {
			onConfirm({
				source_item_id: sourceItemId,
				source_type: sourceType,
				target_type: targetType,
				target_id: selectedId,
			});
		}
	};

	return (
		<div className="absolute right-0 bottom-full mb-1 z-50 bg-white border border-line rounded-lg shadow-lg p-3 w-80">
			<p className="text-xs font-semibold text-ink-2 mb-2">Reclassify to:</p>

			{/* Type selector */}
			<div className="flex gap-1 mb-3">
				{(
					[
						["line-item", "Contract Work"],
						["variation", "Variation"],
						["provisional-sum", "Prov. Sum"],
					] as const
				).map(([type, label]) => (
					<Button
						key={type}
						size="xs"
						variant={targetType === type ? "primary" : "outline"}
						onClick={() => {
							setTargetType(type);
							setSelectedId("");
							setNewDescription("");
						}}
						className={cn("flex-1")}
					>
						{label}
					</Button>
				))}
			</div>

			{/* Target selector */}
			<Combobox
				options={currentOptions}
				value={selectedId}
				onChange={(val) => {
					setSelectedId(val);
					if (val !== CREATE_NEW_VALUE) setNewDescription("");
				}}
				placeholder={
					targetType === "line-item"
						? "Select WBS code..."
						: targetType === "variation"
							? "Select variation..."
							: "Select provisional sum..."
				}
				searchPlaceholder="Search..."
				className="mb-2"
			/>

			{/* New record description */}
			{isCreatingNew && (
				<Input
					type="text"
					value={newDescription}
					onChange={(e) => setNewDescription(e.target.value)}
					placeholder="Description for new record..."
					className="text-sm h-8 mb-2"
				/>
			)}

			{/* Actions */}
			<div className="flex justify-end gap-1.5">
				<Button size="xs" variant="secondary" onClick={onCancel}>
					Cancel
				</Button>
				<Button
					size="xs"
					variant="primary"
					onClick={handleConfirm}
					disabled={!canConfirm || isPending}
				>
					{isPending ? "Moving..." : "Confirm"}
				</Button>
			</div>
		</div>
	);
}
