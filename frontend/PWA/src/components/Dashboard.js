import React, { useMemo } from 'react';
import { zoneHealth, moistureLabel, nitrogenLabel, phLabel } from '../utils/labels';
import './Dashboard.css';

export default function Dashboard({ zones, refresh, goToZone, goToAlerts, goToTasks }) {
  const counts = useMemo(() => {
    const c = { good: 0, average: 0, danger: 0, unknown: 0 };
    zones.forEach(z => {
      const [st] = zoneHealth(z.soil_moisture_20cm, z.nitrogen_ppm, z.ph_level);
      c[st] = (c[st] || 0) + 1;
    });
    return c;
  }, [zones]);

  const worstZone = useMemo(() => {
    const order = { danger: 0, average: 1, good: 2, unknown: 3 };
    return [...zones].sort((a, b) => {
      const [sa] = zoneHealth(a.soil_moisture_20cm, a.nitrogen_ppm, a.ph_level);
      const [sb] = zoneHealth(b.soil_moisture_20cm, b.nitrogen_ppm, b.ph_level);
      return order[sa] - order[sb];
    })[0];
  }, [zones]);

  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';
  const dayStr = new Date().toLocaleDateString('en-KE', { weekday: 'long', day: 'numeric', month: 'long' });

  // Determine priority alert content
  let alertBg = 'var(--orange)', alertIcon = '⚠️', alertTitle = '', alertSub = '';
  if (!worstZone) {
    alertTitle = 'Loading your farm data…';
    alertSub   = 'Please wait a moment.';
  } else {
    const [st] = zoneHealth(worstZone.soil_moisture_20cm, worstZone.nitrogen_ppm, worstZone.ph_level);
    const lbl = worstZone.zone_label || worstZone.zone_id;
    const m = worstZone.soil_moisture_20cm, n = worstZone.nitrogen_ppm, ph = worstZone.ph_level;
    if (st === 'danger') {
      alertBg = 'var(--red)';
      alertIcon = '🚨';
      alertTitle = `Zone ${lbl} needs action TODAY`;
      alertSub = m < 20 ? `Soil is DRY (${m?.toFixed(0)}%). Apply water now.`
               : n < 40 ? `Nitrogen is LOW (${n?.toFixed(0)} ppm). Add fertiliser.`
               : ph < 5.5 ? `Soil too acidic (pH ${ph?.toFixed(1)}). Add lime.`
               : 'Multiple problems detected — tap Act Now.';
    } else if (st === 'average') {
      alertBg = 'var(--orange)';
      alertIcon = '⚠️';
      alertTitle = `Zone ${lbl} needs attention soon`;
      alertSub = 'Conditions are below optimal. Check recommendations.';
    } else {
      alertBg = 'var(--green-lt)';
      alertIcon = '🎉';
      alertTitle = 'All zones look healthy today!';
      alertSub = 'Keep up the great work. Check Reports for trends.';
    }
  }

  const tasks = useMemo(() => {
    return zones
      .filter(z => {
        const [st] = zoneHealth(z.soil_moisture_20cm, z.nitrogen_ppm, z.ph_level);
        return st === 'danger' || st === 'average';
      })
      .slice(0, 3)
      .map(z => {
        const lbl = z.zone_label || z.zone_id;
        const m = z.soil_moisture_20cm, n = z.nitrogen_ppm, ph = z.ph_level;
        const [st] = zoneHealth(m, n, ph);
        const icon = st === 'danger' ? '🔴' : '🟡';
        const action = m < 30 ? `Water Zone ${lbl}` : n < 80 ? `Fertilise Zone ${lbl}` : `Check Zone ${lbl}`;
        return { icon, action, zone: z };
      });
  }, [zones]);

  return (
    <div className="screen dashboard">
      {/* Greeting */}
      <div className="dashboard-greeting">
        <div>
          <h1>{greeting} 🌤️</h1>
          <p>{dayStr}</p>
        </div>
        <button className="btn btn--ghost btn--sm" onClick={refresh} aria-label="Refresh data">
          🔄 Refresh
        </button>
      </div>

      {/* Priority alert — most urgent info first (Nielsen: visibility of status) */}
      <div className="priority-card" style={{ background: alertBg }}
           role="alert" aria-live="polite">
        <div className="priority-card__icon" aria-hidden="true">{alertIcon}</div>
        <div className="priority-card__body">
          <h2>{alertTitle}</h2>
          <p>{alertSub}</p>
        </div>
        {worstZone && alertTitle && (
          <button className="btn btn--sm priority-act-btn"
                  onClick={() => goToZone(worstZone)}
                  aria-label="Act on priority zone">
            Act Now →
          </button>
        )}
      </div>

      {/* Farm at a glance — colour + icon + count (never colour alone) */}
      <p className="section-label">Your Farm at a Glance</p>
      <div className="glance-grid">
        {[
          { key: 'good',    icon: '🟢', label: 'Healthy',   colour: 'var(--green-lt)', textCol: 'var(--green)' },
          { key: 'average', icon: '🟡', label: 'Watch',     colour: '#fef3dc',         textCol: '#b07800' },
          { key: 'danger',  icon: '🔴', label: 'Urgent',    colour: '#fde8e8',         textCol: 'var(--red)' },
        ].map(({ key, icon, label, colour, textCol }) => (
          <div key={key} className="glance-card"
               style={{ background: colour, borderColor: textCol + '33' }}
               onClick={goToAlerts}
               role="button" tabIndex={0}
               aria-label={`${counts[key]} ${label} zones`}>
            <span className="glance-count" style={{ color: textCol }}>
              {counts[key] ?? 0}
            </span>
            <span className="glance-label">{icon} {label}</span>
            <span className="glance-link" style={{ color: textCol }}>zones →</span>
          </div>
        ))}
      </div>

      {/* Today's tasks — checklist UX (Recognition over Recall) */}
      {tasks.length > 0 && (
        <>
          <p className="section-label">Today's Tasks ({tasks.length})</p>
          <div className="card task-preview">
            {tasks.map(({ icon, action, zone }, i) => (
              <button key={i} className="task-preview-row"
                      onClick={() => goToZone(zone)}
                      aria-label={action}>
                <span className="task-priority-icon">{icon}</span>
                <span className="task-text">{action}</span>
                <span className="task-arrow">→</span>
              </button>
            ))}
            <button className="btn btn--ghost" style={{ margin: '8px' }}
                    onClick={goToTasks}>
              See All Tasks
            </button>
          </div>
        </>
      )}

      {tasks.length === 0 && zones.length > 0 && (
        <div className="empty-state" style={{ paddingTop: 32 }}>
          <span className="empty-state-icon">🌾</span>
          <h3>No urgent tasks today</h3>
          <p>Your farm looks healthy. Check Reports for long-term trends.</p>
        </div>
      )}

      {zones.length === 0 && (
        <div className="loader">
          <span className="loader-icon">🌱</span>
          <p>Loading your farm data…</p>
        </div>
      )}
    </div>
  );
}
