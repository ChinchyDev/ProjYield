import React, { useMemo } from 'react';
import { zoneHealth } from '../utils/labels';
import './Alerts.css';

function buildAlertMessage(zone) {
  const m  = zone.soil_moisture_20cm;
  const n  = zone.nitrogen_ppm;
  const ph = zone.ph_level;
  const lbl = zone.zone_label || zone.zone_id;
  if (m  != null && m  < 20)  return `Zone ${lbl}: Soil is critically DRY (${m.toFixed(0)}%). Apply water today.`;
  if (n  != null && n  < 40)  return `Zone ${lbl}: Nitrogen is LOW (${n.toFixed(0)} ppm). Apply fertiliser.`;
  if (ph != null && ph < 5.5) return `Zone ${lbl}: Soil too acidic (pH ${ph.toFixed(1)}). Add lime.`;
  if (ph != null && ph > 7.8) return `Zone ${lbl}: Soil too alkaline (pH ${ph.toFixed(1)}). Adjust treatment.`;
  return `Zone ${lbl}: Multiple conditions need attention.`;
}

export default function Alerts({ zones, goToZone }) {
  const critical = useMemo(() =>
    zones.filter(z => zoneHealth(z.soil_moisture_20cm, z.nitrogen_ppm, z.ph_level)[0] === 'danger'),
    [zones]);

  const watch = useMemo(() =>
    zones.filter(z => zoneHealth(z.soil_moisture_20cm, z.nitrogen_ppm, z.ph_level)[0] === 'average'),
    [zones]);

  const hasAlerts = critical.length > 0 || watch.length > 0;

  return (
    <div className="screen alerts-screen">
      <div className="page-header">
        <h1>🔔 Alerts</h1>
        <p>{critical.length + watch.length} active alerts</p>
      </div>

      {zones.length === 0 && (
        <div className="loader">
          <span className="loader-icon">🌱</span>
          <p>Loading your farm data…</p>
        </div>
      )}

      {zones.length > 0 && !hasAlerts && (
        <div className="empty-state">
          <span className="empty-state-icon">✅</span>
          <h3>No alerts right now</h3>
          <p>All your zones look healthy. Great work!</p>
        </div>
      )}

      {/* Act Today — critical (red) */}
      {critical.length > 0 && (
        <div className="alerts-section">
          <p className="section-label alerts-section-label alerts-section-label--red">
            🔴 Act Today ({critical.length})
          </p>
          {critical.slice(0, 5).map(zone => ( // Miller's Law: max 5
            <AlertCard
              key={zone.zone_id}
              zone={zone}
              severity="danger"
              message={buildAlertMessage(zone)}
              onAct={() => goToZone(zone)}
            />
          ))}
        </div>
      )}

      {/* This Week — watch (amber) */}
      {watch.length > 0 && (
        <div className="alerts-section">
          <p className="section-label alerts-section-label alerts-section-label--amber">
            🟡 This Week ({watch.length})
          </p>
          {watch.slice(0, 5).map(zone => (
            <AlertCard
              key={zone.zone_id}
              zone={zone}
              severity="average"
              message={buildAlertMessage(zone)}
              onAct={() => goToZone(zone)}
            />
          ))}
        </div>
      )}

      {/* SMS note */}
      {hasAlerts && (
        <p className="alerts-sms-note">
          📱 Critical alerts are also sent via SMS to your registered number.
        </p>
      )}
    </div>
  );
}

function AlertCard({ zone, severity, message, onAct }) {
  const colours = {
    danger:  { bg: '#fde8e8', border: 'var(--red)',   btn: 'var(--red)' },
    average: { bg: '#fef3dc', border: 'var(--amber)', btn: '#b07800' },
  };
  const { bg, border, btn } = colours[severity] || colours.average;

  return (
    <div
      className="alert-card"
      style={{ background: bg, borderColor: border }}
      role="alert"
    >
      <div className="alert-card__body">
        <p className="alert-card__message">{message}</p>
      </div>
      <button
        className="btn btn--sm alert-act-btn"
        style={{ background: btn, color: '#fff', width: 'auto', minHeight: 42 }}
        onClick={onAct}
        aria-label="Take action on this alert"
      >
        Act →
      </button>
    </div>
  );
}
