import { useState, useEffect, useRef } from "react";
import { X, Upload, ArrowRight, RotateCcw } from "lucide-react";
import { cn } from "@/lib/utils";

/* ── Phase definitions ──────────────────────────────────────── */
const PHASES = [
	{ name: "Raw Extraction", description: "Extracting text and tables from PDF" },
	{ name: "Detect Format", description: "Identifying document format" },
	{ name: "Extract Line Items", description: "AI parsing of claim line items" },
	{ name: "Validate Claim", description: "Checking totals, percentages, and duplicates" },
	{ name: "WBS Categorisation", description: "Matching items to project WBS codes" },
	{ name: "Variation Matching", description: "Linking variations against contract history" },
	{ name: "Create Records", description: "Saving claim and assessment draft" },
];

interface PhaseRuntime {
	status: "pending" | "running" | "completed" | "failed";
	events: { text: string; level: "info" | "ok" | "warn" | "err"; ts: number }[];
}

interface HarnessState {
	status: "idle" | "running" | "complete" | "error";
	phases: PhaseRuntime[];
	activeIdx: number;
	elapsedMs: number;
	errorMessage: string | null;
}

interface HarnessPanelProps {
	sessionId: string;
	onComplete: (claimId: string) => void;
	onError: (error: string) => void;
	onClose: () => void;
	onRestart?: () => void;
	onReview?: () => void;
	onRerun?: () => void;
}

/* ── PhaseGlyph ─────────────────────────────────────────────── */
function PhaseGlyph({ status }: { status: string }) {
	const base = "w-[22px] h-[22px] shrink-0 inline-flex items-center justify-center";

	if (status === "completed") {
		return (
			<span className={cn(base, "bg-brand text-white rounded-full")}>
				<svg viewBox="0 0 16 16" width="12" height="12" fill="none"
					stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
					<path d="M3 8.5l3.5 3.5L13 4.5" />
				</svg>
			</span>
		);
	}
	if (status === "failed") {
		return (
			<span className={cn(base, "bg-err text-white rounded-full")}>
				<svg viewBox="0 0 16 16" width="12" height="12" fill="none"
					stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
					<path d="M4 4l8 8M12 4l-8 8" />
				</svg>
			</span>
		);
	}
	if (status === "running") {
		return (
			<span className={cn(base, "bg-brand-tint rounded-full relative")}>
				<svg viewBox="0 0 22 22" width="22" height="22" className="absolute inset-0">
					<circle cx="11" cy="11" r="8.5" fill="none" stroke="var(--color-brand-tint-2)" strokeWidth="1.5" />
					<circle cx="11" cy="11" r="8.5" fill="none" stroke="var(--color-brand)" strokeWidth="1.5"
						strokeDasharray="14 40" strokeLinecap="round"
						style={{ transformOrigin: "11px 11px", animation: "harnessSpin 900ms linear infinite" }} />
				</svg>
			</span>
		);
	}
	// pending
	return (
		<span className={base}>
			<span className="w-3.5 h-3.5 border-[1.5px] border-dashed border-line-2 rounded-full" />
		</span>
	);
}

/* ── LogLine ────────────────────────────────────────────────── */
const LOG_COLORS: Record<string, string> = {
	info: "text-ink-3",
	ok: "text-ok",
	warn: "text-warn",
	err: "text-err",
};
const LOG_TEXT_COLORS: Record<string, string> = {
	info: "text-ink-2",
	ok: "text-ok",
	warn: "text-warn",
	err: "text-err",
};

function LogLine({ text, level, ts }: { text: string; level: string; ts: number }) {
	const tsLabel = `+${(ts / 1000).toFixed(2)}s`;
	return (
		<div className="harness-log-line grid items-baseline gap-x-1.5 py-[3px] font-mono text-[11px] leading-[1.45]"
			style={{ gridTemplateColumns: "44px 8px 1fr" }}>
			<span className="text-ink-4">{tsLabel}</span>
			<span className={cn("font-bold leading-none", LOG_COLORS[level])}>
				{level === "ok" ? "\u2713" : level === "warn" ? "\u25B2" : level === "err" ? "\u00D7" : "\u00B7"}
			</span>
			<span className={cn("break-words", LOG_TEXT_COLORS[level])}>{text}</span>
		</div>
	);
}

