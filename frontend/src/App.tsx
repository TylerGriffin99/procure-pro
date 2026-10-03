import { useAuth } from "@/hooks/useAuth";
import Login from "@/pages/Login";
import Dashboard from "@/pages/Dashboard";
import CreateProject from "@/pages/CreateProject";
import ProjectDetail from "@/pages/ProjectDetail";
import ClaimReviewPage from "@/pages/ClaimReviewPage";
import EditProject from "@/pages/EditProject";
import { useMemo } from "react";

function parseRoute() {
	const path = window.location.pathname;

	// /projects/new
	if (path === "/projects/new") return { page: "create-project" as const };

	// /projects/:id/claims/:claimId/review
	const reviewMatch = path.match(
		/^\/projects\/([^/]+)\/claims\/([^/]+)\/review$/
	);
	if (reviewMatch)
		return {
			page: "claim-review" as const,
			projectId: reviewMatch[1],
			claimId: reviewMatch[2],
		};

	// /projects/:id/edit
	const editMatch = path.match(/^\/projects\/([^/]+)\/edit$/);
	if (editMatch)
		return { page: "project-edit" as const, projectId: editMatch[1] };

	// /projects/:id
	const projectMatch = path.match(/^\/projects\/([^/]+)$/);
	if (projectMatch)
		return { page: "project-detail" as const, projectId: projectMatch[1] };

	return { page: "dashboard" as const };
}

export default function App() {
	const { isAuthenticated, isLoading } = useAuth();
	const route = useMemo(parseRoute, []);

	if (isLoading)
		return (
			<div className="min-h-screen flex items-center justify-center">
				Loading...
			</div>
		);
	if (!isAuthenticated) return <Login />;

	switch (route.page) {
		case "create-project":
			return <CreateProject />;
		case "project-edit":
			return <EditProject projectId={route.projectId!} />;
		case "project-detail":
			return <ProjectDetail projectId={route.projectId!} />;
		case "claim-review":
			return (
				<ClaimReviewPage
					projectId={route.projectId!}
					claimId={route.claimId!}
				/>
			);
		default:
			return <Dashboard />;
	}
}
