import { useState } from "react";
import { formatCurrency } from "@/components/currency-cell";
import { RowBtn } from "@/components/RowBtn";

interface InterimAdjustPopoverProps {
    description: string;
    previouslyPaid: string;
    existingComment: string | null;
    onConfirm: (agreedTotal: number, comments: string | null) => void;
    onCancel: () => void;
    isPending: boolean;
}

export function InterimAdjustPopover({
    description,
    previouslyPaid,
    existingComment,
    onConfirm,
    onCancel,
    isPending,
}: InterimAdjustPopoverProps) {
    const prevPaid = Number(previouslyPaid);
    const [agreedTotal, setAgreedTotal] = useState<string>(previouslyPaid);
    const [comment, setComment] = useState<string>(existingComment || "");

    const difference = Number(agreedTotal) - prevPaid;
    const fmt = formatCurrency;

    return (
        <div
            style={{
                background: "var(--color-surface)",
                border: "1px solid var(--color-line-2)",
                borderRadius: "var(--radius-lg)",
                padding: 20,
                minWidth: 340,
                boxShadow: "0 8px 32px rgba(0,0,0,0.12)",
            }}
        >
            <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 12 }}>
                Adjust interim
            </div>
            <div style={{ fontSize: 12, color: "var(--color-ink-3)", marginBottom: 16 }}>
                {description}
            </div>

            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 8 }}>
                <span style={{ color: "var(--color-ink-3)" }}>Previously paid</span>
                <span className="font-mono-nums" style={{ fontWeight: 500 }}>
                    ${fmt(previouslyPaid)}
                </span>
            </div>

            <div style={{ marginBottom: 12 }}>
                <label style={{ fontSize: 11, color: "var(--color-ink-3)", display: "block", marginBottom: 4 }}>
                    Agreed total
                </label>
                <input
                    type="number"
                    step="0.01"
                    value={agreedTotal}
                    autoFocus
                    onChange={(e) => setAgreedTotal(e.target.value)}
                    style={{
                        width: "100%",
                        padding: "6px 8px",
                        textAlign: "right",
                        fontFamily: "var(--font-mono)",
                        fontSize: 13,
                        border: "1px solid var(--color-brand)",
                        borderRadius: 4,
                        outline: 0,
                        background: "var(--color-surface)",
                    }}
                />
            </div>

            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 12 }}>
                <span style={{ color: "var(--color-ink-3)" }}>Difference this period</span>
                <span
                    className="font-mono-nums"
                    style={{
                        fontWeight: 600,
                        color: difference >= 0 ? "var(--color-ok)" : "var(--color-err)",
                    }}
                >
                    {difference >= 0 ? "+" : "-"}${fmt(String(Math.abs(difference)))}
                </span>
            </div>

            <div style={{ marginBottom: 16 }}>
                <label style={{ fontSize: 11, color: "var(--color-ink-3)", display: "block", marginBottom: 4 }}>
                    Comment (optional)
                </label>
                <input
                    type="text"
                    value={comment}
                    onChange={(e) => setComment(e.target.value)}
                    placeholder="e.g. Paid on account"
                    style={{
                        width: "100%",
                        padding: "6px 8px",
                        fontSize: 12,
                        border: "1px solid var(--color-line-2)",
                        borderRadius: 4,
                        outline: 0,
                        background: "var(--color-surface)",
                    }}
                />
            </div>

            <div style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}>
                <RowBtn tone="ghost" onClick={onCancel}>
                    Cancel
                </RowBtn>
                <RowBtn
                    tone="brand"
                    onClick={() => onConfirm(Number(agreedTotal), comment || null)}
                    disabled={isPending}
                >
                    {isPending ? "Saving..." : "Confirm"}
                </RowBtn>
            </div>
        </div>
    );
}
