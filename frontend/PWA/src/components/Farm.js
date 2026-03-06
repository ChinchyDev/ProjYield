import React, { useState, useEffect } from 'react';
import { zoneHealth, moistureLabel, nitrogenLabel, phLabel, statusPillClass } from '../utils/labels';
import RecommendationModal from './RecommendationModal';
import './Farm.css';

const FILTERS = [
  { key: null,      label: 'All' },
  { key: 'good',    label: '🟢 Good' },
  { key: 'average', label: '🟡 Watch' },
  { key: 'danger',  label: '🔴 Urgent' },
];

export default function Farm({ zones, refresh, selectedZone, setSelectedZone }) {
  const [filter, setFilter]       = useState(null);
  const [detailZone, setDetailZone] = useState(selectedZone || null);
  const [showRec, setShowRec]     = useState(false);
  const [showNumbers, setShowNumbers] = useState(false);

  // If parent navigated here with a pre-selected zone, open it
  useEffect(() => {
    if (selectedZone) {
      setDetailZone(selectedZone);
      setSelectedZone(null);
    }
  }, [selectedZone, setSelectedZone]);

  const filtered = zones.filter(z => {
    if (!filter) return true;
    const [st] = zoneHealth(z.soil_moisture_20cm, z.nitrogen_ppm, z.ph_level);
    return st === filter;
  });

  return (
    <div className="screen farm-screen">
      {/* Header */}
      <div className="page-header">
        <h1>🌱 My Farm</h1>
        <p>{zones.length} zones mapped</p>
      </div>

      {/* Filter chips */}
      <div className="filter-row">
        {FILTERS.map(({ key, label }) => (
          <button
            key={String(key)}
            className={`filter-chip${filter === key ? ' filter-chip--active' : ''}`}
            onClick={() => setFilter(key)}
          >
            {label}
          </button>
        ))}
        <button className="btn btn--ghost btn--sm filter-refresh" onClick={refresh}>
          🔄
        </button>
      </div>

      {/* Zone list + detail — responsive split */}
      <div className="farm-body">
        {/* Zone list */}
        <div className={`zone-list${detailZone ? ' zone-list--collapsed' : ''}`}>
          {filtered.length === 0 && (
            <div className="empty-state">
              <span className="empty-state-icon">🔍</span>
              <p>No zones match this filter.</p>
            </div>
          )}
          {filtered.map(zone => {
            const lbl = zone.zone_label || zone.zone_id;
            const [st, tag] = zoneHealth(zone.soil_moisture_20cm, zone.nitrogen_ppm, zone.ph_level);
            const isSelected = detailZone?.zone_id === zone.zone_id;
            return (
              <button
                key={zone.zone_id}
                className={`zone-row${isSelected ? ' zone-row--selected' : ''}`}
                onClick={() => setDetailZone(zone)}
                aria-label={`Zone ${lbl}: ${tag}`}
                aria-pressed={isSelected}
              >
                <span className={`zone-status-bar zone-status-bar--${st}`} aria-hidden="true" />
                <div className="zone-row__body">
                  <span className="zone-row__label">Zone {lbl}</span>
                  <span className={statusPillClass(st)}>{tag}</span>
                </div>
                <span className="zone-row__arrow">›</span>
              </button>
            );
          })}
        </div>

        {/* Zone detail panel */}
        {detailZone && (
          <div className="zone-detail">
            <ZoneDetail
              zone={detailZone}
              showNumbers={showNumbers}
              onToggleNumbers={() => setShowNumbers(v => !v)}
              onBack={() => setDetailZone(null)}
              onGetRec={() => setShowRec(true)}
            />
          </div>
        )}
      </div>

      {/* Recommendation modal */}
      {showRec && detailZone && (
        <RecommendationModal
          zone={detailZone}
          onClose={() => setShowRec(false)}
        />
      )}
    </div>
  );
}

function ZoneDetail({ zone, showNumbers, onToggleNumbers, onBack, onGetRec }) {
  const lbl = zone.zone_label || zone.zone_id;
  const m  = zone.soil_moisture_20cm;
  const n  = zone.nitrogen_ppm;
  const ph = zone.ph_level;
  const [st, tag] = zoneHealth(m, n, ph);

  const statusColours = {
    good:    { bg: 'var(--green-lt)', text: '#fff' },
    average: { bg: 'var(--amber)',    text: 'var(--soil)' },
    danger:  { bg: 'var(--red)',      text: '#fff' },
    unknown: { bg: 'var(--slate)',    text: '#fff' },
  };
  const { bg, text } = statusColours[st] || statusColours.unknown;

  return (
    <div className="zone-detail-inner">
      {/* Back button (mobile) */}
      <button className="zone-detail__back" onClick={onBack} aria-label="Back to zone list">
        ← Back
      </button>

      {/* Status banner */}
      <div className="zone-detail__banner" style={{ background: bg, color: text }}>
        <h2>Zone {lbl}</h2>
        <span>{tag}</span>
      </div>

      <div className="zone-detail__metrics">
        {/* Plain-language metrics — numbers hidden by default (Progressive Disclosure) */}
        {[
          { icon: '💧', label: 'Water',    ...moistureLabel(m),  raw: m  != null ? `${m.toFixed(1)}%`    : null },
          { icon: '🌿', label: 'Nitrogen', ...nitrogenLabel(n),  raw: n  != null ? `${n.toFixed(0)} ppm` : null },
          { icon: '🧪', label: 'Acidity',  ...phLabel(ph),       raw: ph != null ? `pH ${ph.toFixed(1)}` : null },
        ].map(({ icon, label, text: txt, colour, raw }) => (
          <div key={label} className="metric-row">
            <span className="metric-icon">{icon}</span>
            <div className="metric-text">
              <div className="metric-label">{label}</div>
              <div className="metric-value" style={{ color: colour }}>{txt}</div>
            </div>
            {showNumbers && raw && (
              <span className="metric-raw">{raw}</span>
            )}
          </div>
        ))}

        {/* Progressive disclosure toggle */}
        <button className="toggle-numbers-btn" onClick={onToggleNumbers}>
          {showNumbers ? '▲ Hide numbers' : '▼ Show sensor numbers'}
        </button>
      </div>

      {/* Action buttons */}
      <div className="zone-detail__actions">
        <button className="btn btn--primary" onClick={onGetRec}>
          💡 Get Recommendation
        </button>
      </div>
    </div>
  );
}
