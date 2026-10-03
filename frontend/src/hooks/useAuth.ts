import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "@/api/client";

interface User {
	id: string;
	email: string;
	first_name: string;
	last_name: string;
	phone_number: string | null;
	role: string;
	email_verified: boolean;
	profile_image_url: string | null;
	organization_id: string | null;
	country: string;
	currency: string;
	created_at: string | null;
}

export function useAuth() {
	const queryClient = useQueryClient();

	const { data: user, isLoading } = useQuery<User>({
		queryKey: ["auth", "me"],
		queryFn: () => api.get("/auth/me").then((r) => r.data),
		enabled: !!localStorage.getItem("token"),
		retry: false,
	});

	const login = useMutation({
		mutationFn: (creds: { email: string; password: string }) => {
			const form = new URLSearchParams();
			form.append("username", creds.email);
			form.append("password", creds.password);
			return api.post("/auth/login", form).then((r) => r.data);
		},
		onSuccess: (data) => {
			localStorage.setItem("token", data.access_token);
			queryClient.invalidateQueries({ queryKey: ["auth"] });
		},
	});

	const register = useMutation({
		mutationFn: (data: { email: string; password: string; first_name: string; last_name: string; country: string }) =>
			api.post("/auth/register", data).then((r) => r.data),
	});

	const logout = () => {
		localStorage.removeItem("token");
		queryClient.clear();
		window.location.href = "/login";
	};

	return { user, isLoading, login, register, logout, isAuthenticated: !!user };
}
