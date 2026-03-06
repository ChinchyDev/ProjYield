import React, { useState, useEffect, useCallback } from 'react';
import './App.css';
import Dashboard from './components/Dashboard';
import Farm from './components/Farm';
import Tasks from './components/Tasks';
import Reports from './components/Reports';
import Alerts from './components/Alerts';
import { getZonesSummary, getSystemStatus } from './api';

// Hub-and-spoke nav — 5 items max (Hick's Law)
const NAV = [
  { id: 'dashboard', icon: '🏠', label: 'Home' },
  { id: 'farm',      icon: '🌱', label: 'My Farm' },
  { id: 'tasks',     icon: '📋', label: 'Tasks' },
  { id: 'reports',   icon: '📊', label: 'Reports' },
  { id: 'alerts',    icon: '🔔', label: 'Alerts' },
];

export default function App() {
  const [screen, setScreen]     = useState('dashboard');
  const [zones, setZones]       = useState([]);
  const [online, setOnline]     = useState(null); // null = checking
  const [offline, setOffline]   = useState(false);
  const [alertCount, setAlertCount] = useState(0);
  const [selectedZone, setSelectedZone] = useState(null);

  const refresh = useCallback(async () => {
    try {
      const { data, offline: fromCache } = await getZonesSummary();
      setZones(data.zones || []);
      setOnline(true);
      setOffline(fromCache);
      // Count urgent zones for alert badge
      const urgent = (data.zones || []).filter(z => z.status === 'danger').length;
      setAlertCount(urgent);
    } catch {
      setOnline(false);
      setOffline(true);
    }
  }, []);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 30_000);
    return () => clearInterval(interval);
  }, [refresh]);

  // Navigate to farm and open a zone detail
  const goToZone = (zone) => {
    setSelectedZone(zone);
    setScreen('farm');
  };

  const screenProps = { zones, refresh, goToZone, selectedZone, setSelectedZone };

  return (
    <div className="app">
      {/* Offline banner — Nielsen: visibility of system status */}
      {offline && (
        <div className="offline-banner" role="status">
          📡 You're offline — showing last updated data
        </div>
      )}

      {/* Main content — hub screens */}
      <main className="main-content">
        {screen === 'dashboard' && <Dashboard {...screenProps} goToAlerts={() => setScreen('alerts')} goToTasks={() => setScreen('tasks')} />}
        {screen === 'farm'      && <Farm {...screenProps} />}
        {screen === 'tasks'     && <Tasks {...screenProps} />}
        {screen === 'reports'   && <Reports {...screenProps} />}
        {screen === 'alerts'    && <Alerts {...screenProps} />}
      </main>

      {/* Bottom navigation (mobile-first, thumb-friendly) */}
      <nav className="bottom-nav" aria-label="Main navigation">
        {NAV.map(({ id, icon, label }) => (
          <button
            key={id}
            className={`nav-btn${screen === id ? ' nav-btn--active' : ''}`}
            onClick={() => setScreen(id)}
            aria-label={label}
            aria-current={screen === id ? 'page' : undefined}
          >
            <span className="nav-icon" aria-hidden="true">
              {icon}
              {id === 'alerts' && alertCount > 0 && (
                <span className="nav-badge">{alertCount}</span>
              )}
            </span>
            <span className="nav-label">{label}</span>
          </button>
        ))}
      </nav>

      {/* Connection status dot — always visible */}
      <div className={`conn-dot ${online === true ? 'conn-dot--online' : online === false ? 'conn-dot--offline' : 'conn-dot--checking'}`}
           role="status"
           aria-label={online ? 'Connected to server' : 'Not connected'} />
    </div>
  );
}
