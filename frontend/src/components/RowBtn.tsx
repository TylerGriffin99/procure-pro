import type { ReactNode } from "react";

const TONES = {
	ok: {
		bg: "var(--color-ok-tint)",
		color: "var(--color-ok)",
		border: "1px solid color-mix(in oklab, var(--color-ok) 25%, transparent)",
	},
	brand: {
		bg: "var(--color-brand-tint)",
		color: "var(--color-brand)",
		border: "1px solid var(--color-brand-tint-2)",
	},
	ghost: {
		bg: "var(--color-paper-3)",
		color: "var(--color-ink-2)",
		border: "1px solid var(--color-line-2)",
	},
	err: {
		bg: "var(--color-err-tint)",
		color: "var(--color-err)",
		border: "1px solid color-mix(in oklab, var(--color-err) 20%, transparent)",
	},
} as const;

interface RowBtnProps {
	tone: keyof typeof TONES;
	onClick: () => void;
	disabled?: boolean;
	children: ReactNode;
}

export function RowBtn({ tone, onClick, disabled, children }: RowBtnProps) {
	const t = TONES[tone];
	return (
		<button
			onClick={onClick}
			disabled={disabled}
			style={{
				padding: "2px 7px",
				fontSize: 10,
				borderRadius: "var(--radius-sm)",
				fontWeight: 500,
				whiteSpace: "nowrap",
				transition: "all 80ms ease",
				background: t.bg,
				color: t.color,
				border: t.border,
				opacity: disabled ? 0.5 : 1,
				cursor: disabled ? "not-allowed" : "pointer",
			}}
		>
			{children}
		</button>
	);
}