/* ── PhaseStrip ─────────────────────────────────────────────── */
function PhaseStrip({ phases, errored }: { phases: PhaseRuntime[]; errored: boolean }) {
	return (
		<div className="flex gap-0.5 h-[22px]">
			{phases.map((p, i) => {
				const isDone = p.status === "completed";
				const isRun = p.status === "running";
				const isFail = p.status === "failed";
				let fill = "var(--color-paper-3)";
				if (isDone) fill = "var(--color-brand)";
				else if (isRun) fill = "var(--color-brand-tint-2)";
				else if (isFail) fill = "var(--color-err)";
				const ghost = errored && p.status === "pending" ? 0.4 : 1;
				return (
					<svg key={i} viewBox="0 0 12 22" width={`${100 / phases.length}%`} height="22"
						preserveAspectRatio="none" style={{ opacity: ghost }}>
						<polygon points="0,0 12,0 12,22 0,22" fill={fill} />
						<polygon points="0,0 12,0 6,11"
							fill={isDone ? "var(--color-brand-2)" : isFail ? "color-mix(in oklch, var(--color-err) 70%, black)" : fill}
							opacity={isDone || isFail ? 0.55 : 1} />
						{isRun && <polygon points="0,0 12,0 6,11" fill="var(--color-brand)"
							style={{ animation: "harnessShimmer 1400ms ease-in-out infinite" }} />}
					</svg>
				);
			})}
		</div>
	);
}

/* ── PhaseRow ───────────────────────────────────────────────── */
function PhaseRow({ idx, phase, runtimePhase, expanded, onToggle, last }: {
	idx: number;
	phase: { name: string; description: string };
	runtimePhase: PhaseRuntime;
	expanded: boolean;
	onToggle: () => void;
	last: boolean;
}) {
	const status = runtimePhase.status;
	const titleColor = cn(
		"text-[13px] font-medium tracking-[-0.005em]",
		status === "completed" && "text-ink",
		status === "running" && "text-brand-2",
		status === "failed" && "text-err",
		status === "pending" && "text-ink-4",
	);

	return (
		<div className="relative">
			{!last && (
				<span
					className={cn(
						"absolute left-[10px] top-[26px] -bottom-2 w-px",
						status === "completed" ? "bg-brand" : "bg-line-2",
						status === "pending" && "opacity-40",
					)}
				/>
			)}

			<button
				onClick={onToggle}
				className="w-full grid items-center gap-x-3 py-1 text-left cursor-pointer bg-transparent border-none"
				style={{ gridTemplateColumns: "22px 1fr auto" }}
			>
				<PhaseGlyph status={status} />
				<span className="flex flex-col gap-px min-w-0">
					<span className={titleColor}>{phase.name}</span>
					<span className="text-[11px] text-ink-4 font-mono">
						{status === "running" ? "running\u2026"
							: status === "failed" ? "failed"
								: phase.description}
					</span>
				</span>
				<span className="text-[10px] text-ink-4 font-mono tracking-[0.06em] uppercase">
					{String(idx + 1).padStart(2, "0")}/{String(PHASES.length).padStart(2, "0")}
				</span>
			</button>

			{(status === "running" || status === "failed" || expanded) && runtimePhase.events.length > 0 && (
				<div className="ml-[34px] mt-1 mb-2 pl-3 border-l border-line">
					{runtimePhase.events.map((e, i) => (
						<LogLine key={i} text={e.text} level={e.level} ts={e.ts} />
					))}
				</div>
			)}
		</div>
	);
}

