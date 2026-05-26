/**
 * pages/RegisterPage.jsx — New account registration.
 */

import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import toast from "react-hot-toast";
import { Mic, Eye, EyeOff, ArrowRight, Loader, Check } from "lucide-react";

const PASSWORD_RULES = [
  { test: (p) => p.length >= 8,         label: "At least 8 characters"  },
  { test: (p) => /[A-Z]/.test(p),       label: "One uppercase letter"    },
  { test: (p) => /[0-9]/.test(p),       label: "One number"              },
];

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate     = useNavigate();
  const [form, setForm]       = useState({ full_name: "", email: "", password: "" });
  const [showPw, setShowPw]   = useState(false);
  const [loading, setLoading] = useState(false);
  const [errors,  setErrors]  = useState({});

  const field = (key) => ({
    value:    form[key],
    onChange: (e) => { setForm((f) => ({ ...f, [key]: e.target.value })); setErrors((er) => ({ ...er, [key]: "" })); },
  });

  const validate = () => {
    const e = {};
    if (!form.full_name.trim() || form.full_name.length < 2) e.full_name = "Name must be at least 2 characters";
    if (!form.email.trim() || !/\S+@\S+\.\S+/.test(form.email)) e.email = "Valid email required";
    if (!PASSWORD_RULES.every((r) => r.test(form.password))) e.password = "Password doesn't meet requirements";
    setErrors(e);
    return !Object.keys(e).length;
  };

  const handleSubmit = async (ev) => {
    ev.preventDefault();
    if (!validate()) return;
    setLoading(true);
    try {
      await register(form.email, form.password, form.full_name);
      toast.success("Account created! Welcome aboard.");
      navigate("/");
    } catch (err) {
      const msg = err.response?.data?.error || "Registration failed";
      toast.error(msg);
      if (msg.toLowerCase().includes("email")) setErrors({ email: msg });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-6" style={{ background: "var(--bg)" }}>
      {/* Ambient orbs */}
      <div className="fixed top-0 right-0 w-[500px] h-[500px] rounded-full pointer-events-none opacity-10"
        style={{ background: "radial-gradient(circle, #6366f1 0%, transparent 70%)", transform: "translate(30%,-30%)" }} />
      <div className="fixed bottom-0 left-0 w-96 h-96 rounded-full pointer-events-none opacity-8"
        style={{ background: "radial-gradient(circle, #10b981 0%, transparent 70%)", transform: "translate(-30%, 30%)" }} />

      <div className="w-full max-w-md animate-slide-up relative z-10">
        <div className="flex items-center gap-2 mb-8">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-brand-500 to-brand-700 flex items-center justify-center shadow-glow-brand">
            <Mic size={18} className="text-white" />
          </div>
          <span className="font-display text-lg text-[var(--text)]">Meeting Analyzer</span>
        </div>

        <h2 className="font-display text-3xl text-[var(--text)] mb-1">Create your account</h2>
        <p className="text-[var(--text-2)] mb-8">Start analyzing your meetings with AI.</p>

        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Full name */}
          <div>
            <label className="block text-sm font-medium text-[var(--text-2)] mb-1.5">Full name</label>
            <input type="text" className={`input-field ${errors.full_name ? "!border-red-500" : ""}`}
              placeholder="Jane Smith" autoComplete="name" {...field("full_name")} />
            {errors.full_name && <p className="mt-1 text-xs text-red-400">{errors.full_name}</p>}
          </div>

          {/* Email */}
          <div>
            <label className="block text-sm font-medium text-[var(--text-2)] mb-1.5">Email</label>
            <input type="email" className={`input-field ${errors.email ? "!border-red-500" : ""}`}
              placeholder="you@company.com" autoComplete="email" {...field("email")} />
            {errors.email && <p className="mt-1 text-xs text-red-400">{errors.email}</p>}
          </div>

          {/* Password + strength */}
          <div>
            <label className="block text-sm font-medium text-[var(--text-2)] mb-1.5">Password</label>
            <div className="relative">
              <input type={showPw ? "text" : "password"}
                className={`input-field pr-11 ${errors.password ? "!border-red-500" : ""}`}
                placeholder="Create a strong password" autoComplete="new-password" {...field("password")} />
              <button type="button" onClick={() => setShowPw((s) => !s)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text-3)] hover:text-[var(--text-2)] transition-colors">
                {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
            {/* Password rules */}
            {form.password && (
              <div className="mt-2 space-y-1">
                {PASSWORD_RULES.map(({ test, label }) => {
                  const ok = test(form.password);
                  return (
                    <div key={label} className={`flex items-center gap-1.5 text-xs transition-colors ${ok ? "text-green-400" : "text-[var(--text-3)]"}`}>
                      <Check size={11} className={ok ? "opacity-100" : "opacity-30"} />
                      <span>{label}</span>
                    </div>
                  );
                })}
              </div>
            )}
            {errors.password && <p className="mt-1 text-xs text-red-400">{errors.password}</p>}
          </div>

          <button type="submit" disabled={loading}
            className="btn-brand w-full flex items-center justify-center gap-2 py-3 text-sm">
            {loading ? <Loader size={16} className="animate-spin" /> : null}
            {loading ? "Creating account…" : "Create account"}
            {!loading && <ArrowRight size={16} />}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-[var(--text-2)]">
          Already have an account?{" "}
          <Link to="/login" className="text-[var(--brand-light)] font-semibold hover:underline">Sign in</Link>
        </p>
      </div>
    </div>
  );
}
