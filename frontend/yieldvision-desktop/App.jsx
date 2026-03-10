import { useState, useEffect } from "react";
import { Sprout, LogOut, Sun, Moon } from "lucide-react";

import { LIGHT, DARK }         from "./theme";
import { getPendingRecommendations } from "./api";

import BottomNav           from "./components/BottomNav";
import OnboardingScreen    from "./screens/OnboardingScreen";
import HomeScreen          from "./screens/HomeScreen";
import FarmScreen          from "./screens/FarmScreen";
import TasksScreen         from "./screens/TasksScreen";
import AlertsScreen        from "./screens/AlertsScreen";

export default function App() {
  // ── Theme ────────────────────────────────────────────────────────────────
  const [isDark, setIsDark] = useState(() => {
    const saved = localStorage.getItem("yv_theme");
    if (saved) return saved === "dark";
    // Respect OS preference as default
    return window.matchMedia?.("(prefers-color-scheme: dark)").matches;
  });

  const t = isDark ? DARK : LIGHT;

  function toggleTheme() {
    setIsDark(prev => {
      localStorage.setItem("yv_theme", !prev ? "dark" : "light");
      return !prev;
    });
  }

  // Apply dark class to <html> for Tailwind dark: variants (used in index.css)
  useEffect(() => {
    document.documentElement.classList.toggle("dark", isDark);
  }, [isDark]);

  // ── Session ──────────────────────────────────────────────────────────────
  const [session, setSession] = useState(() => {
    const farmId   = localStorage.getItem("yv_farm_id");
    const farmName = localStorage.getItem("yv_farm_name");
    const owner    = localStorage.getItem("yv_owner");
    if (farmId) return { farm_id: farmId, farm_name: farmName || "My Farm", owner_name: owner || "Farmer" };
    return null;
  });

  // ── Navigation ───────────────────────────────────────────────────────────
  const [tab, setTab] = useState("home");

  // ── Alert badge count ────────────────────────────────────────────────────
  const [alertCount, setAlertCount] = useState(0);

  useEffect(() => {
    if (!session) return;
    getPendingRecommendations(session.farm_id)
      .then(r => setAlertCount(r.critical || 0))
      .catch(() => {});
  }, [session, tab]);

  // ── Auth ─────────────────────────────────────────────────────────────────
  function handleLogin(s) {
    setSession(s);
    setTab("home");
  }

  function handleLogout() {
    localStorage.removeItem("yv_farm_id");
    localStorage.removeItem("yv_farm_name");
    localStorage.removeItem("yv_owner");
    setSession(null);
    setTab("home");
  }

  // ── Render: not logged in ─────────────────────────────────────────────────
  if (!session) {
    return <OnboardingScreen onLogin={handleLogin} t={t} />;
  }

  // ── Render: main app ──────────────────────────────────────────────────────
  return (
    <div
      className="flex flex-col h-screen overflow-hidden"
      style={{ background: t.bg, color: t.textPrimary }}
    >
      {/* ── Top bar ─────────────────────────────────── */}
      <header
        className="flex-shrink-0 flex items-center justify-between px-4 py-3 z-40"
        style={{
          background:         t.bg + "dd",
          backdropFilter:     "blur(12px)",
          WebkitBackdropFilter:"blur(12px)",
          borderBottom:       `1px solid ${t.border}`,
        }}
      >
        {/* Logo */}
        <div className="flex items-center gap-2">
          <div
            className="w-7 h-7 rounded-lg flex items-center justify-center shadow-sm"
            style={{ background: t.panel }}
          >
            <Sprout size={14} color={t.panelMuted} />
          </div>
          <span className="text-sm font-bold" style={{ color: t.textPrimary }}>
            YieldVision
          </span>
        </div>

        {/* Right controls */}
        <div className="flex items-center gap-1.5">
          {/* Dark / light toggle */}
          <button
            onClick={toggleTheme}
            className="p-2 rounded-xl transition-opacity hover:opacity-70"
            style={{ background: t.bgCard }}
            title={isDark ? "Switch to light mode" : "Switch to dark mode"}
            aria-label={isDark ? "Light mode" : "Dark mode"}
          >
            {isDark
              ? <Sun  size={14} style={{ color: t.textSub }} />
              : <Moon size={14} style={{ color: t.textSub }} />}
          </button>

          {/* Logout */}
          <button
            onClick={handleLogout}
            className="p-2 rounded-xl transition-opacity hover:opacity-70"
            style={{ background: t.bgCard }}
            title="Sign out"
            aria-label="Sign out"
          >
            <LogOut size={14} style={{ color: t.textSub }} />
          </button>
        </div>
      </header>

      {/* ── Screen content ──────────────────────────── */}
      <main className="flex-1 overflow-hidden relative">
        {tab === "home" && (
          <HomeScreen
            farmId={session.farm_id}
            farmName={session.farm_name}
            ownerName={session.owner_name}
            onNavigate={setTab}
            t={t}
          />
        )}
        {tab === "farm" && (
          <FarmScreen
            farmId={session.farm_id}
            farmName={session.farm_name}
            t={t}
          />
        )}
        {tab === "tasks" && (
          <TasksScreen farmId={session.farm_id} t={t} />
        )}
        {tab === "alerts" && (
          <AlertsScreen farmId={session.farm_id} t={t} />
        )}
      </main>

      {/* ── Bottom nav ──────────────────────────────── */}
      <BottomNav
        active={tab}
        onChange={setTab}
        alertCount={alertCount}
        t={t}
      />
    </div>
  );
}