/* ── HarnessHeader ──────────────────────────────────────────── */
function HarnessHeader({ state, onClose }: { state: HarnessState; onClose: () => void }) {
	const completed = state.phases.filter(p => p.status === "completed").length;
	const title =
		state.status === "complete" ? "Claim parsed"
			: state.status === "error" ? "Processing failed"
				: "Processing claim";

	const badgeClass = cn(
		"inline-flex items-center gap-[5px] px-2 py-0.5 rounded-full text-[10px] font-medium",
		state.status === "complete" && "bg-ok-tint text-ok",
		state.status === "error" && "bg-err-tint text-err",
		state.status !== "complete" && state.status !== "error" && "bg-brand-tint text-brand",
	);
	const dotClass = cn(
		"w-[5px] h-[5px] rounded-full",
		state.status === "complete" && "bg-ok",
		state.status === "error" && "bg-err",
		state.status !== "complete" && state.status !== "error" && "bg-brand",
	);
	const badgeLabel = state.status === "complete" ? "Done" : state.status === "error" ? "Error" : "Live";

	return (
		<div className="px-[18px] pt-[18px] pb-3.5 border-b border-line">
			<div className="flex items-center justify-between mb-3">
				<span className="eyebrow">AI Reconciliation &middot; stream</span>
				<button
					onClick={onClose}
					aria-label="Close"
					className="w-[22px] h-[22px] rounded-[4px] text-ink-3 inline-flex items-center justify-center bg-transparent border-none cursor-pointer hover:bg-paper-2 hover:text-ink-2 transition-colors"
				>
					<X className="w-3.5 h-3.5" />
				</button>
			</div>

			<div className="flex items-baseline justify-between gap-3">
				<h2 className="font-display text-[26px] leading-[1.15] tracking-[-0.015em]">
					{title}
				</h2>
				<span className="font-mono-nums text-xs text-ink-3 whitespace-nowrap">
					{completed}/{PHASES.length} &middot; {(state.elapsedMs / 1000).toFixed(1)}s
				</span>
			</div>

			{/* Filename pill */}
			<div className="mt-3 flex items-center gap-2.5 p-2 rounded-[var(--radius-md)] bg-paper-2 border border-line">
				<span className="w-6 h-6 inline-flex items-center justify-center bg-surface border border-line rounded-[3px]">
					<svg viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="var(--color-ink-3)" strokeWidth="1.2">
						<path d="M4 1h6l3 3v11H4z" />
						<path d="M10 1v3h3" />
					</svg>
				</span>
				<div className="flex-1 min-w-0">
					<div className="text-xs font-medium text-ink truncate">
						Contractor progress claim
					</div>
					<div className="text-[10px] text-ink-4 font-mono tracking-[0.04em]">
						PDF &middot; streaming
					</div>
				</div>
				<span className={badgeClass}>
					<span className={dotClass} />
					{badgeLabel}
				</span>
			</div>

			{/* Phase strip */}
			<div className="mt-3.5">
				<PhaseStrip phases={state.phases} errored={state.status === "error"} />
			</div>
		</div>
	);
}

/* ── HarnessFooter ──────────────────────────────────────────── */
function HarnessFooter({ state, onCancel, onRestart, onReview, onRerun }: {
	state: HarnessState;
	onCancel: () => void;
	onRestart?: () => void;
	onReview?: () => void;
	onRerun?: () => void;
}) {
	if (state.status === "complete") {
		return (
			<div className="px-[18px] py-3.5 border-t border-line flex flex-col gap-2.5 bg-ok-tint">
				<div className="text-xs font-mono text-ok">
					&#x2713; Ready for QS review
				</div>
				<div className="flex gap-1.5">
					<button
						onClick={onReview}
						className="flex-1 inline-flex items-center justify-center gap-1.5 px-3.5 py-2 rounded-[var(--radius-md)] bg-brand text-white text-[13px] font-medium border-none cursor-pointer"
					>
						Review claim <ArrowRight className="w-3.5 h-3.5" />
					</button>
					{onRestart && (
						<button
							onClick={onRestart}
							title="Upload another"
							className="px-2.5 py-2 rounded-[var(--radius-md)] bg-transparent border border-line text-ink-3 cursor-pointer inline-flex items-center justify-center hover:bg-paper-2 transition-colors"
						>
							<Upload className="w-3.5 h-3.5" />
						</button>
					)}
				</div>
			</div>
		);
	}
	if (state.status === "error") {
		return (
			<div className="px-[18px] py-3.5 border-t border-line flex flex-col gap-2.5 bg-err-tint">
				<div className="text-xs font-mono text-err">
					&#x00D7; Processing failed &middot; claim not saved
				</div>
				<div className="flex gap-1.5">
					<button
						onClick={onRerun}
						className="flex-1 inline-flex items-center justify-center gap-1.5 px-3.5 py-2 rounded-[var(--radius-md)] bg-brand text-white text-[13px] font-medium border-none cursor-pointer"
					>
						<RotateCcw className="w-3 h-3" /> Retry
					</button>
				</div>
			</div>
		);
	}
	// running
	return (
		<div className="px-[18px] py-3 border-t border-line flex items-center justify-between bg-paper-2">
			<span className="text-[11px] text-ink-3 font-mono">
				Safe to leave &middot; processing continues in background
			</span>
			<button
				onClick={onCancel}
				className="px-2.5 py-[5px] rounded-[var(--radius-md)] bg-err-tint text-err text-xs font-medium border border-err/20 cursor-pointer"
			>
				Cancel
			</button>
		</div>
	);
}

