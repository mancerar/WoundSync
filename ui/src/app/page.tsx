"use client";

import Image from "next/image";
import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { setUser } from "@/lib/auth";
import { useAuth } from "@/app/providers/AuthProvider";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Mail, Lock, User as UserIcon } from "lucide-react";

export default function Login() {
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [pw, setPw] = useState("");
  const router = useRouter();
  const { signIn } = useAuth();

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!email || !username) return alert("Enter email and username");
    if (!pw) return alert("Enter password");
    
    // FIREBASE AUTHENTICATION - COMMENTED OUT FOR NOW
    // Uncomment this block when Firebase is configured
    /*
    signIn(email, pw)
      .then(() => {
        setUser({ email, username });
        router.replace("/dashboard");
      })
      .catch((err) => {
        console.error(err);
        const errorCode = err?.code;
        let errorMessage = "Sign in failed";
        
        if (errorCode === "auth/user-not-found" || errorCode === "auth/invalid-credential") {
          errorMessage = "Account not found. Please create a new account.";
        } else if (errorCode === "auth/wrong-password") {
          errorMessage = "Incorrect password. Please try again.";
        } else if (errorCode === "auth/invalid-email") {
          errorMessage = "Invalid email address.";
        } else if (errorCode === "auth/too-many-requests") {
          errorMessage = "Too many failed attempts. Please try again later.";
        } else if (err?.message) {
          errorMessage = err.message;
        }
        
        alert(errorMessage);
      });
    */
    
    // Temporary local-only login (no Firebase)
    // Temporary local-only login (no Firebase)
    setUser({ email, username });
    router.replace("/dashboard");
  }

  return (
    <div className="ws-container">
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

      {/* About */}
      <p className="mt-4 text-[15px] leading-6 text-slate-700">
        WoundSync lets you capture wound photos and see objective trends over
        time, including size, appearance, and overall progress. It uses
        on-device computer vision to help you monitor healing safely between
        visits.
      </p>

      {/* Log in */}
      <h2 className="mt-5 text-xl font-semibold text-slate-800">
        Log in
      </h2>

      {/* Form */}
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
            className="h-12 rounded-xl pl-10 text-base"
            type="password"
            placeholder="Password"
            value={pw}
            onChange={(e) => setPw(e.target.value)}
          />
        </div>

        <Button
          type="submit"
          className="h-12 w-full rounded-xl text-base font-semibold"
        >
          Continue
        </Button>
      </form>

      {/* Auth link */}
      <p className="mt-4 text-slate-600">
        No account?{" "}
        <Link href="/signup" className="font-medium text-blue-600">
          Sign up →
        </Link>
      </p>

      {/* Badges */}
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