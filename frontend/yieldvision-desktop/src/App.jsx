import { useState, useEffect, useCallback } from "react";
import Icon from "@mdi/react";
import {
  mdiWeatherSunny,
  mdiWeatherNight,
  mdiLogout,
  mdiLeaf,
  mdiRobotMower,
} from "@mdi/js";

import { LIGHT, DARK }              from "./theme";
import { getPendingRecommendations } from "./api";

import BottomNav           from "./components/BottomNav";
import RoverControlPanel   from "./components/RoverControlPanel";
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
    return window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false;
  });

  const t = isDark ? DARK : LIGHT;

  function toggleTheme() {
    setIsDark(prev => {
      localStorage.setItem("yv_theme", !prev ? "dark" : "light");
      return !prev;
    });
  }

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

  // ── Rover control panel ───────────────────────────────────────────────────
  const [roverOpen, setRoverOpen] = useState(false);

  // ── Alert badge ──────────────────────────────────────────────────────────
  const [alertCount, setAlertCount] = useState(0);

  const refreshAlertCount = useCallback(() => {
    if (!session) return;
    getPendingRecommendations(session.farm_id)
      .then(r => {
        const recs = Array.isArray(r) ? r : (r.recommendations || []);
        const critical = recs.filter(
          x => (x.urgency || "").toUpperCase() === "CRITICAL" && x.status === "pending"
        ).length;
        setAlertCount(critical);
      })
      .catch(() => {});
  }, [session]);

  useEffect(() => {
    refreshAlertCount();
    const id = setInterval(refreshAlertCount, 60_000);
    return () => clearInterval(id);
  }, [refreshAlertCount]);

  // ── Auth ─────────────────────────────────────────────────────────────────
  function handleLogin(s) {
    localStorage.setItem("yv_farm_id",   s.farm_id);
    localStorage.setItem("yv_farm_name", s.farm_name || "My Farm");
    localStorage.setItem("yv_owner",     s.owner_name || "Farmer");
    setSession(s);
    setTab("home");
  }

  function handleLogout() {
    ["yv_farm_id", "yv_farm_name", "yv_owner"].forEach(k => localStorage.removeItem(k));
    setSession(null);
    setTab("home");
  }

  // ── Not logged in ─────────────────────────────────────────────────────────
  if (!session) {
    return <OnboardingScreen onLogin={handleLogin} t={t} />;
  }

  // ── Main app ──────────────────────────────────────────────────────────────
  const screenProps = { farmId: session.farm_id, farmName: session.farm_name, t };

  return (
    <div
      className="flex flex-col h-screen overflow-hidden"
      style={{ background: t.bg, color: t.textPrimary }}
    >
      {/* ── Top bar ─────────────────────────────────────────────────────── */}
      <header
        className="flex-shrink-0 flex items-center justify-between px-5 py-3 z-40 glass drag-handle"
        style={{
          background:  t.bgCard,
          borderBottom:`1px solid ${t.border}`,
        }}
      >
        {/* Logo */}
        <div className="flex items-center gap-2.5">
          <div
            className="flex items-center justify-center rounded-xl"
            style={{ width: "30px", height: "30px", background: t.panel }}
          >
            <Icon path={mdiLeaf} size={0.7} color={t.panelMuted} />
          </div>
          <div>
            <div className="text-sm font-bold leading-none" style={{ color: t.textPrimary }}>
              YieldVision
            </div>
            <div className="text-xs leading-none mt-0.5" style={{ color: t.textMuted }}>
              {session.farm_name}
            </div>
          </div>
        </div>

        {/* Controls */}
        <div className="flex items-center gap-1">
          {/* Rover control toggle */}
          <button
            onClick={() => setRoverOpen(prev => !prev)}
            className="flex items-center justify-center rounded-xl transition-opacity hover:opacity-80 no-focus-ring"
            style={{
              width: "32px", height: "32px",
              background: roverOpen ? t.accent : t.bgHover,
            }}
            aria-label="Toggle rover control"
            title="Rover Control"
          >
            <Icon
              path={mdiRobotMower}
              size={0.62}
              color={roverOpen ? t.accentText : t.textSub}
            />
          </button>

          <button
            onClick={toggleTheme}
            className="flex items-center justify-center rounded-xl transition-opacity hover:opacity-70 no-focus-ring"
            style={{ width: "32px", height: "32px", background: t.bgHover }}
            aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
          >
            <Icon
              path={isDark ? mdiWeatherSunny : mdiWeatherNight}
              size={0.62}
              color={t.textSub}
            />
          </button>

          <button
            onClick={handleLogout}
            className="flex items-center justify-center rounded-xl transition-opacity hover:opacity-70 no-focus-ring"
            style={{ width: "32px", height: "32px", background: t.bgHover }}
            aria-label="Sign out"
          >
            <Icon path={mdiLogout} size={0.62} color={t.textSub} />
          </button>
        </div>
      </header>

      {/* ── Rover control panel — slides in below header ─────────────────── */}
      {roverOpen && (
        <RoverControlPanel
          t={t}
          onClose={() => setRoverOpen(false)}
        />
      )}

      {/* ── Screen content ──────────────────────────────────────────────── */}
      <main className="flex-1 overflow-hidden relative">
        {tab === "home" && (
          <HomeScreen
            session={session}
            t={t}
            onNavigate={setTab}
          />
        )}
        {tab === "farm"   && <FarmScreen   {...screenProps} />}
        {tab === "tasks"  && <TasksScreen  {...screenProps} onRefreshAlerts={refreshAlertCount} />}
        {tab === "alerts" && <AlertsScreen {...screenProps} />}
      </main>

      {/* ── Floating bottom nav ──────────────────────────────────────────── */}
      <BottomNav
        active={tab}
        onChange={setTab}
        alertCount={alertCount}
        t={t}
      />
    </div>
  );
}
