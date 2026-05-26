/**
 * pages/ProfilePage.jsx — User profile management.
 */
import { useState }   from "react";
import { useAuth }    from "../context/AuthContext";
import { useTheme }   from "../context/ThemeContext";
import { usersAPI }   from "../services/api";
import toast from "react-hot-toast";
import { User, Lock, Bell, Moon, Save, Loader } from "lucide-react";

function Section({ title, icon: Icon, children }) {
  return (
    <div className="glass rounded-2xl p-6">
      <div className="flex items-center gap-2 mb-5">
        <Icon size={16} className="text-[var(--brand-light)]" />
        <h3 className="font-semibold text-[var(--text)]">{title}</h3>
      </div>
      {children}
    </div>
  );
}

export default function ProfilePage() {
  const { user, updateUser } = useAuth();
  const { dark, toggle }     = useTheme();

  const [profile, setProfile] = useState({ full_name: user?.full_name || "" });
  const [pwForm,  setPwForm]  = useState({ current_password: "", new_password: "" });
  const [saving,  setSaving]  = useState("");

  const saveProfile = async () => {
    setSaving("profile");
    try {
      const { data } = await usersAPI.updateProfile(profile);
      updateUser(data.user);
      toast.success("Profile updated");
    } catch (e) {
      toast.error(e.response?.data?.error || "Update failed");
    } finally {
      setSaving("");
    }
  };

  const savePassword = async () => {
    if (!pwForm.current_password || !pwForm.new_password) { toast.error("Both fields required"); return; }
    setSaving("password");
    try {
      await usersAPI.updateProfile(pwForm);    // uses auth controller's change_password via PUT /auth/password
      toast.success("Password changed");
      setPwForm({ current_password: "", new_password: "" });
    } catch (e) {
      toast.error(e.response?.data?.error || "Password change failed");
    } finally {
      setSaving("");
    }
  };

  const savePref = async (key, val) => {
    try {
      await usersAPI.updatePreferences({ [key]: val });
      updateUser({ preferences: { ...(user?.preferences || {}), [key]: val } });
      toast.success("Preference saved");
    } catch {
      toast.error("Failed to save preference");
    }
  };

  return (
    <div className="max-w-2xl mx-auto space-y-5 animate-fade-in">
      <div>
        <h1 className="font-display text-3xl text-[var(--text)]">Profile</h1>
        <p className="text-[var(--text-2)] text-sm mt-1">Manage your account settings.</p>
      </div>

      {/* Avatar + name display */}
      <div className="glass rounded-2xl p-5 flex items-center gap-4">
        <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-brand-400 to-brand-700 flex items-center justify-center text-white text-xl font-bold shadow-glow-brand">
          {user?.full_name?.[0]?.toUpperCase() || "U"}
        </div>
        <div>
          <p className="font-semibold text-[var(--text)]">{user?.full_name}</p>
          <p className="text-sm text-[var(--text-2)]">{user?.email}</p>
          <span className={`badge mt-1 ${user?.role === "admin" ? "badge-brand" : "badge-neutral"}`}>{user?.role}</span>
        </div>
      </div>

      {/* Profile info */}
      <Section title="Personal information" icon={User}>
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-[var(--text-2)] mb-1.5">Full name</label>
            <input className="input-field" value={profile.full_name}
              onChange={(e) => setProfile((p) => ({ ...p, full_name: e.target.value }))} />
          </div>
          <div>
            <label className="block text-sm text-[var(--text-2)] mb-1.5">Email</label>
            <input className="input-field opacity-60" value={user?.email || ""} disabled />
          </div>
          <button onClick={saveProfile} disabled={saving === "profile"}
            className="btn-brand flex items-center gap-2 px-5 py-2.5 text-sm">
            {saving === "profile" ? <Loader size={14} className="animate-spin" /> : <Save size={14} />}
            Save changes
          </button>
        </div>
      </Section>

      {/* Password */}
      <Section title="Change password" icon={Lock}>
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-[var(--text-2)] mb-1.5">Current password</label>
            <input type="password" className="input-field" value={pwForm.current_password}
              onChange={(e) => setPwForm((p) => ({ ...p, current_password: e.target.value }))} />
          </div>
          <div>
            <label className="block text-sm text-[var(--text-2)] mb-1.5">New password</label>
            <input type="password" className="input-field" value={pwForm.new_password}
              onChange={(e) => setPwForm((p) => ({ ...p, new_password: e.target.value }))} />
          </div>
          <button onClick={savePassword} disabled={saving === "password"}
            className="btn-brand flex items-center gap-2 px-5 py-2.5 text-sm">
            {saving === "password" ? <Loader size={14} className="animate-spin" /> : <Lock size={14} />}
            Update password
          </button>
        </div>
      </Section>

      {/* Preferences */}
      <Section title="Preferences" icon={Bell}>
        <div className="space-y-4">
          {[
            { key: "dark_mode",      label: "Dark mode",              icon: Moon,  type: "toggle", current: dark, action: () => { toggle(); savePref("dark_mode", !dark); } },
            { key: "email_notify",   label: "Email notifications",    icon: Bell,  type: "toggle", current: user?.preferences?.email_notify, action: () => savePref("email_notify", !user?.preferences?.email_notify) },
          ].map(({ key, label, icon: Icon, type, current, action }) => (
            <div key={key} className="flex items-center justify-between py-2">
              <div className="flex items-center gap-2">
                <Icon size={15} className="text-[var(--text-3)]" />
                <span className="text-sm text-[var(--text)]">{label}</span>
              </div>
              <button onClick={action}
                className={`w-11 h-6 rounded-full transition-colors relative ${current ? "bg-brand-600" : "bg-white/10"}`}>
                <span className={`absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform ${current ? "translate-x-5" : "translate-x-0.5"}`} />
              </button>
            </div>
          ))}
        </div>
      </Section>
    </div>
  );
}
