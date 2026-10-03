import { useState, useRef, useEffect } from "react";
import { cn } from "@/lib/utils";
import { ChevronsUpDown } from "lucide-react";

interface ComboboxOption {
	value: string;
	label: string;
}

interface ComboboxProps {
	options: ComboboxOption[];
	value: string;
	onChange: (value: string) => void;
	placeholder?: string;
	searchPlaceholder?: string;
	emptyLabel?: string;
	className?: string;
}

function Combobox({
	options,
	value,
	onChange,
	placeholder = "Select...",
	searchPlaceholder = "Search...",
	emptyLabel = "No results",
	className,
}: ComboboxProps) {
	const [open, setOpen] = useState(false);
	const [search, setSearch] = useState("");
	const containerRef = useRef<HTMLDivElement>(null);
	const inputRef = useRef<HTMLInputElement>(null);

	const filtered = search
		? options.filter((o) => o.label.toLowerCase().includes(search.toLowerCase()))
		: options;

	const selected = options.find((o) => o.value === value);

	useEffect(() => {
		if (open && inputRef.current) inputRef.current.focus();
	}, [open]);

	useEffect(() => {
		function handleClickOutside(e: MouseEvent) {
			if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
				setOpen(false);
				setSearch("");
			}
		}
		if (open) {
			document.addEventListener("mousedown", handleClickOutside);
			return () => document.removeEventListener("mousedown", handleClickOutside);
		}
	}, [open]);

	const handleSelect = (newValue: string) => {
		onChange(newValue);
		setOpen(false);
		setSearch("");
	};

	return (
		<div ref={containerRef} className={cn("relative", className)}>
			{open ? (
				<>
					<input
						ref={inputRef}
						type="text"
						value={search}
						onChange={(e) => setSearch(e.target.value)}
						placeholder={searchPlaceholder}
						className="w-full text-sm px-3 py-1.5 border border-input rounded-md bg-background focus:outline-none focus:ring-1 focus:ring-ring"
					/>
					<div className="absolute z-20 top-full left-0 mt-1 w-full max-h-48 overflow-y-auto bg-popover border rounded-md shadow-lg">
						<button
							type="button"
							onClick={() => handleSelect("")}
							className="w-full text-left px-3 py-1.5 text-xs text-muted-foreground hover:bg-accent"
						>
							{placeholder}
						</button>
						{filtered.map((opt) => (
							<button
								key={opt.value}
								type="button"
								onClick={() => handleSelect(opt.value)}
								className={cn(
									"w-full text-left px-3 py-1.5 text-xs hover:bg-accent",
									opt.value === value && "bg-accent font-medium"
								)}
							>
								{opt.label}
							</button>
						))}
						{filtered.length === 0 && (
							<div className="px-3 py-2 text-xs text-muted-foreground">{emptyLabel}</div>
						)}
					</div>
				</>
			) : (
				<button
					type="button"
					onClick={() => setOpen(true)}
					className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
				>
					<span className="truncate">
						{selected ? selected.label : <span className="italic">{placeholder}</span>}
					</span>
					<ChevronsUpDown className="h-3 w-3 shrink-0 opacity-50" />
				</button>
			)}
		</div>
	);
}

export { Combobox };
export type { ComboboxOption };
