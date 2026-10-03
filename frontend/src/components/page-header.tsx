import { type ReactNode } from "react";
import { ArrowLeft } from "lucide-react";

interface PageHeaderProps {
  eyebrow?: string;
  title: string;
  subtitle?: ReactNode;
  actions?: ReactNode;
  backHref?: string;
  backLabel?: string;
  children?: ReactNode;
}

export function PageHeader({ eyebrow, title, subtitle, actions, backHref, backLabel, children }: PageHeaderProps) {
  return (
    <header className="flex items-start justify-between gap-6 pb-6 mb-6 border-b border-line">
      <div className="min-w-0 flex-1">
        {backHref && (
          <a
            href={backHref}
            className="inline-flex items-center gap-1.5 text-xs text-ink-3 hover:text-ink mb-4 transition-colors"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            {backLabel || "Back"}
          </a>
        )}
        {eyebrow && <div className="eyebrow mb-2">{eyebrow}</div>}
        <h1 className="font-display text-[var(--t-4xl,40px)] leading-tight tracking-tight text-ink">
          {title}
        </h1>
        {subtitle && <div className="mt-2.5 text-ink-3 text-[13px]">{subtitle}</div>}
        {children}
      </div>
      {actions && (
        <div className="flex items-center gap-2 shrink-0">{actions}</div>
      )}
    </header>
  );
}
