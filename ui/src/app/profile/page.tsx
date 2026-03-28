"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { clearUser, getUser } from "@/lib/auth";
import { clearProgress, getProgress } from "@/lib/progress";
import { useRouter } from "next/navigation";
import { auth } from "@/firebase/firebase";
import {
  deleteUser,
  signOut as fbSignOut,
  EmailAuthProvider,
  reauthenticateWithCredential,
} from "firebase/auth";

export default function Profile() {
  const [email, setEmail] = useState<string>("");
  const [username, setUsername] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const router = useRouter();

  useEffect(() => {
    const u = getUser();
    if (!u) {
      router.replace("/");
      return;
    }
    setEmail(u.email);
    setUsername(u.username || "");
  }, [router]);

  function exportData() {
    const blob = new Blob(
      [JSON.stringify({ progress: getProgress() }, null, 2)],
      { type: "application/json" }
    );
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "woundsync-data.json";
    a.click();
    URL.revokeObjectURL(url);
  }

  function cleanupLocalData() {
    clearProgress();
    clearUser();
  }

  async function deleteAll() {
    if (!confirm("Delete Firebase account and all local data on this device?")) {
      return;
    }

    try {
      setBusy(true);

      const user = auth?.currentUser;

      if (!user) {
        alert("No active Firebase session found. Please sign in again, then try deleting your account.");
        return;
      }

      try {
        await deleteUser(user);
      } catch (err: any) {
        if (err?.code !== "auth/requires-recent-login") {
          throw err;
        }

        const userEmail = user.email || email;
        if (!userEmail) {
          alert("Please log out, sign back in, and then try deleting your account again.");
          return;
        }

        const password = window.prompt(
          "For security, please enter your password to confirm account deletion:"
        );

        if (!password) {
          alert("Account deletion cancelled.");
          return;
        }

        const credential = EmailAuthProvider.credential(userEmail, password);
        await reauthenticateWithCredential(user, credential);
        await deleteUser(user);
      }

      cleanupLocalData();
      router.replace("/");
    } catch (err: any) {
      const code = err?.code;

      if (
        code === "auth/wrong-password" ||
        code === "auth/invalid-credential" ||
        code === "auth/invalid-login-credentials"
      ) {
        alert("Incorrect password. Please try again.");
        return;
      }

      if (code === "auth/too-many-requests") {
        alert("Too many attempts. Please wait a bit and try again.");
        return;
      }

      alert("Could not delete account: " + (err?.message || "Unknown error"));
    } finally {
      setBusy(false);
    }
  }

  async function logout() {
    try {
      setBusy(true);

      if (auth) {
        await fbSignOut(auth);
      }

      clearUser();
      router.replace("/");
    } catch (err: any) {
      alert("Could not log out: " + (err?.message || "Unknown error"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="ws-container space-y-6">
      <Link
        href="/dashboard"
        style={{
          display: "inline-block",
          color: "#2563eb",
          textDecoration: "none",
          fontWeight: 600,
          marginBottom: 12,
        }}
      >
        ← Back to Dashboard
      </Link>

      <div>
        <h1 className="text-3xl font-extrabold tracking-tight sm:text-4xl">
          Profile
        </h1>
        <p className="mt-1 text-slate-600 text-base sm:text-[17px]">
          Manage your account and privacy
        </p>
      </div>

      <div className="ws-card p-4 space-y-3">
        <div>
          <div className="text-slate-800 text-lg font-semibold">Username</div>
          <p className="mt-1 text-slate-600 text-sm break-words">
            {username || "yourname"}
          </p>
        </div>
        <div>
          <div className="text-slate-800 text-lg font-semibold">Account email</div>
          <p className="mt-1 text-slate-600 text-sm break-words">
            {email || "you@example.com"}
          </p>
        </div>
      </div>

      <div className="space-y-3">
        <Button
          variant="outline"
          className="w-full h-12 rounded-xl text-base font-medium"
          onClick={exportData}
          disabled={busy}
        >
          Export my data
        </Button>

        <Button
          variant="outline"
          className="w-full h-12 rounded-xl text-base font-medium border-red-200 text-red-600 hover:bg-red-50"
          onClick={deleteAll}
          disabled={busy}
        >
          {busy ? "Working..." : "Delete account & data"}
        </Button>
      </div>

      <div className="ws-card p-4 space-y-2">
        <div className="text-slate-800 text-lg font-semibold">
          Disclaimer &amp; Privacy
        </div>
        <p className="text-sm text-slate-600 leading-relaxed">
          WoundSync stores your data locally on your device only. No photos or
          progress records are uploaded to a remote server. Deleting your
          account removes all stored data from this device.
        </p>
      </div>

      <Button
        variant="outline"
        className="w-full h-12 rounded-xl text-base font-medium"
        onClick={logout}
        disabled={busy}
      >
        Log out
      </Button>
    </div>
  );
}