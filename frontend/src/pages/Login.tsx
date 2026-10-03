import { useState } from "react";
import { useForm } from "react-hook-form";
import { yupResolver } from "@hookform/resolvers/yup";
import * as yup from "yup";
import { useAuth } from "@/hooks/useAuth";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { FormField } from "@/components/form-field";
import { Select } from "@/components/ui/select";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { ArrowRight } from "lucide-react";

const loginSchema = yup.object({
  email: yup.string().email("Invalid email").required("Email is required"),
  password: yup.string().required("Password is required"),
});

const signUpSchema = loginSchema.shape({
  first_name: yup.string().required("First name is required"),
  last_name: yup.string().required("Last name is required"),
  country: yup.string().oneOf(["NZ", "AU"], "Select a country").required("Country is required"),
});

type SignUpValues = yup.InferType<typeof signUpSchema>;

export default function Login() {
  const { login, register: registerUser } = useAuth();
  const [isSignUp, setIsSignUp] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<SignUpValues>({
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    resolver: yupResolver(isSignUp ? signUpSchema : (loginSchema as any)),
  });

  const onSubmit = (data: SignUpValues) => {
    if (isSignUp) {
      registerUser.mutate(
        {
          email: data.email,
          password: data.password,
          first_name: data.first_name!,
          last_name: data.last_name!,
          country: data.country!,
        },
        {
          onSuccess: () => {
            login.mutate({ email: data.email, password: data.password });
          },
        }
      );
    } else {
      login.mutate({ email: data.email, password: data.password });
    }
  };

  const error = login.isError || registerUser.isError;
  const isPending = login.isPending || registerUser.isPending;
  const errorMessage = isSignUp
    ? registerUser.isError
      ? "Registration failed. Email may already be in use."
      : "Login failed after registration."
    : "Invalid credentials";

  return (
    <div className="min-h-screen grid grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)] bg-paper">
      {/* Left: brand storytelling pane */}
      <aside className="relative overflow-hidden flex flex-col p-12 px-14" style={{ background: "var(--color-brand-3)", color: "var(--color-paper)" }}>
        {/* Faceted background motif */}
        <svg viewBox="0 0 400 600" preserveAspectRatio="xMidYMid slice" className="absolute inset-0 w-full h-full opacity-10">
          <g fill="none" stroke="white" strokeWidth="0.6">
            <path d="M-20 200 L200 50 L420 280 L200 480 Z" />
            <path d="M-20 200 L200 480" />
            <path d="M200 50 L200 480" />
            <path d="M-20 200 L420 280" />
            <path d="M60 400 L260 180 L380 520" />
            <path d="M-20 460 L160 320 L300 600" />
          </g>
        </svg>

        <div className="relative z-10 flex items-center gap-3">
          <img src="/crane-256.png" alt="Procure AI" className="h-7 w-auto brightness-0 invert" />
          <span className="font-display text-[22px] tracking-[0.05em] uppercase">Procure AI</span>
        </div>

        <div className="flex-1" />

        <div className="relative z-10 max-w-[440px]">
          <div className="eyebrow mb-4" style={{ color: "rgba(255,255,255,0.5)" }}>
            Smart Quantity Surveying
          </div>
          <h2 className="font-display text-[48px] leading-[1.05] tracking-tight text-white">
            <em className="italic">Reconcile</em> every progress claim with precision.
          </h2>
          <p className="mt-5 text-sm leading-relaxed max-w-[380px]" style={{ color: "rgba(255,255,255,0.65)" }}>
            Procure AI validates totals, matches variations and flags exceptions for commercial projects — so QS's spend minutes, not days, on invoice reconciliation and payment recommendations.
          </p>
        </div>

        <div className="relative z-10 mt-14 flex gap-10">
          <MiniMetric value="98%" label="parsing accuracy" />
          <MiniMetric value="6h→20m" label="cycle time" />
          <MiniMetric value="42" label="active projects" />
        </div>

        <div className="relative z-10 mt-10 text-[11px] tracking-[0.05em]" style={{ color: "rgba(255,255,255,0.4)" }}>
          © 2026 PROCURE AI
        </div>
      </aside>

      {/* Right: form */}
      <main className="flex items-center justify-center p-12 px-16">
        <div className="w-full max-w-[380px]">
          <div className="mb-8">
            <div className="eyebrow mb-2.5">
              {isSignUp ? "Create your account" : "Welcome back"}
            </div>
            <h1 className="font-display text-4xl tracking-tight leading-tight">
              {isSignUp ? "Start auditing claims." : "Sign in to Procure AI."}
            </h1>
          </div>

          <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-3.5">
            {error && (
              <Alert variant="error">
                <AlertDescription>{errorMessage}</AlertDescription>
              </Alert>
            )}

            {isSignUp && (
              <>
                <div className="grid grid-cols-2 gap-2.5">
                  <FormField label="First name" required error={errors.first_name}>
                    <Input placeholder="First name" {...register("first_name")} />
                  </FormField>
                  <FormField label="Last name" required error={errors.last_name}>
                    <Input placeholder="Last name" {...register("last_name")} />
                  </FormField>
                </div>
                <FormField label="Country" required error={errors.country}>
                  <Select {...register("country")} defaultValue="">
                    <option value="" disabled>Select your country</option>
                    <option value="NZ">New Zealand</option>
                    <option value="AU">Australia</option>
                  </Select>
                </FormField>
              </>
            )}

            <FormField label="Email" required error={errors.email}>
              <Input type="email" placeholder="you@firm.com" {...register("email")} />
            </FormField>

            <FormField label="Password" required error={errors.password}>
              <Input type="password" placeholder="••••••••" {...register("password")} />
            </FormField>

            <Button variant="primary" size="lg" type="submit" disabled={isPending} className="w-full mt-2">
              {isPending
                ? isSignUp ? "Creating account..." : "Signing in..."
                : isSignUp ? "Create account" : "Continue"}
              {!isPending && <ArrowRight className="h-3.5 w-3.5" />}
            </Button>

            {/* Divider */}
            <div className="flex items-center gap-3 my-2.5">
              <div className="flex-1 h-px bg-line" />
              <span className="eyebrow">or</span>
              <div className="flex-1 h-px bg-line" />
            </div>

            <Button variant="secondary" size="lg" type="button" className="w-full" disabled title="Google sign-in coming soon">
              Google
            </Button>
          </form>

          <p className="mt-8 text-xs text-ink-3 text-center">
            {isSignUp ? "Already have an account?" : "Don't have an account yet?"}{" "}
            <button
              type="button"
              onClick={() => setIsSignUp(!isSignUp)}
              className="text-brand font-medium"
            >
              {isSignUp ? "Sign in" : "Request access"}
            </button>
          </p>
        </div>
      </main>
    </div>
  );
}

function MiniMetric({ value, label }: { value: string; label: string }) {
  return (
    <div>
      <div className="font-display text-[22px] text-white tracking-tight">{value}</div>
      <div className="text-[10px] tracking-[0.08em] uppercase mt-0.5" style={{ color: "rgba(255,255,255,0.5)" }}>
        {label}
      </div>
    </div>
  );
}
