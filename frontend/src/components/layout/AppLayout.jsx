/**
 * components/layout/AppLayout.jsx — Sidebar + main content shell.
 * Renders on all protected routes via React Router's <Outlet />.
 */

import { useState } from "react";
import { Outlet, NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { useTheme } from "../../context/ThemeContext";
import toast from "react-hot-toast";
import {
  LayoutDashboard, Upload, Search, User, Shield,
  LogOut, Sun, Moon, Menu, X, Mic, ChevronRight,
} from "lucide-react";

const NAV = [
  { to: "/",        icon: LayoutDashboard, label: "Dashboard"  },
  { to: "/upload",  icon: Upload,          label: "Upload"      },
  { to: "/search",  icon: Search,          label: "Search"      },
  { to: "/profile", icon: User,            label: "Profile"     },
];

export default function AppLayout() {
  const { user, logout, isAdmin } = useAuth();
  const { dark, toggle }          = useTheme();
  const navigate                  = useNavigate();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  const handleLogout = async () => {
    await logout();
    toast.success("Signed out");
    navigate("/login");
  };

  const sidebarLinks = [
    ...NAV,
    ...(isAdmin ? [{ to: "/admin", icon: Shield, label: "Admin" }] : []),
  ];

  return (
    <div className="flex min-h-screen">

      {/* ── Mobile overlay ─────────────────────────────────────────────────── */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/60 lg:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* ── Sidebar ────────────────────────────────────────────────────────── */}
      <aside
        className={`
          fixed lg:sticky top-0 left-0 h-screen z-50 flex flex-col
          transition-all duration-300 ease-out
          border-r border-[var(--border)]
          ${collapsed ? "w-[68px]" : "w-[230px]"}
          ${mobileOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"}
        `}
        style={{ background: "var(--bg-2)" }}
      >
        {/* Logo */}
        <div className="flex items-center gap-3 px-4 py-5 border-b border-[var(--border)]">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-brand-500 to-brand-700 flex items-center justify-center flex-shrink-0 shadow-glow-brand">
            <Mic size={16} className="text-white" />
          </div>
          {!collapsed && (
            <span className="font-display text-[1.05rem] text-[var(--text)] tracking-tight leading-tight">
              Meeting<br />
              <span className="gradient-text">Analyzer</span>
            </span>
          )}
          <button
            onClick={() => setCollapsed((c) => !c)}
            className="ml-auto text-[var(--text-3)] hover:text-[var(--text)] transition-colors hidden lg:flex"
          >
            <ChevronRight size={16} className={`transition-transform ${collapsed ? "" : "rotate-180"}`} />
          </button>
        </div>

        {/* Nav links */}
        <nav className="flex-1 p-3 space-y-1">
          {sidebarLinks.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                `sidebar-link ${isActive ? "active" : ""} ${collapsed ? "justify-center" : ""}`
              }
              title={collapsed ? label : undefined}
              onClick={() => setMobileOpen(false)}
            >
              <Icon size={18} className="flex-shrink-0" />
              {!collapsed && <span>{label}</span>}
            </NavLink>
          ))}
        </nav>

        {/* Bottom: theme + user + logout */}
        <div className="p-3 border-t border-[var(--border)] space-y-1">
          <button
            onClick={toggle}
            className={`sidebar-link w-full ${collapsed ? "justify-center" : ""}`}
          >
            {dark ? <Sun size={18} className="flex-shrink-0" /> : <Moon size={18} className="flex-shrink-0" />}
            {!collapsed && <span>{dark ? "Light mode" : "Dark mode"}</span>}
          </button>

          {!collapsed && (
            <div className="flex items-center gap-2 px-3 py-2 rounded-xl" style={{ background: "rgba(255,255,255,0.03)" }}>
              <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-brand-400 to-brand-600 flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
                {user?.full_name?.[0]?.toUpperCase() || "U"}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-semibold text-[var(--text)] truncate">{user?.full_name}</p>
                <p className="text-[10px] text-[var(--text-3)] truncate">{user?.email}</p>
              </div>
            </div>
          )}

          <button
            onClick={handleLogout}
            className={`sidebar-link w-full text-red-400 hover:text-red-300 ${collapsed ? "justify-center" : ""}`}
          >
            <LogOut size={18} className="flex-shrink-0" />
            {!collapsed && <span>Sign out</span>}
          </button>
        </div>
      </aside>

      {/* ── Main content ───────────────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col min-w-0 min-h-screen">
        {/* Mobile topbar */}
        <header className="lg:hidden flex items-center gap-3 px-4 py-3 border-b border-[var(--border)]" style={{ background: "var(--bg-2)" }}>
          <button onClick={() => setMobileOpen(true)} className="text-[var(--text-2)]">
            <Menu size={22} />
          </button>
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-lg bg-gradient-to-br from-brand-500 to-brand-700 flex items-center justify-center">
              <Mic size={12} className="text-white" />
            </div>
            <span className="font-display text-sm gradient-text">Meeting Analyzer</span>
          </div>
        </header>

        <main className="flex-1 p-6 lg:p-8 max-w-7xl mx-auto w-full">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
