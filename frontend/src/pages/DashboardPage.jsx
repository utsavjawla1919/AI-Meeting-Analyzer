/**
 * pages/DashboardPage.jsx — Main dashboard with stats, charts, and meeting list.
 */

import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth }           from "../context/AuthContext";
import { useMeetings, useDashboardStats } from "../hooks/useMeetings";
import { meetingsAPI }       from "../services/api";
import toast from "react-hot-toast";
import { format, formatDistanceToNow } from "date-fns";
import {
  Clock, CheckCircle, AlertCircle, TrendingUp, Upload, ArrowRight,
  Trash2, MoreVertical, Loader, Search, Filter, RefreshCw,
} from "lucide-react";
import SentimentDoughnutChart from "../components/charts/SentimentDoughnutChart";
import WeeklyBarChart         from "../components/charts/WeeklyBarChart";

// ── Stat card ──────────────────────────────────────────────────────────────────
function StatCard({ label, value, icon: Icon, color, sub }) {
  return (
    <div className="glass glass-hover rounded-2xl p-5 cursor-default">
      <div className="flex items-start justify-between mb-3">
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${color}`}>
          <Icon size={18} className="text-white" />
        </div>
      </div>
      <p className="text-2xl font-bold text-[var(--text)] font-display">{value ?? "—"}</p>
      <p className="text-sm text-[var(--text-2)] mt-0.5">{label}</p>
      {sub && <p className="text-xs text-[var(--text-3)] mt-1">{sub}</p>}
    </div>
  );
}

// ── Status badge ───────────────────────────────────────────────────────────────
function StatusBadge({ status }) {
  const map = {
    completed:   { cls: "badge-positive", label: "Done"        },
    failed:      { cls: "badge-negative", label: "Failed"      },
    pending:     { cls: "badge-amber",    label: "Pending"      },
    transcribing:{ cls: "badge-brand",    label: "Transcribing" },
    analyzing:   { cls: "badge-brand",    label: "Analyzing"    },
  };
  const { cls, label } = map[status] || { cls: "badge-neutral", label: status };
  return (
    <span className={`badge ${cls}`}>
      {["transcribing","analyzing","pending"].includes(status) && (
        <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" />
      )}
      {label}
    </span>
  );
}

// ── Meeting row ────────────────────────────────────────────────────────────────
function MeetingRow({ meeting, onDelete }) {
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const handleDelete = async (e) => {
    e.stopPropagation();
    if (!window.confirm("Delete this meeting?")) return;
    setDeleting(true);
    try {
      await meetingsAPI.delete(meeting._id);
      toast.success("Meeting deleted");
      onDelete(meeting._id);
    } catch {
      toast.error("Delete failed");
    } finally {
      setDeleting(false);
      setMenuOpen(false);
    }
  };

  const fmt = (s) => {
    if (!s) return "—";
    const m = Math.floor(s / 60), sec = s % 60;
    return m > 0 ? `${m}m ${sec}s` : `${sec}s`;
  };

  return (
    <div
      onClick={() => meeting.status === "completed" && navigate(`/meetings/${meeting._id}`)}
      className={`glass glass-hover rounded-xl p-4 flex items-center gap-4 ${meeting.status === "completed" ? "cursor-pointer" : ""}`}
    >
      {/* Status dot */}
      <span className={`status-dot flex-shrink-0 ${meeting.status}`} />

      {/* Info */}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-[var(--text)] truncate">
          {meeting.ai_title || meeting.title}
        </p>
        <p className="text-xs text-[var(--text-3)] mt-0.5">
          {meeting.created_at ? formatDistanceToNow(new Date(meeting.created_at), { addSuffix: true }) : "—"}
          {meeting.duration_seconds ? ` · ${fmt(meeting.duration_seconds)}` : ""}
        </p>
      </div>

      {/* Language */}
      {meeting.language && (
        <span className="text-xs font-mono text-[var(--text-3)] hidden sm:block uppercase">
          {meeting.language}
        </span>
      )}

      <StatusBadge status={meeting.status} />

      {/* Actions */}
      <div className="relative flex-shrink-0" onClick={(e) => e.stopPropagation()}>
        <button onClick={() => setMenuOpen((o) => !o)}
          className="w-8 h-8 rounded-lg flex items-center justify-center text-[var(--text-3)] hover:text-[var(--text)] hover:bg-white/5 transition-colors">
          {deleting ? <Loader size={14} className="animate-spin" /> : <MoreVertical size={14} />}
        </button>
        {menuOpen && (
          <div className="absolute right-0 top-9 z-20 w-36 rounded-xl border border-[var(--border)] shadow-card py-1"
            style={{ background: "var(--bg-2)" }}>
            <button onClick={handleDelete}
              className="flex items-center gap-2 w-full px-3 py-2 text-xs text-red-400 hover:bg-red-500/10 transition-colors">
              <Trash2 size={13} /> Delete
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Main Dashboard ─────────────────────────────────────────────────────────────
export default function DashboardPage() {
  const { user }    = useAuth();
  const [page, setPage]     = useState(1);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [ids, setIds]       = useState(null);   // deleted IDs tracked locally

  const { meetings: rawMeetings, total, pages, loading: mLoading, refetch } =
    useMeetings({ page, limit: 8, search: search || undefined, status: status || undefined });

  const { stats, loading: sLoading } = useDashboardStats();

  const meetings = ids ? rawMeetings.filter((m) => !ids.has(m._id)) : rawMeetings;

  const handleDelete = (id) => {
    setIds((prev) => new Set([...(prev || []), id]));
    refetch();
  };

  const firstName = user?.full_name?.split(" ")[0] || "there";

  return (
    <div className="space-y-8 animate-fade-in">

      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-3xl text-[var(--text)]">
            Good {new Date().getHours() < 12 ? "morning" : new Date().getHours() < 17 ? "afternoon" : "evening"},{" "}
            <span className="gradient-text">{firstName}</span>
          </h1>
          <p className="text-[var(--text-2)] text-sm mt-1">Here's what's happening with your meetings.</p>
        </div>
        <Link to="/upload" className="btn-brand flex items-center gap-2 px-5 py-2.5 text-sm">
          <Upload size={16} /> Upload meeting
        </Link>
      </div>

      {/* ── Stats cards ─────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 stagger">
        <StatCard label="Total Meetings"  value={stats?.total_meetings}  icon={TrendingUp}   color="bg-brand-600"         sub={`${stats?.completed || 0} completed`} />
        <StatCard label="Hours Analyzed"  value={stats?.total_hours}     icon={Clock}        color="bg-emerald-600"       sub="Total audio processed" />
        <StatCard label="Completed"       value={stats?.completed}       icon={CheckCircle}  color="bg-green-600"         sub="Successfully analyzed" />
        <StatCard label="Failed"          value={stats?.failed}          icon={AlertCircle}  color="bg-red-600"           sub="Need attention" />
      </div>

      {/* ── Charts row ──────────────────────────────────────────────────────── */}
      {stats && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2 glass rounded-2xl p-5">
            <h3 className="text-sm font-semibold text-[var(--text-2)] mb-4">Meetings per week</h3>
            <WeeklyBarChart data={stats.weekly_meetings || []} />
          </div>
          <div className="glass rounded-2xl p-5">
            <h3 className="text-sm font-semibold text-[var(--text-2)] mb-4">Status overview</h3>
            <SentimentDoughnutChart
              data={{
                completed: stats.completed || 0,
                pending:   stats.pending   || 0,
                failed:    stats.failed    || 0,
              }}
              labels={["Completed","Pending","Failed"]}
              colors={["#10b981","#f59e0b","#ef4444"]}
            />
          </div>
        </div>
      )}

      {/* ── Meeting list ─────────────────────────────────────────────────────── */}
      <div>
        {/* List header + filters */}
        <div className="flex items-center gap-3 mb-4 flex-wrap">
          <h2 className="font-display text-xl text-[var(--text)] flex-1">Recent meetings</h2>

          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-3)]" />
            <input
              className="input-field pl-8 py-2 text-sm w-52"
              placeholder="Search meetings…"
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            />
          </div>

          <select
            className="input-field py-2 text-sm w-36"
            value={status}
            onChange={(e) => { setStatus(e.target.value); setPage(1); }}
          >
            <option value="">All statuses</option>
            <option value="completed">Completed</option>
            <option value="pending">Pending</option>
            <option value="failed">Failed</option>
          </select>

          <button onClick={refetch} className="btn-ghost p-2 rounded-xl" title="Refresh">
            <RefreshCw size={15} className={mLoading ? "animate-spin" : ""} />
          </button>
        </div>

        {/* Rows */}
        {mLoading ? (
          <div className="flex items-center justify-center py-16">
            <Loader size={24} className="animate-spin text-[var(--brand)]" />
          </div>
        ) : meetings.length === 0 ? (
          <div className="text-center py-16 glass rounded-2xl">
            <p className="text-4xl mb-3">🎙️</p>
            <p className="text-[var(--text)] font-semibold">No meetings yet</p>
            <p className="text-[var(--text-2)] text-sm mt-1 mb-5">Upload your first meeting recording to get started.</p>
            <Link to="/upload" className="btn-brand inline-flex items-center gap-2 px-5 py-2.5 text-sm">
              <Upload size={15} /> Upload now
            </Link>
          </div>
        ) : (
          <div className="space-y-2">
            {meetings.map((m) => (
              <MeetingRow key={m._id} meeting={m} onDelete={handleDelete} />
            ))}
          </div>
        )}

        {/* Pagination */}
        {pages > 1 && (
          <div className="flex items-center justify-center gap-2 mt-6">
            <button disabled={page === 1} onClick={() => setPage((p) => p - 1)} className="btn-ghost px-4 py-2 text-sm">Prev</button>
            <span className="text-sm text-[var(--text-2)]">Page {page} of {pages}</span>
            <button disabled={page === pages} onClick={() => setPage((p) => p + 1)} className="btn-ghost px-4 py-2 text-sm">Next</button>
          </div>
        )}
      </div>
    </div>
  );
}
