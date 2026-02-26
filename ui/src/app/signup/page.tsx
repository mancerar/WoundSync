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
    
    // FIREBASE AUTHENTICATION - COMMENTED OUT FOR NOW
    // Uncomment this block when Firebase is configured
    
    signUp(email, pw)
      .then(() => {
        setUser({ email, username });
        alert("Account created successfully! Welcome to WoundSync.");
        router.replace("/dashboard");
      })
      .catch((err) => {
        console.error(err);
        const errorCode = err?.code;
        let errorMessage = "Sign up failed";
        
        if (errorCode === "auth/email-already-in-use") {
          errorMessage = "This email is already registered. Please log in instead.";
        } else if (errorCode === "auth/invalid-email") {
          errorMessage = "Invalid email address.";
        } else if (errorCode === "auth/weak-password") {
          errorMessage = "Password is too weak. Use at least 8 characters with letters and numbers.";
        } else if (err?.message) {
          errorMessage = err.message;
        }
        
        alert(errorMessage);
      });
    
    
    // Temporary local-only signup (no Firebase)
    setUser({ email, username });
    alert("Account created successfully! Welcome to WoundSync.");
    router.replace("/dashboard");
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