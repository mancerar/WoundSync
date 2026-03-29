"use client";

import Image from "next/image";
import Link from "next/link";
import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { getUser, setUser } from "@/lib/auth";
import { useAuth } from "@/app/providers/AuthProvider";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Mail, Lock, User as UserIcon, Eye, EyeOff } from "lucide-react";

const PAGE_TOP_PADDING = "max(calc(env(safe-area-inset-top) + 12px), 56px)";
const PAGE_BOTTOM_PADDING = "max(calc(env(safe-area-inset-bottom) + 12px), 20px)";

export default function Login() {
  return (
    <Suspense fallback={<div className="ws-container">Loading...</div>}>
      <LoginContent />
    </Suspense>
  );
}

function LoginContent() {
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [pw, setPw] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [message, setMessage] = useState<{
    type: "success" | "error" | "info";
    text: string;
  } | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isResetSending, setIsResetSending] = useState(false);
  const router = useRouter();
  const searchParams = useSearchParams();
  const {
    user: authUser,
    loading: authLoading,
    signIn,
    resetPassword,
    authEnabled,
  } = useAuth();

  useEffect(() => {
    if (!authEnabled || authLoading) return;
    if (authUser) {
      router.replace("/dashboard");
    }
  }, [authEnabled, authLoading, authUser, router]);

  useEffect(() => {
    const remembered = getUser();
    if (remembered?.email && !email) setEmail(remembered.email);
    if (remembered?.username && !username) setUsername(remembered.username);

    const emailFromQuery = searchParams.get("email") || "";
    if (emailFromQuery && !email) {
      setEmail(emailFromQuery);
    }
  }, [searchParams, email, username]);

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setMessage(null);

    if (!email) {
      setMessage({ type: "error", text: "Please enter your email." });
      return;
    }

    if (!pw) {
      setMessage({
        type: "error",
        text: "Please enter your password to continue.",
      });
      return;
    }

    if (!authEnabled) {
      setUser({ email, ...(username ? { username } : {}) });
      setMessage({
        type: "success",
        text: "Signed in successfully. Redirecting to your dashboard...",
      });
      router.replace("/dashboard");
      return;
    }

    setIsSubmitting(true);

    signIn(email, pw)
      .then(() => {
        setUser({ email, ...(username ? { username } : {}) });
        setMessage({
          type: "success",
          text: "Welcome back to WoundSync. Redirecting...",
        });
        router.replace("/dashboard");
      })
      .catch((err) => {
        const errorCode = err?.code;
        let errorMessage = "Sign in failed";

        if (errorCode === "auth/user-not-found") {
          errorMessage = "Account not found. Please create a new account.";
        } else if (errorCode === "auth/invalid-credential") {
          errorMessage =
            "Sign-in failed. Check your email/password, and make sure Email/Password sign-in is enabled in Firebase Authentication.";
        } else if (errorCode === "auth/wrong-password") {
          errorMessage = "Incorrect password. Please try again.";
        } else if (errorCode === "auth/invalid-login-credentials") {
          errorMessage =
            "Incorrect email or password. If needed, use Forgot Password to reset access.";
        } else if (errorCode === "auth/invalid-email") {
          errorMessage = "Invalid email address.";
        } else if (errorCode === "auth/too-many-requests") {
          errorMessage = "Too many failed attempts. Please try again later.";
        } else if (err?.message) {
          errorMessage = err.message;
        }

        setMessage({ type: "error", text: errorMessage });
      })
      .finally(() => {
        setIsSubmitting(false);
      });
  }

  async function onForgotPassword() {
    const targetEmail = (email || "").trim();
    setMessage(null);

    if (!targetEmail) {
      setMessage({
        type: "error",
        text: "Enter your email first, then select Forgot Password.",
      });
      return;
    }

    setIsResetSending(true);

    try {
      await resetPassword(targetEmail);
      setMessage({
        type: "success",
        text: "Password reset email sent. Check your inbox and spam folder for the reset link.",
      });
    } catch (err: unknown) {
      let errorMessage = "Could not send reset email. Please try again.";

      const code = (err as { code?: string })?.code;

      if (code === "auth/invalid-email") {
        errorMessage = "Invalid email address.";
      } else if (code === "auth/user-not-found") {
        errorMessage =
          "If an account exists for that email, a reset link will be sent.";
      } else if (code === "auth/too-many-requests") {
        errorMessage = "Too many attempts. Please try again later.";
      } else if (err instanceof Error && err.message) {
        if (err.message.includes("Password reset email is unavailable")) {
          errorMessage = "Password reset is currently unavailable.";
        } else {
          errorMessage = err.message;
        }
      }

      setMessage({ type: "error", text: errorMessage });
    } finally {
      setIsResetSending(false);
    }
  }

  return (
    <div
      className="ws-container"
      style={{
        paddingTop: PAGE_TOP_PADDING,
        paddingBottom: PAGE_BOTTOM_PADDING,
      }}
    >
      <div className="flex items-center gap-3">
        <div className="relative h-20 w-20 shrink-0">
          <Image
            src="/WoundSync Logo.png"
            alt="WoundSync"
            fill
            className="rounded-md object-contain"
            priority
          />
        </div>
        <div className="leading-tight">
          <h1 className="text-3xl font-extrabold tracking-tight sm:text-4xl">
            WoundSync
          </h1>
          <p className="text-slate-600 text-base sm:text-[17px]">
            Track your healing safely
          </p>
        </div>
      </div>

      <p className="mt-4 text-[15px] leading-6 text-slate-700">
        WoundSync lets you capture wound photos and see objective trends over
        time, including size, appearance, and overall progress. It uses
        on-device computer vision to help you monitor healing safely between
        visits.
      </p>

      <h2 className="mt-5 text-xl font-semibold text-slate-800">Log in</h2>

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

      <form onSubmit={onSubmit} className="mt-4 space-y-4">
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
            suppressHydrationWarning
            type="button"
            onClick={() => setShowPw((v) => !v)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
            aria-label={showPw ? "Hide password" : "Show password"}
          >
            {showPw ? (
              <EyeOff className="h-5 w-5" />
            ) : (
              <Eye className="h-5 w-5" />
            )}
          </button>
        </div>

        <Button
          type="submit"
          className="h-12 w-full rounded-xl text-base font-semibold"
          disabled={isSubmitting}
        >
          {isSubmitting ? "Signing in..." : "Continue"}
        </Button>

        <button
          suppressHydrationWarning
          type="button"
          onClick={onForgotPassword}
          className="text-sm font-medium text-blue-600 hover:underline disabled:cursor-not-allowed disabled:opacity-60"
          disabled={isResetSending}
        >
          {isResetSending ? "Sending reset email..." : "Forgot Password?"}
        </button>
      </form>

      <p className="mt-4 text-slate-600">
        No account?{" "}
        <Link href="/signup" className="font-medium text-blue-600">
          Sign up →
        </Link>
      </p>

      <div className="mt-4 flex flex-wrap gap-3">
        <span className="rounded-full border border-blue-100 bg-blue-50 px-4 py-1.5 text-sm text-slate-700">
          🔒 Private &amp; secure
        </span>
        <span className="rounded-full border border-blue-100 bg-blue-50 px-4 py-1.5 text-sm text-slate-700">
          🚫 Not for medical diagnosis
        </span>
      </div>
    </div>
  );
}