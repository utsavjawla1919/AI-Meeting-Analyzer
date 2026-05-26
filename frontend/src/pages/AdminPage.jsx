/**
 * pages/AdminPage.jsx — Admin panel: platform stats and user management.
 */
import { useState, useEffect } from "react";
import { usersAPI }  from "../services/api";
import { useAuth }   from "../context/AuthContext";
import toast from "react-hot-toast";
import { Shield, Users, TrendingUp, Loader, ToggleLeft, ToggleRight, Trash2, Crown } from "lucide-react";
import { formatDistanceToNow } from "date-fns";

function StatCard({ label, value, icon: Icon, color }) {
  return (
    <div className="glass rounded-2xl p-5">
      <div className={`w-9 h-9 rounded-xl flex items-center justify-center mb-3 ${color}`}>
        <Icon size={16} className="text-white" />
      </div>
      <p className="text-2xl font-bold text-[var(--text)] font-display">{value ?? "—"}</p>
      <p className="text-sm text-[var(--text-2)] mt-0.5">{label}</p>
    </div>
  );
}

export default function AdminPage() {
  const { user: self } = useAuth();
  const [stats,  setStats]  = useState(null);
  const [users,  setUsers]  = useState([]);
  const [total,  setTotal]  = useState(0);
  const [page,   setPage]   = useState(1);
  const [search, setSearch] = useState("");
  const [loading,setLoading]= useState(true);
  const [acting, setActing] = useState({});

  const loadStats = () =>
    usersAPI.adminStats().then(({ data }) => setStats(data)).catch(() => {});

  const loadUsers = () => {
    setLoading(true);
    usersAPI.adminListUsers({ page, limit: 10, search: search || undefined })
      .then(({ data }) => { setUsers(data.users); setTotal(data.total); })
      .catch(() => toast.error("Failed to load users"))
      .finally(() => setLoading(false));
  };

  useEffect(() => { loadStats(); }, []);
  useEffect(() => { loadUsers(); }, [page, search]);

  const toggleUser = async (uid) => {
    setActing((a) => ({ ...a, [uid]: "toggle" }));
    try {
      const { data } = await usersAPI.adminToggleUser(uid);
      toast.success(data.message);
      loadUsers();
    } catch (e) {
      toast.error(e.response?.data?.error || "Failed");
    } finally {
      setActing((a) => ({ ...a, [uid]: null }));
    }
  };

  const changeRole = async (uid, role) => {
    setActing((a) => ({ ...a, [uid]: "role" }));
    try {
      await usersAPI.adminChangeRole(uid, role);
      toast.success(`Role updated to ${role}`);
      loadUsers();
    } catch (e) {
      toast.error(e.response?.data?.error || "Failed");
    } finally {
      setActing((a) => ({ ...a, [uid]: null }));
    }
  };

  const pages = Math.ceil(total / 10);

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-xl bg-brand-600/20 flex items-center justify-center">
          <Shield size={18} className="text-brand-400" />
        </div>
        <div>
          <h1 className="font-display text-3xl text-[var(--text)]">Admin Panel</h1>
          <p className="text-sm text-[var(--text-2)]">Platform management and oversight.</p>
        </div>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard label="Total users"    value={stats.total_users}    icon={Users}      color="bg-brand-600"   />
          <StatCard label="Active users"   value={stats.active_users}   icon={TrendingUp} color="bg-emerald-600" />
          <StatCard label="Total meetings" value={stats.total_meetings} icon={TrendingUp} color="bg-amber-600"   />
          <StatCard label="Hours analyzed" value={stats.total_hours}    icon={Shield}     color="bg-rose-600"    />
        </div>
      )}

      {/* User table */}
      <div className="glass rounded-2xl overflow-hidden">
        <div className="flex items-center justify-between p-4 border-b border-[var(--border)]">
          <h3 className="font-semibold text-[var(--text)]">All users ({total})</h3>
          <input className="input-field py-2 text-sm w-52" placeholder="Search users…"
            value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} />
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader size={22} className="animate-spin text-[var(--brand)]" />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--border)]">
                  {["User","Role","Meetings","Joined","Status","Actions"].map((h) => (
                    <th key={h} className="text-left text-xs text-[var(--text-3)] font-medium px-4 py-3">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {users.map((u) => {
                  const isSelf   = u._id === self?._id;
                  const spinning = acting[u._id];
                  return (
                    <tr key={u._id} className="border-b border-[var(--border)] last:border-0 hover:bg-white/[0.02] transition-colors">
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-brand-400 to-brand-600 flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
                            {u.full_name?.[0]?.toUpperCase()}
                          </div>
                          <div>
                            <p className="font-medium text-[var(--text)]">{u.full_name} {isSelf && <span className="badge badge-brand ml-1">You</span>}</p>
                            <p className="text-xs text-[var(--text-3)]">{u.email}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`badge ${u.role === "admin" ? "badge-brand" : "badge-neutral"}`}>
                          {u.role === "admin" && <Crown size={10} />} {u.role}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-[var(--text-2)]">{u.meeting_count || 0}</td>
                      <td className="px-4 py-3 text-xs text-[var(--text-3)]">
                        {u.created_at ? formatDistanceToNow(new Date(u.created_at), { addSuffix: true }) : "—"}
                      </td>
                      <td className="px-4 py-3">
                        <span className={`badge ${u.is_active ? "badge-positive" : "badge-negative"}`}>
                          {u.is_active ? "Active" : "Inactive"}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        {!isSelf && (
                          <div className="flex items-center gap-1">
                            <button onClick={() => toggleUser(u._id)} disabled={!!spinning}
                              className="p-1.5 rounded-lg hover:bg-white/10 text-[var(--text-3)] hover:text-[var(--text)] transition-colors"
                              title={u.is_active ? "Deactivate" : "Activate"}>
                              {spinning === "toggle" ? <Loader size={13} className="animate-spin" /> :
                               u.is_active ? <ToggleRight size={15} className="text-green-400" /> : <ToggleLeft size={15} />}
                            </button>
                            <button onClick={() => changeRole(u._id, u.role === "admin" ? "user" : "admin")}
                              disabled={!!spinning}
                              className="p-1.5 rounded-lg hover:bg-white/10 text-[var(--text-3)] hover:text-amber-400 transition-colors"
                              title={u.role === "admin" ? "Remove admin" : "Make admin"}>
                              <Crown size={13} />
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {pages > 1 && (
          <div className="flex items-center justify-center gap-3 p-4 border-t border-[var(--border)]">
            <button disabled={page === 1} onClick={() => setPage((p) => p - 1)} className="btn-ghost px-3 py-1.5 text-xs">Prev</button>
            <span className="text-xs text-[var(--text-3)]">{page}/{pages}</span>
            <button disabled={page === pages} onClick={() => setPage((p) => p + 1)} className="btn-ghost px-3 py-1.5 text-xs">Next</button>
          </div>
        )}
      </div>
    </div>
  );
}
