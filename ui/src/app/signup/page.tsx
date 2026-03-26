"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { setUser } from "@/lib/auth";
import { useAuth } from "@/app/providers/AuthProvider";
import { auth } from "@/firebase/firebase";
import Link from "next/link";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Mail, Lock, User as UserIcon, Eye, EyeOff } from "lucide-react";

export default function Signup() {
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [pw, setPw] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error" | "info"; text: string } | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const router = useRouter();
  const { signUp, authEnabled } = useAuth();

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setMessage(null);

    if (!username || !email || pw.length < 8) {
      setMessage({
        type: "error",
        text: "Please enter username, email, and a password with at least 8 characters.",
      });
      return;
    }

    if (!authEnabled) {
      setUser({ email, username });
      setMessage({
        type: "success",
        text: "Account created successfully. Welcome to WoundSync!",
      });
      router.replace("/dashboard");
      return;
    }

    setIsSubmitting(true);

    signUp(email, pw)
      .then(async () => {
        if (authEnabled && auth?.currentUser) {
          await auth.currentUser.getIdToken(true);
        }

        setUser({ email, username });
        setMessage({
          type: "success",
          text: "Account created successfully. Welcome to WoundSync!",
        });
        router.replace("/dashboard");
        router.refresh();
      })
      .catch((err) => {
        const errorCode = err?.code;
        let errorMessage = "Sign up failed";

        if (errorCode === "auth/email-already-in-use") {
          errorMessage = "This email is already registered. Redirecting you to login...";
          setMessage({ type: "info", text: errorMessage });
          router.replace(`/?email=${encodeURIComponent(email)}`);
          return;
        } else if (errorCode === "auth/invalid-email") {
          errorMessage = "Invalid email address.";
        } else if (errorCode === "auth/weak-password") {
          errorMessage = "Password is too weak. Use at least 8 characters with letters and numbers.";
        } else if (err?.message) {
          errorMessage = err.message;
        }

        setMessage({ type: "error", text: errorMessage });
      })
      .finally(() => {
        setIsSubmitting(false);
      });
  }

  return (
    <div className="ws-container">
      <div className="leading-tight">
        <h1 className="text-3xl font-extrabold tracking-tight sm:text-4xl">
          Create account
        </h1>
        <p className="mt-1 text-slate-600 text-base sm:text-[17px]">
          It takes less than a minute
        </p>
      </div>

      {message ? (
        <div
          className={`mt-4 rounded-xl border px-4 py-3 text-sm ${
            message.type === "success"
              ? "border-emerald-200 bg-emerald-50 text-emerald-800"
              : message.type === "error"
                ? "border-red-200 bg-red-50 text-red-700"
                : "border-blue-200 bg-blue-50 text-blue-700"
          }`}
        >
          {message.text}
        </div>
      ) : null}

      <form onSubmit={onSubmit} className="mt-6 space-y-4">
        <div className="relative">
          <UserIcon className="pointer-events-none absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-400" />
          <Input
            className="h-12 rounded-xl pl-10 text-base"
            placeholder="Username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoCapitalize="none"
            autoCorrect="off"
          />
        </div>

        <div className="relative">
          <Mail className="pointer-events-none absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-400" />
          <Input
            className="h-12 rounded-xl pl-10 text-base"
            type="email"
            inputMode="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoCapitalize="none"
            autoCorrect="off"
          />
        </div>

        <div className="relative">
          <Lock className="pointer-events-none absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-400" />
          <Input
            className="h-12 rounded-xl pl-10 pr-11 text-base"
            type={showPw ? "text" : "password"}
            placeholder="Password"
            value={pw}
            onChange={(e) => setPw(e.target.value)}
          />
          <button
            type="button"
            aria-label={showPw ? "Hide password" : "Show password"}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400"
            onClick={() => setShowPw((s) => !s)}
          >
            {showPw ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
          </button>
        </div>

        <Button
          type="submit"
          className="w-full h-12 rounded-xl text-base font-medium"
          disabled={isSubmitting}
        >
          {isSubmitting ? "Creating account..." : "Create account"}
        </Button>
      </form>

      <p className="mt-6 text-sm text-slate-600">
        Already have an account?{" "}
        <Link href="/" className="text-blue-600 hover:underline font-medium">
          Log in
        </Link>
      </p>
    </div>
  );
}