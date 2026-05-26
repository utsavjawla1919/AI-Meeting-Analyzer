/**
 * App.jsx — Root component. Sets up providers, routing, and protected routes.
 */

import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "react-hot-toast";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { ThemeProvider } from "./context/ThemeContext";

import AppLayout    from "./components/layout/AppLayout";
import LoginPage    from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import DashboardPage  from "./pages/DashboardPage";
import UploadPage     from "./pages/UploadPage";
import MeetingPage    from "./pages/MeetingPage";
import ProfilePage    from "./pages/ProfilePage";
import AdminPage      from "./pages/AdminPage";
import SearchPage     from "./pages/SearchPage";

// ── Protected route wrapper ────────────────────────────────────────────────────
function Protected({ children, adminOnly = false }) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!user) return <Navigate to="/login" replace />;
  if (adminOnly && user.role !== "admin") return <Navigate to="/" replace />;

  return children;
}

// ── Public route wrapper (redirect if already logged in) ──────────────────────
function Public({ children }) {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (user) return <Navigate to="/" replace />;
  return children;
}

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
          <Toaster
            position="top-right"
            toastOptions={{
              style: {
                background:  "var(--bg-2)",
                color:       "var(--text)",
                border:      "1px solid var(--border-2)",
                borderRadius: "12px",
                fontFamily:  "'DM Sans', sans-serif",
                fontSize:    "0.9rem",
              },
              success: { iconTheme: { primary: "#10b981", secondary: "#fff" } },
              error:   { iconTheme: { primary: "#ef4444", secondary: "#fff" } },
            }}
          />

          <Routes>
            {/* Public auth routes */}
            <Route path="/login"    element={<Public><LoginPage /></Public>} />
            <Route path="/register" element={<Public><RegisterPage /></Public>} />

            {/* Protected app routes */}
            <Route element={<Protected><AppLayout /></Protected>}>
              <Route index              element={<DashboardPage />} />
              <Route path="upload"      element={<UploadPage />} />
              <Route path="meetings/:id" element={<MeetingPage />} />
              <Route path="search"      element={<SearchPage />} />
              <Route path="profile"     element={<ProfilePage />} />
              <Route
                path="admin"
                element={<Protected adminOnly><AdminPage /></Protected>}
              />
            </Route>

            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  );
}
