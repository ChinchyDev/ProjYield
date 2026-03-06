import React, { useMemo, useRef, useEffect } from 'react';
import { zoneHealth } from '../utils/labels';
import './Reports.css';

function zoneScore(zone) {
  const m  = zone.soil_moisture_20cm;
  const n  = zone.nitrogen_ppm;
  const ph = zone.ph_level;
  const parts = [];
  if (m  != null) parts.push(Math.min(100, (m  / 50)  * 100));
  if (n  != null) parts.push(Math.min(100, (n  / 150) * 100));
  if (ph != null) {
    const s = (ph >= 6.0 && ph <= 7.0) ? 100 : Math.max(0, 100 - Math.abs(ph - 6.5) * 30);
    parts.push(s);
  }
  return parts.length ? parts.reduce((a, b) => a + b, 0) / parts.length : 50;
}

function BarChart({ zones }) {
  const canvasRef = useRef(null);
  const data = zones.slice(0, 20);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !data.length) return;
    const ctx = canvas.getContext('2d');
    const W = canvas.width  = canvas.offsetWidth;
    const H = canvas.height = canvas.offsetHeight;
    ctx.clearRect(0, 0, W, H);

    const ML = 36, MB = 28, MT = 10;
    const plotW = W - ML - 10;
    const plotH = H - MB - MT;
    const n     = data.length;
    const barW  = Math.max(8, Math.floor(plotW / n) - 4);

    // Grid lines
    [0, 25, 50, 75, 100].forEach(pct => {
      const y = MT + plotH - Math.round(plotH * pct / 100);
      ctx.strokeStyle = '#DDD8CE';
      ctx.setLineDash([3, 3]);
      ctx.beginPath(); ctx.moveTo(ML, y); ctx.lineTo(W - 10, y); ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = '#6C8EBF';
      ctx.font = '10px Segoe UI,sans-serif';
      ctx.textAlign = 'right';
      ctx.fillText(String(pct), ML - 4, y + 3);
    });

    // Bars
    const statusColours = { good: '#52B788', average: '#E9A826', danger: '#D62828', unknown: '#6C8EBF' };
    data.forEach((zone, i) => {
      const score = zoneScore(zone);
      const [st]  = zoneHealth(zone.soil_moisture_20cm, zone.nitrogen_ppm, zone.ph_level);
      const x     = ML + i * (barW + 4) + 2;
      const bh    = Math.round(plotH * score / 100);
      const y0    = MT + plotH - bh;

      ctx.fillStyle = statusColours[st] || '#6C8EBF';
      ctx.beginPath();
      ctx.roundRect(x, y0, barW, bh, [4, 4, 0, 0]);
      ctx.fill();

      // Label
      const lbl = zone.zone_label || zone.zone_id || '?';
      ctx.fillStyle = '#6C8EBF';
      ctx.font = n > 12 ? '8px Segoe UI,sans-serif' : '10px Segoe UI,sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(lbl.slice(0, 4), x + barW / 2, H - 6);
    });
  }, [data]);

  return <canvas ref={canvasRef} className="report-canvas" aria-label="Soil health bar chart" />;
}

export default function Reports({ zones }) {
  const sorted = useMemo(() => [...zones].sort((a, b) => zoneScore(b) - zoneScore(a)), [zones]);
  const avg    = useMemo(() => zones.length ? Math.round(zones.reduce((s, z) => s + zoneScore(z), 0) / zones.length) : null, [zones]);
  const counts = useMemo(() => {
    const c = { good: 0, average: 0, danger: 0 };
    zones.forEach(z => {
      const [st] = zoneHealth(z.soil_moisture_20cm, z.nitrogen_ppm, z.ph_level);
      if (st in c) c[st]++;
    });
    return c;
  }, [zones]);

  return (
    <div className="screen reports-screen">
      <div className="page-header">
        <h1>📊 Reports</h1>
        <p>Your farm performance at a glance</p>
      </div>

      {zones.length === 0 && (
        <div className="loader">
          <span className="loader-icon">🌱</span>
          <p>Loading your farm data…</p>
        </div>
      )}

      {zones.length > 0 && (
        <>
          {/* Summary stats */}
          <p className="section-label">Farm Summary</p>
          <div className="stats-row">
            <div className="stat-card">
              <span className="stat-value" style={{ color: 'var(--green)' }}>{avg ?? '—'}</span>
              <span className="stat-label">Average health score</span>
            </div>
            <div className="stat-card">
              <span className="stat-value" style={{ color: 'var(--green-lt)' }}>{counts.good}</span>
              <span className="stat-label">🟢 Healthy zones</span>
            </div>
            <div className="stat-card">
              <span className="stat-value" style={{ color: 'var(--red)' }}>{counts.danger}</span>
              <span className="stat-label">🔴 Urgent zones</span>
            </div>
          </div>

          {/* Bar chart — plain axes, no 3D, annotated labels */}
          <p className="section-label">Soil Health Score by Zone</p>
          <div className="card report-chart-card">
            <p className="chart-legend">
              <span style={{ color: 'var(--green-lt)' }}>■ Healthy</span>
              <span style={{ color: 'var(--amber)' }}>■ Watch</span>
              <span style={{ color: 'var(--red)' }}>■ Urgent</span>
              <span style={{ color: 'var(--slate)', marginLeft: 'auto' }}>Higher = better</span>
            </p>
            <BarChart zones={zones} />
          </div>

          {/* Top performers */}
          <p className="section-label">Top Performing Zones</p>
          <div className="card">
            {sorted.slice(0, 5).map((z, i) => {
              const score = Math.round(zoneScore(z));
              const lbl   = z.zone_label || z.zone_id;
              const [st]  = zoneHealth(z.soil_moisture_20cm, z.nitrogen_ppm, z.ph_level);
              const colours = { good: 'var(--green-lt)', average: 'var(--amber)', danger: 'var(--red)', unknown: 'var(--slate)' };
              return (
                <div key={z.zone_id} className="top-zone-row card-body">
                  <span className="top-zone-rank">#{i + 1}</span>
                  <span className="top-zone-label">Zone {lbl}</span>
                  <div className="top-zone-bar-wrap">
                    <div className="top-zone-bar-bg">
                      <div className="top-zone-bar-fill" style={{ width: `${score}%`, background: colours[st] }} />
                    </div>
                  </div>
                  <span className="top-zone-score" style={{ color: colours[st] }}>{score}</span>
                </div>
              );
            })}
          </div>

          <p style={{ padding: '12px 16px', fontSize: '0.78rem', color: 'var(--slate)' }}>
            💡 Share this report with your agricultural extension officer for expert advice.
          </p>
        </>
      )}
    </div>
  );
}
