import { useEffect, useCallback, type ReactNode } from "react";
import { cn } from "@/lib/utils";

interface DialogProps {
	open: boolean;
	onClose: () => void;
	children: ReactNode;
}

function Dialog({ open, onClose, children }: DialogProps) {
	const handleEscape = useCallback(
		(e: KeyboardEvent) => {
			if (e.key === "Escape") onClose();
		},
		[onClose]
	);

	useEffect(() => {
		if (!open) return;
		window.addEventListener("keydown", handleEscape);
		return () => window.removeEventListener("keydown", handleEscape);
	}, [open, handleEscape]);

	if (!open) return null;

	return (
		<div
			className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center"
			onMouseDown={(e) => {
				if (e.target === e.currentTarget) onClose();
			}}
		>
			{children}
		</div>
	);
}

function DialogContent({
	className,
	children,
	...props
}: React.HTMLAttributes<HTMLDivElement>) {
	return (
		<div
			className={cn(
				"bg-background rounded-lg shadow-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto",
				className
			)}
			{...props}
		>
			{children}
		</div>
	);
}

function DialogHeader({
	className,
	children,
	onClose,
	...props
}: React.HTMLAttributes<HTMLDivElement> & { onClose?: () => void }) {
	return (
		<div
			className={cn("flex justify-between items-center px-6 py-4 border-b", className)}
			{...props}
		>
			<div>{children}</div>
			{onClose && (
				<button
					onClick={onClose}
					className="text-muted-foreground hover:text-foreground text-xl"
				>
					&times;
				</button>
			)}
		</div>
	);
}

function DialogTitle({
	className,
	...props
}: React.HTMLAttributes<HTMLHeadingElement>) {
	return (
		<h2 className={cn("text-lg font-semibold", className)} {...props} />
	);
}

function DialogFooter({
	className,
	...props
}: React.HTMLAttributes<HTMLDivElement>) {
	return (
		<div
			className={cn("flex justify-end gap-3 px-6 py-4 border-t", className)}
			{...props}
		/>
	);
}

export { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter };
