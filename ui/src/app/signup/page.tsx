"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { setUser } from "@/lib/auth";
import { useAuth } from "@/app/providers/AuthProvider";
import Link from "next/link";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Mail, Lock, User as UserIcon } from "lucide-react";

export default function Signup() {
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [pw, setPw] = useState("");
  const router = useRouter();
  const { signUp } = useAuth();

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!username || !email || pw.length < 8)
      return alert("Enter username, email & 8+ char password");
    // Create account in Firebase then mirror to local storage
    signUp(email, pw)
      .then(() => {
        setUser({ email, username });
        router.replace("/dashboard");
      })
      .catch((err) => {
        console.error(err);
        alert("Sign up failed: " + (err?.message ?? err));
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

      {/* Form */}
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
            className="h-12 rounded-xl pl-10 text-base"
            type="password"
            placeholder="Password (min 8 chars)"
            value={pw}
            onChange={(e) => setPw(e.target.value)}
          />
        </div>

        <Button type="submit" className="h-12 w-full rounded-xl text-base font-semibold">
          Create account
        </Button>
      </form>

      {/* Auth link */}
      <p className="mt-4 text-slate-600">
        Already have an account?{" "}
        <Link href="/" className="font-medium text-blue-600">
          Log in →
        </Link>
      </p>
    </div>
  );
}