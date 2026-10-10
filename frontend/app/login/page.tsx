"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { LogIn, UserPlus, ArrowLeft, Loader2, AlertCircle } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const { login, register } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (mode === "register" && password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }
    if (password.length < 6) {
      setError("Password must be at least 6 characters");
      return;
    }

    setIsLoading(true);
    try {
      if (mode === "login") {
        await login(email, password);
      } else {
        await register(name, email, password);
      }
      router.push("/");
    } catch (err: any) {
      setError(err.message || "Something went wrong");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="login-container min-h-screen flex items-center justify-center bg-[#f8fafc] px-4 relative overflow-hidden">
      {/* Ambient background glows */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -top-40 -left-40 w-96 h-96 rounded-full bg-blue-100/60 blur-3xl"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -bottom-40 -right-40 w-96 h-96 rounded-full bg-sky-100/60 blur-3xl"
      />

      <div className="w-full max-w-md nova-glass-card rounded-3xl p-8 sm:p-10 relative z-10">
        {/* NOVA Branding */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gradient-to-tr from-blue-600 to-sky-400 text-white font-extrabold text-2xl shadow-[0_6px_20px_rgba(37,99,235,0.3)] mb-4">
            N
          </div>
          <h1 className="text-2xl font-bold tracking-[0.25em] text-slate-900 uppercase">
            NOVA
          </h1>
          <p className="text-xs font-semibold tracking-[0.2em] text-slate-400 uppercase mt-1">
            VOICE AI ASSISTANT
          </p>
        </div>

        {/* Mode Title */}
        <h2 className="text-lg font-semibold text-slate-800 text-center mb-6">
          {mode === "login" ? "Sign in" : "Create account"}
        </h2>

        {/* Error Banner */}
        {error && (
          <div className="mb-4 px-4 py-2.5 rounded-xl bg-red-50 border border-red-200 text-xs font-medium text-red-600 flex items-center gap-2 animate-fadeIn">
            <AlertCircle size={14} />
            {error}
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {mode === "register" && (
            <div>
              <label
                htmlFor="name"
                className="block text-xs font-medium text-slate-700 mb-1.5 ml-1"
              >
                Name
              </label>
              <input
                id="name"
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Your name"
                className="nova-input"
              />
            </div>
          )}

          <div>
            <label
              htmlFor="email"
              className="block text-xs font-medium text-slate-700 mb-1.5 ml-1"
            >
              Email
            </label>
            <input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="name@example.com"
              className="nova-input"
            />
          </div>

          <div>
            <label
              htmlFor="password"
              className="block text-xs font-medium text-slate-700 mb-1.5 ml-1"
            >
              Password
            </label>
            <input
              id="password"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="nova-input"
            />
          </div>

          {mode === "register" && (
            <div>
              <label
                htmlFor="confirmPassword"
                className="block text-xs font-medium text-slate-700 mb-1.5 ml-1"
              >
                Confirm password
              </label>
              <input
                id="confirmPassword"
                type="password"
                required
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="••••••••"
                className="nova-input"
              />
            </div>
          )}

          <div className="pt-2">
            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-3 px-4 rounded-xl bg-blue-600 hover:bg-blue-700 active:scale-[0.99] text-white font-medium text-sm transition-all shadow-[0_4px_16px_rgba(37,99,235,0.25)] flex items-center justify-center gap-2 cursor-pointer disabled:opacity-70"
            >
              {isLoading ? (
                <Loader2 size={18} className="animate-spin" />
              ) : mode === "login" ? (
                <>
                  <LogIn size={16} />
                  Sign In
                </>
              ) : (
                <>
                  <UserPlus size={16} />
                  Create Account
                </>
              )}
            </button>
          </div>

          {/* Toggle mode */}
          <div className="text-center pt-2">
            {mode === "login" ? (
              <p className="text-xs text-slate-500">
                Don&apos;t have an account?{" "}
                <button
                  type="button"
                  onClick={() => {
                    setMode("register");
                    setError("");
                  }}
                  className="text-blue-600 hover:text-blue-700 font-medium transition-colors cursor-pointer"
                >
                  Create account
                </button>
              </p>
            ) : (
              <p className="text-xs text-slate-500">
                Already have an account?{" "}
                <button
                  type="button"
                  onClick={() => {
                    setMode("login");
                    setError("");
                  }}
                  className="text-blue-600 hover:text-blue-700 font-medium transition-colors cursor-pointer"
                >
                  Sign in
                </button>
              </p>
            )}
          </div>
        </form>

        <div className="mt-8 text-center">
          <Link
            href="/"
            className="text-[11px] text-slate-400 hover:text-blue-600 transition-colors inline-flex items-center gap-1"
          >
            <ArrowLeft size={12} />
            Back to NOVA Home
          </Link>
        </div>
      </div>
    </div>
  );
}
