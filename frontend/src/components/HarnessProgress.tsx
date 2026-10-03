import { useState, useEffect, useRef } from "react";
import { Check, X, ChevronDown } from "lucide-react";
import { Progress } from "@/components/ui/progress";
import { Spinner } from "@/components/ui/spinner";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface PhaseInfo {
	index: number;
	name: string;
	description: string;
	status: "pending" | "running" | "completed" | "failed";
}

interface HarnessProgressProps {
	sessionId: string;
	projectId: string;
	onComplete: (claimId: string) => void;
	onError: (error: string) => void;
}

const PHASES: { name: string; description: string }[] = [
	{ name: "Raw Extraction", description: "Extracting text and tables from PDF" },
	{ name: "Detect Format", description: "Identifying document format" },
	{ name: "Extract Line Items", description: "AI parsing of claim line items" },
	{ name: "Validate Claim", description: "Checking totals, percentages, and duplicates" },
	{ name: "WBS Categorisation", description: "Matching items to WBS codes" },
	{ name: "Variation Matching", description: "Identifying and matching variations" },
	{ name: "Create Records", description: "Saving claim and assessment records" },
];

export default function HarnessProgress({
	sessionId,
	onComplete,
	onError,
}: HarnessProgressProps) {
	const [phases, setPhases] = useState<PhaseInfo[]>(
		PHASES.map((p, i) => ({ index: i, name: p.name, description: p.description, status: "pending" }))
	);
	const [error, setError] = useState<string | null>(null);
	const [done, setDone] = useState(false);
	const [expandedPhase, setExpandedPhase] = useState<number | null>(null);
	const [phaseDetails, setPhaseDetails] = useState<Record<number, string>>({});

	const onCompleteRef = useRef(onComplete);
	const onErrorRef = useRef(onError);
	useEffect(() => { onCompleteRef.current = onComplete; }, [onComplete]);
	useEffect(() => { onErrorRef.current = onError; }, [onError]);

	useEffect(() => {
		const token = localStorage.getItem("token");
		const url = `/api/harness/sessions/${sessionId}/stream`;

		const controller = new AbortController();

		async function startStream() {
			try {
				const response = await fetch(url, {
					headers: { Authorization: `Bearer ${token}` },
					signal: controller.signal,
				});

				if (!response.ok) {
					const text = await response.text();
					setError(`Stream failed: ${response.status}`);
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
							setDone(true);
							return;
						}

						try {
							const event = JSON.parse(payload);
							handleEvent(event);
						} catch {
							// skip malformed events
						}
					}
				}
			} catch (err: unknown) {
				if (err instanceof Error && err.name === "AbortError") return;
				setError("Connection lost");
				onErrorRef.current("Connection lost");
			}
		}

		function handleEvent(event: Record<string, unknown>) {
			switch (event.type) {
				case "harness_phase_start":
					setExpandedPhase(event.phase_index as number);
					setPhases((prev) =>
						prev.map((p) =>
							p.index === (event.phase_index as number)
								? { ...p, status: "running" }
								: p
						)
					);
					break;

				case "harness_phase_result":
					setPhases((prev) =>
						prev.map((p) =>
							p.index === (event.phase_index as number)
								? { ...p, status: "completed" }
								: p
						)
					);
					if (event.detail) {
						setPhaseDetails((prev) => ({
							...prev,
							[event.phase_index as number]: event.detail as string,
						}));
					}
					break;

				case "harness_phase_error":
					setPhases((prev) =>
						prev.map((p) =>
							p.index === (event.phase_index as number)
								? { ...p, status: "failed" }
								: p
						)
					);
					break;

				case "harness_complete":
					setDone(true);
					if (event.claim_id) {
						onCompleteRef.current(event.claim_id as string);
					}
					break;

				case "harness_error":
					setError(event.error as string);
					setDone(true);
					onErrorRef.current(event.error as string);
					break;
			}
		}

		// Defer stream start so StrictMode cleanup can clearTimeout
		// before the fetch fires, preventing the duplicate request.
		const timeoutId = setTimeout(() => startStream(), 0);

		return () => {
			clearTimeout(timeoutId);
			controller.abort();
		};
	}, [sessionId]);

	const completedCount = phases.filter((p) => p.status === "completed").length;
	const progressPct = (completedCount / phases.length) * 100;

	const progressIndicatorClass = error
		? "bg-red-500"
		: done
			? "bg-emerald-500"
			: "bg-primary";

	return (
		<div className="space-y-4">
			{/* Header */}
			<div className="flex items-center justify-between">
				<h3 className="font-semibold text-ink-1">
					{done && !error
						? "Claim Parsed Successfully"
						: error
							? "Processing Failed"
							: "Processing Claim..."}
				</h3>
				<Badge variant="muted">
					{completedCount}/{phases.length} phases
				</Badge>
			</div>

			{/* Progress bar */}
			<Progress value={progressPct} indicatorClassName={progressIndicatorClass} />

			{/* Phase cards */}
			<div className="space-y-2">
				{phases.map((phase) => {
					const isExpanded = expandedPhase === phase.index;
					const borderColor =
						phase.status === "running"
							? "border-brand/40 bg-brand-tint/50"
							: phase.status === "completed"
								? "border-emerald-400/30 bg-emerald-50/30"
								: phase.status === "failed"
									? "border-red-400/30 bg-red-50/30"
									: "border-line bg-white";

					return (
						<div
							key={phase.index}
							className={cn(
								"rounded-lg border overflow-hidden transition-all duration-300",
								borderColor
							)}
						>
							{/* Phase header */}
							<button
								onClick={() => setExpandedPhase(isExpanded ? null : phase.index)}
								className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-paper-2/50 transition-colors"
							>
								{/* Status icon */}
								<div className="flex-shrink-0">
									{phase.status === "completed" && (
										<div className="w-6 h-6 flex items-center justify-center rounded-full bg-emerald-100">
											<Check className="w-3.5 h-3.5 text-emerald-600" strokeWidth={2.5} />
										</div>
									)}
									{phase.status === "running" && (
										<Spinner size="sm" className="border-blue-500 border-t-transparent" />
									)}
									{phase.status === "failed" && (
										<div className="w-6 h-6 flex items-center justify-center rounded-full bg-red-100">
											<X className="w-3.5 h-3.5 text-err" strokeWidth={2.5} />
										</div>
									)}
									{phase.status === "pending" && (
										<div className="w-6 h-6 rounded-full border-2 border-line" />
									)}
								</div>

								{/* Phase name */}
								<div className="flex-1 min-w-0">
									<span
										className={cn(
											"text-sm font-medium",
											phase.status === "completed" && "text-emerald-700",
											phase.status === "running" && "text-blue-700",
											phase.status === "failed" && "text-err",
											phase.status === "pending" && "text-ink-3"
										)}
									>
										{phase.name}
									</span>
								</div>

								{/* Chevron */}
								<ChevronDown
									className={cn(
										"w-4 h-4 text-ink-3 transition-transform duration-200",
										isExpanded && "rotate-180"
									)}
								/>
							</button>

							{/* Expanded detail */}
							{isExpanded && (
								<div className="px-4 pb-3 border-t border-line">
									<p className="text-xs text-ink-3 mt-2">{phase.description}</p>
									{phaseDetails[phase.index] && (
										<p className="text-xs text-ink-2 mt-1 font-medium">
											{phaseDetails[phase.index]}
										</p>
									)}
									{phase.status === "running" && (
										<div className="flex items-center gap-2 mt-2 text-xs text-blue-600">
											<Spinner size="sm" className="border-blue-500 border-t-transparent" />
											<span>In progress...</span>
										</div>
									)}
								</div>
							)}
						</div>
					);
				})}
			</div>

			{/* Error display */}
			{error && (
				<Alert variant="error">
					<AlertDescription>{error}</AlertDescription>
				</Alert>
			)}

			{/* Success */}
			{done && !error && (
				<Alert variant="success">
					<AlertDescription>Redirecting to review page...</AlertDescription>
				</Alert>
			)}
		</div>
	);
}