/* ── Main HarnessPanel ──────────────────────────────────────── */
export default function HarnessPanel({
	sessionId,
	onComplete,
	onError,
	onClose,
	onRestart,
	onReview,
	onRerun,
}: HarnessPanelProps) {
	const [state, setState] = useState<HarnessState>({
		status: "running",
		phases: PHASES.map(() => ({ status: "pending", events: [] })),
		activeIdx: -1,
		elapsedMs: 0,
		errorMessage: null,
	});
	const [expandedPhases, setExpandedPhases] = useState<Record<number, boolean>>({});
	const logRef = useRef<HTMLDivElement>(null);
	const startTimeRef = useRef<number>(performance.now());
	const onCompleteRef = useRef(onComplete);
	const onErrorRef = useRef(onError);

	useEffect(() => { onCompleteRef.current = onComplete; }, [onComplete]);
	useEffect(() => { onErrorRef.current = onError; }, [onError]);

	// Elapsed timer
	useEffect(() => {
		if (state.status !== "running") return;
		let raf: number;
		const tick = () => {
			setState(s => ({ ...s, elapsedMs: performance.now() - startTimeRef.current }));
			raf = requestAnimationFrame(tick);
		};
		raf = requestAnimationFrame(tick);
		return () => cancelAnimationFrame(raf);
	}, [state.status]);

	// SSE stream
	useEffect(() => {
		const token = localStorage.getItem("token");
		const url = `/api/v1/harness/sessions/${sessionId}/stream`;
		const controller = new AbortController();
		startTimeRef.current = performance.now();

		async function startStream() {
			try {
				const response = await fetch(url, {
					headers: { Authorization: `Bearer ${token}` },
					signal: controller.signal,
				});

				if (!response.ok) {
					const text = await response.text();
					setState(s => ({ ...s, status: "error", errorMessage: `Stream failed: ${response.status}` }));
					onErrorRef.current(text);
					return;
				}

				const reader = response.body?.getReader();
				if (!reader) return;

				const decoder = new TextDecoder();
				let buffer = "";

				while (true) {
					const { done: streamDone, value } = await reader.read();
					if (streamDone) break;

					buffer += decoder.decode(value, { stream: true });
					const lines = buffer.split("\n");
					buffer = lines.pop() || "";

					for (const line of lines) {
						if (!line.startsWith("data: ")) continue;
						const payload = line.slice(6).trim();
						if (payload === "[DONE]") {
							setState(s => {
								// If harness_complete already fired, status is "complete" and claim_id was set.
								// If not, the [DONE] arrived without a claim_id — show an error.
								if (s.status === "complete") return s;
								onErrorRef.current("Processing finished without producing a claim");
								return { ...s, status: "error", errorMessage: "Processing finished without producing a claim" };
							});
							return;
						}

						try {
							const event = JSON.parse(payload);
							handleEvent(event);
						} catch {
							// skip malformed
						}
					}
				}

				// Stream ended without [DONE] or harness_complete — treat as unexpected close
				setState(s => {
					if (s.status === "running") {
						onErrorRef.current("Connection closed unexpectedly");
						return { ...s, status: "error", errorMessage: "Connection closed unexpectedly" };
					}
					return s;
				});
			} catch (err: unknown) {
				if (err instanceof Error && err.name === "AbortError") return;
				setState(s => ({ ...s, status: "error", errorMessage: "Connection lost" }));
				onErrorRef.current("Connection lost");
			}
		}

		function handleEvent(event: Record<string, unknown>) {
			const elapsed = performance.now() - startTimeRef.current;
			switch (event.type) {
				case "harness_phase_start":
					setState(s => {
						const phases = s.phases.map((p, idx) =>
							idx === (event.phase_index as number) ? { ...p, status: "running" as const } : p
						);
						return { ...s, phases, activeIdx: event.phase_index as number };
					});
					break;

				case "harness_phase_result":
					setState(s => {
						const phases = s.phases.map((p, idx) => {
							if (idx !== (event.phase_index as number)) return p;
							const newEvents = event.detail
								? [...p.events, { text: event.detail as string, level: "ok" as const, ts: elapsed }]
								: p.events;
							return { ...p, status: "completed" as const, events: newEvents };
						});
						return { ...s, phases };
					});
					break;

				case "harness_phase_error":
					setState(s => {
						const phases = s.phases.map((p, idx) => {
							if (idx !== (event.phase_index as number)) return p;
							return {
								...p, status: "failed" as const,
								events: [...p.events, { text: (event.error as string) || "Phase failed", level: "err" as const, ts: elapsed }],
							};
						});
						return { ...s, phases };
					});
					break;

				case "harness_log":
					setState(s => {
						const phaseIdx = (event.phase_index as number) ?? s.activeIdx;
						if (phaseIdx < 0) return s;
						const phases = s.phases.map((p, idx) => {
							if (idx !== phaseIdx) return p;
							return {
								...p,
								events: [...p.events, {
									text: event.message as string,
									level: (event.level as "info" | "ok" | "warn" | "err") || "info",
									ts: elapsed,
								}],
							};
						});
						return { ...s, phases };
					});
					break;

				case "harness_complete":
					setState(s => ({ ...s, status: "complete" }));
					if (event.claim_id) {
						onCompleteRef.current(event.claim_id as string);
					}
					break;

				case "harness_error":
					setState(s => ({
						...s, status: "error",
						errorMessage: event.error as string,
					}));
					onErrorRef.current(event.error as string);
					break;
			}
		}

		const timeoutId = setTimeout(() => startStream(), 0);
		return () => {
			clearTimeout(timeoutId);
			controller.abort();
		};
	}, [sessionId]);

	// Auto-expand running/failed phases
	useEffect(() => {
		setExpandedPhases(prev => {
			const next = { ...prev };
			state.phases.forEach((p, i) => {
				if (p.status === "running" || p.status === "failed") next[i] = true;
				else if (p.status === "completed" && prev[i] === undefined) next[i] = false;
			});
			return next;
		});
	}, [state.activeIdx, state.status]);

	// Autoscroll
	useEffect(() => {
		if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
	}, [state.phases]);

	return (
		<aside className="harness-fade bg-surface border border-line rounded-[var(--radius-lg)] flex flex-col min-h-0 max-h-[calc(100vh-120px)] sticky top-20">
			<HarnessHeader state={state} onClose={onClose} />

			<div ref={logRef} className="flex-1 min-h-0 overflow-y-auto px-[18px] pt-3 pb-2 flex flex-col gap-0.5">
				{PHASES.map((phase, i) => (
					<PhaseRow
						key={i}
						idx={i}
						phase={phase}
						runtimePhase={state.phases[i]}
						expanded={!!expandedPhases[i]}
						onToggle={() => setExpandedPhases(p => ({ ...p, [i]: !p[i] }))}
						last={i === PHASES.length - 1}
					/>
				))}
			</div>

			<HarnessFooter
				state={state}
				onCancel={onClose}
				onRestart={onRestart}
				onReview={onReview}
				onRerun={onRerun}
			/>
		</aside>
	);
}
