import { useState, useRef, useEffect, createContext, useContext, type ReactNode } from "react";
import { cn } from "@/lib/utils";

const DropdownCloseCtx = createContext<(() => void) | null>(null);

interface DropdownMenuProps {
	trigger: ReactNode;
	children: ReactNode;
	align?: "left" | "right";
	className?: string;
}

export function DropdownMenu({ trigger, children, align = "right", className }: DropdownMenuProps) {
	const [open, setOpen] = useState(false);
	const ref = useRef<HTMLDivElement>(null);

	useEffect(() => {
		function handleClickOutside(e: MouseEvent) {
			if (ref.current && !ref.current.contains(e.target as Node)) {
				setOpen(false);
			}
		}
		if (open) {
			document.addEventListener("mousedown", handleClickOutside);
		}
		return () => document.removeEventListener("mousedown", handleClickOutside);
	}, [open]);

	return (
		<DropdownCloseCtx.Provider value={() => setOpen(false)}>
			<div ref={ref} className={cn("relative inline-block", className)}>
				<div onClick={() => setOpen((o) => !o)}>{trigger}</div>
				{open && (
					<div
						className={cn(
							"absolute top-full mt-1 z-50 min-w-[140px] rounded-[var(--radius-md)] border border-line-2 bg-surface shadow-lg py-1",
							align === "right" ? "right-0" : "left-0",
						)}
					>
						{children}
					</div>
				)}
			</div>
		</DropdownCloseCtx.Provider>
	);
}

interface DropdownMenuItemProps {
	children: ReactNode;
	onClick: () => void;
	className?: string;
}

export function DropdownMenuItem({ children, onClick, className }: DropdownMenuItemProps) {
	const close = useContext(DropdownCloseCtx);
	return (
		<button
			type="button"
			className={cn(
				"w-full text-left px-3 py-1.5 text-[13px] text-ink hover:bg-paper-2 cursor-pointer transition-colors",
				className,
			)}
			onClick={() => {
				onClick();
				close?.();
			}}
		>
			{children}
		</button>
	);
}
