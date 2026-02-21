"use client";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { clearUser, getUser } from "@/lib/auth";
import { clearProgress, getProgress } from "@/lib/progress";
import { useRouter } from "next/navigation";

export default function Profile() {
  const [email, setEmail] = useState<string>("");
  const [username, setUsername] = useState<string>("");
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

  async function deleteAll() {
  if (!confirm("Delete account & all data on this device?")) return;

  clearProgress();
  clearUser();
  router.replace("/");
}

  function logout() {
    clearUser();
    router.replace("/");
  }

  return (
    <div className="ws-container space-y-6">
      <div>
        <h1 className="text-3xl font-extrabold tracking-tight sm:text-4xl">
          Profile
        </h1>
        <p className="mt-1 text-slate-600 text-base sm:text-[17px]">
          Manage your account and privacy
        </p>
      </div>

      {/* Account Info*/}
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

      {/* Actions */}
      <div className="space-y-3">
        <Button
          variant="outline"
          className="w-full h-12 rounded-xl text-base font-medium"
          onClick={exportData}
        >
          Export my data
        </Button>

        <Button
          variant="outline"
          className="w-full h-12 rounded-xl text-base font-medium border-red-200 text-red-600 hover:bg-red-50"
          onClick={deleteAll}
        >
          Delete account &amp; data
        </Button>
      </div>

      {/* Disclaimer/Privacy section */}
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

      {/* Logout button */}
      <Button
        variant="outline"
        className="w-full h-12 rounded-xl text-base font-medium"
        onClick={logout}
      >
        Log out
      </Button>
    </div>
  );
}