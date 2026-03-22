"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { auth } from "@/firebase/firebase";
import { confirmPasswordReset, verifyPasswordResetCode } from "firebase/auth";

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<div className="ws-container">Loading...</div>}>
      <ResetPasswordContent />
    </Suspense>
  );
}

function ResetPasswordContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const oobCode = useMemo(() => searchParams.get("oobCode") || "", [searchParams]);
  const [email, setEmail] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");

  useEffect(() => {
    async function validateCode() {
      if (!auth) {
        setError("Firebase auth is not enabled.");
        setLoading(false);
        return;
      }
      if (!oobCode) {
        setError("Missing reset code. Please use the link from your email.");
        setLoading(false);
        return;
      }

      try {
        const restoredEmail = await verifyPasswordResetCode(auth, oobCode);
        setEmail(restoredEmail || "");
      } catch {
        setError("This password reset link is invalid or expired. Please request a new one.");
      } finally {
        setLoading(false);
      }
    }

    validateCode();
  }, [oobCode]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();

    if (!auth) {
      setError("Firebase auth is not enabled.");
      return;
    }

    if (!newPassword || newPassword.length < 8) {
      setError("Password must be at least 8 characters long.");
      return;
    }

    if (newPassword !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setError("");
    setSuccessMessage("");
    setSubmitting(true);

    try {
      await confirmPasswordReset(auth, oobCode, newPassword);
      setSuccessMessage("Your password has been updated successfully. Redirecting to login...");
      setTimeout(() => {
        router.replace(`/?email=${encodeURIComponent(email)}`);
      }, 1200);
    } catch (err: unknown) {
      const code = (err as { code?: string })?.code;
      if (code === "auth/weak-password") {
        setError("Password is too weak. Use at least 8 characters.");
      } else if (code === "auth/expired-action-code" || code === "auth/invalid-action-code") {
        setError("This reset link is invalid or expired. Request a new one from login.");
      } else {
        setError("Could not reset password. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <div className="ws-container">
        <h1 className="text-2xl font-bold">Reset Password</h1>
        <p className="mt-3 text-slate-600">Validating your reset link...</p>
      </div>
    );
  }

  if (error && !email) {
    return (
      <div className="ws-container">
        <h1 className="text-2xl font-bold">Reset Password</h1>
        <p className="mt-3 text-red-600">{error}</p>
        <p className="mt-4 text-slate-600">
          Go back to <Link href="/" className="font-medium text-blue-600">login</Link> and request a new reset email.
        </p>
      </div>
    );
  }

  return (
    <div className="ws-container">
      <h1 className="text-3xl font-extrabold tracking-tight sm:text-4xl">Reset your password</h1>
      <p className="mt-2 text-slate-600">Account: {email}</p>

      <form onSubmit={onSubmit} className="mt-6 space-y-4">
        <Input
          className="h-12 rounded-xl text-base"
          type="password"
          placeholder="New password (min 8 chars)"
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
        />

        <Input
          className="h-12 rounded-xl text-base"
          type="password"
          placeholder="Confirm new password"
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
        />

        {error ? (
          <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        ) : null}

        {successMessage ? (
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
            {successMessage}
          </div>
        ) : null}

        <Button
          type="submit"
          className="h-12 w-full rounded-xl text-base font-semibold"
          disabled={submitting || !!successMessage}
        >
          {submitting ? "Updating password..." : "Update password"}
        </Button>
      </form>

      <p className="mt-4 text-slate-600">
        Back to <Link href="/" className="font-medium text-blue-600">login</Link>
      </p>
    </div>
  );
}
