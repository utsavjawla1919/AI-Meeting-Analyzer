/**
 * pages/LoginPage.jsx — Authentication login page.
 */

import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import toast from "react-hot-toast";
import { Mic, Eye, EyeOff, ArrowRight, Loader } from "lucide-react";

export default function LoginPage() {
  const { login }    = useAuth();
  const navigate     = useNavigate();
  const [form, setForm]       = useState({ email: "", password: "" });
  const [showPw, setShowPw]   = useState(false);
  const [loading, setLoading] = useState(false);
  const [errors,  setErrors]  = useState({});

  const validate = () => {
    const e = {};
    if (!form.email.trim())    e.email    = "Email is required";
    if (!form.password)        e.password = "Password is required";
    setErrors(e);
    return !Object.keys(e).length;
  };

  const handleSubmit = async (ev) => {
    ev.preventDefault();
    if (!validate()) return;
    setLoading(true);
    try {
      await login(form.email, form.password);
      toast.success("Welcome back!");
      navigate("/");
    } catch (err) {
      const msg = err.response?.data?.error || "Login failed";
      toast.error(msg);
      if (msg.toLowerCase().includes("password")) setErrors({ password: msg });
      else setErrors({ email: msg });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex" style={{ background: "var(--bg)" }}>
      {/* Left — branding panel */}
      <div className="hidden lg:flex flex-col justify-between w-[46%] p-12 relative overflow-hidden"
        style={{ background: "var(--bg-2)", borderRight: "1px solid var(--border)" }}>

        {/* Decorative orb */}
        <div className="absolute -top-32 -left-32 w-96 h-96 rounded-full opacity-20 animate-spin-slow"
          style={{ background: "radial-gradient(circle, #6366f1 0%, transparent 70%)" }} />
        <div className="absolute -bottom-24 -right-24 w-72 h-72 rounded-full opacity-15"
          style={{ background: "radial-gradient(circle, #10b981 0%, transparent 70%)" }} />

        <div className="relative z-10 flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-brand-500 to-brand-700 flex items-center justify-center shadow-glow-brand">
            <Mic size={20} className="text-white" />
          </div>
          <span className="font-display text-xl text-[var(--text)]">Meeting Analyzer</span>
        </div>

        <div className="relative z-10 space-y-6">
          <h1 className="font-display text-5xl leading-tight text-[var(--text)]">
            Turn meetings into<br />
            <span className="gradient-text">actionable insights.</span>
          </h1>
          <p className="text-[var(--text-2)] text-lg leading-relaxed">
            Upload your meeting recordings. Get AI-generated summaries,
            action items, decisions, and sentiment analysis — instantly.
          </p>
          <div className="flex gap-6">
            {[["🎙️","STT via Whisper"], ["🧠","NLP Analysis"], ["📊","Sentiment Charts"]].map(([e,l]) => (
              <div key={l} className="flex items-center gap-2 text-sm text-[var(--text-3)]">
                <span>{e}</span><span>{l}</span>
              </div>
            ))}
          </div>
        </div>

        <p className="relative z-10 text-xs text-[var(--text-3)]">
          © 2025 AI Meeting Analyzer. All rights reserved.
        </p>
      </div>

      {/* Right — form */}
      <div className="flex-1 flex items-center justify-center p-6">
        <div className="w-full max-w-md animate-slide-up">

          {/* Mobile logo */}
          <div className="flex items-center gap-2 mb-8 lg:hidden">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-brand-500 to-brand-700 flex items-center justify-center">
              <Mic size={16} className="text-white" />
            </div>
            <span className="font-display text-lg gradient-text">Meeting Analyzer</span>
          </div>

          <h2 className="font-display text-3xl text-[var(--text)] mb-1">Welcome back</h2>
          <p className="text-[var(--text-2)] mb-8">Sign in to your account to continue.</p>

          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Email */}
            <div>
              <label className="block text-sm font-medium text-[var(--text-2)] mb-1.5">Email</label>
              <input
                type="email"
                className={`input-field ${errors.email ? "!border-red-500 !shadow-[0_0_0_3px_rgba(239,68,68,0.15)]" : ""}`}
                placeholder="you@company.com"
                value={form.email}
                onChange={(e) => { setForm((f) => ({ ...f, email: e.target.value })); setErrors((er) => ({ ...er, email: "" })); }}
                autoComplete="email"
              />
              {errors.email && <p className="mt-1 text-xs text-red-400">{errors.email}</p>}
            </div>

            {/* Password */}
            <div>
              <label className="block text-sm font-medium text-[var(--text-2)] mb-1.5">Password</label>
              <div className="relative">
                <input
                  type={showPw ? "text" : "password"}
                  className={`input-field pr-11 ${errors.password ? "!border-red-500 !shadow-[0_0_0_3px_rgba(239,68,68,0.15)]" : ""}`}
                  placeholder="••••••••"
                  value={form.password}
                  onChange={(e) => { setForm((f) => ({ ...f, password: e.target.value })); setErrors((er) => ({ ...er, password: "" })); }}
                  autoComplete="current-password"
                />
                <button type="button" onClick={() => setShowPw((s) => !s)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text-3)] hover:text-[var(--text-2)] transition-colors">
                  {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
              {errors.password && <p className="mt-1 text-xs text-red-400">{errors.password}</p>}
            </div>

            <button type="submit" disabled={loading}
              className="btn-brand w-full flex items-center justify-center gap-2 py-3 text-sm">
              {loading ? <Loader size={16} className="animate-spin" /> : null}
              {loading ? "Signing in…" : "Sign in"}
              {!loading && <ArrowRight size={16} />}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-[var(--text-2)]">
            Don't have an account?{" "}
            <Link to="/register" className="text-[var(--brand-light)] font-semibold hover:underline">
              Create one
            </Link>
          </p>

          {/* Demo credentials */}
          <div className="mt-6 p-4 rounded-xl border border-[var(--border)] glass text-center">
            <p className="text-xs text-[var(--text-3)] mb-2">Demo credentials</p>
            <p className="text-xs text-[var(--text-2)] font-mono">demo@meetinganalyzer.app</p>
            <p className="text-xs text-[var(--text-2)] font-mono">Admin@1234</p>
          </div>
        </div>
      </div>
    </div>
  );
}
