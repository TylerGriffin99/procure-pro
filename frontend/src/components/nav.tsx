import { useAuth } from "@/hooks/useAuth";
import { LogOut, Search, Bell } from "lucide-react";

export interface Breadcrumb {
	label: string;
	href?: string;
}

interface NavProps {
	breadcrumbs?: Breadcrumb[];
}

export function Nav({ breadcrumbs }: NavProps) {
	const { user, logout } = useAuth();

	return (
		<header
			className="sticky top-0 z-50 border-b border-line"
			style={{
				background: "color-mix(in oklab, var(--color-paper) 92%, transparent)",
				backdropFilter: "saturate(140%) blur(8px)",
			}}
		>
			<div
				className="flex items-center gap-6 px-8"
				style={{ height: 52 }}
			>
				{/* Brand */}
				<a href="/" className="flex items-center gap-2.5 shrink-0 cursor-pointer">
					<img
						src="/crane-256.png"
						alt="Procure AI"
						className="h-6 w-auto object-contain"
					/>
					<span className="font-display text-[19px] tracking-[0.04em] uppercase text-ink leading-none">
						Procure AI
					</span>
				</a>

				{/* Breadcrumbs */}
				{breadcrumbs && breadcrumbs.length > 0 && (
					<nav className="flex items-center gap-1.5 min-w-0">
						{breadcrumbs.map((crumb, i) => (
							<span key={i} className="flex items-center gap-1.5 min-w-0">
								<span className="text-ink-4 text-xs">/</span>
								{crumb.href ? (
									<a
										href={crumb.href}
										className="text-xs text-ink-3 hover:text-ink-2 transition-colors truncate max-w-[200px]"
									>
										{crumb.label}
									</a>
								) : (
									<span className="text-xs text-ink-2 truncate max-w-[200px]">
										{crumb.label}
									</span>
								)}
							</span>
						))}
					</nav>
				)}

				{/* Spacer */}
				<div className="flex-1" />

				{/* Right */}
				<div className="flex items-center gap-1.5 shrink-0">
					<button
						className="inline-flex items-center justify-center w-7 h-7 rounded-md text-ink-3 hover:bg-paper-2 hover:text-ink transition-colors"
						title="Search"
					>
						<Search className="h-3.5 w-3.5" />
					</button>
					<button
						className="relative inline-flex items-center justify-center w-7 h-7 rounded-md text-ink-3 hover:bg-paper-2 hover:text-ink transition-colors"
						title="Notifications"
					>
						<Bell className="h-3.5 w-3.5" />
					</button>

					<div className="w-px h-[18px] bg-line mx-1" />

					{user && (
						<div className="inline-flex items-center gap-2 py-1 px-2 pl-1 rounded-full border border-line">
							<div className="w-6 h-6 rounded-full bg-brand text-white inline-flex items-center justify-center text-[11px] font-medium tracking-wide">
								{(user.first_name?.[0] ?? "").toUpperCase()}
								{(user.last_name?.[0] ?? "").toUpperCase()}
							</div>
							<span className="text-xs text-ink-2">
								{user.first_name} {user.last_name}
							</span>
							<button
								onClick={logout}
								className="text-ink-4 hover:text-ink transition-colors"
								title="Sign out"
							>
								<LogOut className="h-3 w-3" />
							</button>
						</div>
					)}
				</div>
			</div>
		</header>
	);
}
