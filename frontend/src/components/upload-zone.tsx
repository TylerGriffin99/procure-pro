import { useState, useRef, useCallback, type DragEvent, type ChangeEvent } from "react";
import { cn } from "@/lib/utils";
import { Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";

interface UploadZoneProps {
	onFileSelect: (file: File) => void;
	accept?: string;
	isUploading?: boolean;
	uploadingLabel?: string;
	uploadingDescription?: string;
	disabled?: boolean;
	disabledMessage?: string;
	className?: string;
}

export function UploadZone({
	onFileSelect,
	accept = "application/pdf",
	isUploading = false,
	uploadingLabel = "Uploading...",
	uploadingDescription,
	disabled = false,
	disabledMessage,
	className,
}: UploadZoneProps) {
	const [isDragging, setIsDragging] = useState(false);
	const fileInputRef = useRef<HTMLInputElement>(null);

	const handleDragOver = useCallback((e: DragEvent) => {
		e.preventDefault();
		if (!disabled) setIsDragging(true);
	}, [disabled]);

	const handleDragLeave = useCallback((e: DragEvent) => {
		e.preventDefault();
		setIsDragging(false);
	}, []);

	const handleDrop = useCallback(
		(e: DragEvent) => {
			e.preventDefault();
			setIsDragging(false);
			if (disabled) return;
			const files = e.dataTransfer.files;
			if (files.length > 0) {
				onFileSelect(files[0]);
			}
		},
		[onFileSelect, disabled]
	);

	const handleFileInput = (e: ChangeEvent<HTMLInputElement>) => {
		const file = e.target.files?.[0];
		if (file) onFileSelect(file);
	};

	const triggerFileInput = () => {
		fileInputRef.current?.click();
	};

	return (
		<div
			onDragOver={handleDragOver}
			onDragLeave={handleDragLeave}
			onDrop={handleDrop}
			className={cn(
				"border-2 border-dashed rounded-lg p-12 text-center transition-colors",
				disabled
					? "border-border opacity-50 cursor-not-allowed"
					: isDragging
						? "border-primary bg-primary/5"
						: "border-border hover:border-muted-foreground/50",
				className
			)}
		>
			{disabled ? (
				<div className="flex flex-col items-center gap-3">
					<Upload className="h-12 w-12 text-muted-foreground/30" />
					<p className="text-muted-foreground">
						{disabledMessage ?? "Upload is currently disabled"}
					</p>
				</div>
			) : isUploading ? (
				<div className="flex flex-col items-center gap-3">
					<Spinner size="lg" />
					<p className="text-muted-foreground font-medium">{uploadingLabel}</p>
					{uploadingDescription && (
						<p className="text-sm text-muted-foreground/70">{uploadingDescription}</p>
					)}
				</div>
			) : (
				<div className="flex flex-col items-center gap-3">
					<Upload className="h-12 w-12 text-muted-foreground/50" />
					<p className="text-muted-foreground">
						Drag and drop a contractor claim PDF here
					</p>
					<p className="text-sm text-muted-foreground/50">or</p>
					<Button variant="primary" size="sm" type="button" onClick={triggerFileInput}>
						Browse Files
					</Button>
					<input
						ref={fileInputRef}
						type="file"
						accept={accept}
						onChange={handleFileInput}
						className="hidden"
					/>
				</div>
			)}
		</div>
	);
}
