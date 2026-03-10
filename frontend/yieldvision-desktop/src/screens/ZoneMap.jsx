import { useMemo, useState } from "react";
import { statusColor } from "../utils/health";

const SVG_W = 700;
const SVG_H = 380;
const PAD   = 40;

/**
 * ZoneMap — renders the farm as GPS-bounded polygon partitions sent by the rover.
 * Each zone's boundary_coords [[lat,lon],...] draws a filled territory patch.
 * Falls back to an auto-generated grid partition when no boundary data exists.
 *
 * Props:
 *   zones        array of zone objects (with boundary_coords or gps_lat/lon)
 *   selectedId   currently selected zone id
 *   onSelect     (zone) => void
 *   statusOf     (zone) => status string
 *   t            theme
 */
export default function ZoneMap({ zones, selectedId, onSelect, statusOf, t }) {
  const hasBoundaries = zones.some(z => z.boundary_coords?.length >= 3);
  const hasGps        = zones.some(z => z.gps_lat != null && z.gps_lon != null);

  return (
    <PartitionMap
      zones={zones}
      selectedId={selectedId}
      onSelect={onSelect}
      statusOf={statusOf}
      t={t}
      hasBoundaries={hasBoundaries}
      hasGps={hasGps}
    />
  );
}

// ─── Unified partition map ─────────────────────────────────────────────────────

function PartitionMap({ zones, selectedId, onSelect, statusOf, t, hasBoundaries, hasGps }) {
  const [hovered, setHovered] = useState(null);

  // Build a global coordinate space from all vertices across all zones
  const { polygons, centroids } = useMemo(() => {
    if (!zones.length) return { polygons: [], centroids: [] };

    // Collect all lat/lon points from boundaries OR fallback to centroid GPS
    let allLats = [], allLons = [];

    zones.forEach(z => {
      if (z.boundary_coords?.length) {
        z.boundary_coords.forEach(([lat, lon]) => {
          allLats.push(lat); allLons.push(lon);
        });
      } else if (z.gps_lat != null) {
        allLats.push(z.gps_lat); allLons.push(z.gps_lon);
      }
    });

    if (!allLats.length) {
      // No GPS at all — build a symmetric grid
      return buildGridPartitions(zones);
    }

    const minLat = Math.min(...allLats), maxLat = Math.max(...allLats);
    const minLon = Math.min(...allLons), maxLon = Math.max(...allLons);
    const dLat   = (maxLat - minLat) || 0.002;
    const dLon   = (maxLon - minLon) || 0.002;

    // Add 8% margin
    const marginLat = dLat * 0.08;
    const marginLon = dLon * 0.08;
    const eLat = dLat + marginLat * 2;
    const eLon = dLon + marginLon * 2;

    function project(lat, lon) {
      return {
        x: PAD + ((lon - minLon + marginLon) / eLon) * (SVG_W - PAD * 2),
        y: PAD + (1 - (lat - minLat + marginLat) / eLat) * (SVG_H - PAD * 2),
      };
    }

    const polygons = zones.map(z => {
      let verts;
      if (z.boundary_coords?.length >= 3) {
        verts = z.boundary_coords.map(([lat, lon]) => project(lat, lon));
      } else if (z.gps_lat != null) {
        // No boundary — generate a small square patch around the centroid
        const r = 0.0003;
        verts = [
          project(z.gps_lat - r, z.gps_lon - r),
          project(z.gps_lat - r, z.gps_lon + r),
          project(z.gps_lat + r, z.gps_lon + r),
          project(z.gps_lat + r, z.gps_lon - r),
        ];
      } else {
        verts = [];
      }
      return { zone: z, verts, pointsStr: verts.map(v => `${v.x.toFixed(1)},${v.y.toFixed(1)}`).join(" ") };
    });

    const centroids = polygons.map(({ zone, verts }) => {
      if (!verts.length) return null;
      const cx = verts.reduce((s, v) => s + v.x, 0) / verts.length;
      const cy = verts.reduce((s, v) => s + v.y, 0) / verts.length;
      return { zone, cx, cy };
    }).filter(Boolean);

    return { polygons, centroids };
  }, [zones]);

  const isEmpty = polygons.length === 0;

  return (
    <div style={{ position: "relative", width: "100%", background: t.panelLight, borderRadius: 16, overflow: "hidden", border: `1px solid ${t.border}` }}>

      {/* Legend top-right */}
      <div style={{
        position: "absolute", top: 10, right: 12,
        display: "flex", gap: 10, zIndex: 10,
      }}>
        {[
          { label: "Critical", col: statusColor("CRITICAL", t) },
          { label: "Watch",    col: statusColor("HIGH", t) },
          { label: "Healthy",  col: statusColor("GOOD", t) },
        ].map(l => (
          <div key={l.label} style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <div style={{ width: 9, height: 9, borderRadius: 3, background: l.col, opacity: 0.85 }} />
            <span style={{ fontSize: "0.6rem", color: t.textMuted, fontWeight: 600 }}>{l.label}</span>
          </div>
        ))}
      </div>

      {isEmpty ? (
        <div style={{ padding: "60px 0", textAlign: "center" }}>
          <p style={{ color: t.textMuted, fontSize: "0.82rem" }}>No zone data yet. Deploy the rover to scan your farm.</p>
        </div>
      ) : (
        <svg
          viewBox={`0 0 ${SVG_W} ${SVG_H}`}
          style={{ width: "100%", display: "block", cursor: "default" }}
          aria-label="Farm partition map"
        >
          {/* ── Hatched terrain background ── */}
          <defs>
            <pattern id="terrain" patternUnits="userSpaceOnUse" width="14" height="14" patternTransform="rotate(35)">
              <line x1="0" y1="0" x2="0" y2="14" stroke={t.border} strokeWidth="0.6" opacity="0.45" />
            </pattern>
            <filter id="zoneShadow" x="-10%" y="-10%" width="120%" height="120%">
              <feDropShadow dx="0" dy="2" stdDeviation="3" floodOpacity="0.18" />
            </filter>
          </defs>

          {/* Background terrain fill */}
          <rect x="0" y="0" width={SVG_W} height={SVG_H} fill={`url(#terrain)`} />

          {/* ── Zone polygons ── */}
          {polygons.map(({ zone, verts, pointsStr }) => {
            if (!pointsStr) return null;
            const st       = statusOf(zone);
            const color    = statusColor(st, t);
            const isSelect = zone.zone_id === selectedId;
            const isHover  = zone.zone_id === hovered;
            const alpha    = isSelect ? "55" : isHover ? "44" : "2e";

            return (
              <g
                key={zone.zone_id}
                onClick={() => onSelect(zone)}
                onMouseEnter={() => setHovered(zone.zone_id)}
                onMouseLeave={() => setHovered(null)}
                style={{ cursor: "pointer" }}
                role="button"
                aria-label={`Zone ${zone.zone_id}`}
              >
                {/* Fill */}
                <polygon
                  points={pointsStr}
                  fill={color + alpha}
                  filter={isSelect ? "url(#zoneShadow)" : undefined}
                />
                {/* Border */}
                <polygon
                  points={pointsStr}
                  fill="none"
                  stroke={color}
                  strokeWidth={isSelect ? 2.5 : isHover ? 2 : 1.4}
                  strokeLinejoin="round"
                  strokeDasharray={isSelect ? "none" : "5 3"}
                  opacity={isSelect ? 1 : 0.75}
                />
              </g>
            );
          })}

          {/* ── Zone labels at centroids ── */}
          {centroids.map(({ zone, cx, cy }) => {
            const st      = statusOf(zone);
            const color   = statusColor(st, t);
            const isSelect = zone.zone_id === selectedId;
            const r        = isSelect ? 16 : 13;

            return (
              <g
                key={`lbl-${zone.zone_id}`}
                onClick={() => onSelect(zone)}
                onMouseEnter={() => setHovered(zone.zone_id)}
                onMouseLeave={() => setHovered(null)}
                style={{ cursor: "pointer" }}
              >
                {/* Glow ring if selected */}
                {isSelect && (
                  <circle cx={cx} cy={cy} r={r + 6} fill="none" stroke={color} strokeWidth="2" opacity="0.35" />
                )}
                {/* Badge circle */}
                <circle cx={cx} cy={cy} r={r} fill={color} opacity={isSelect ? 1 : 0.92} />
                {/* Zone ID */}
                <text
                  x={cx} y={cy + 4}
                  textAnchor="middle"
                  fontSize={isSelect ? "9" : "8"}
                  fontWeight="800"
                  fill="#fff"
                  style={{ pointerEvents: "none", userSelect: "none", fontFamily: "monospace" }}
                >
                  {zone.zone_id}
                </text>
              </g>
            );
          })}

          {/* ── Tooltip on hover ── */}
          {hovered && (() => {
            const c = centroids.find(c => c.zone.zone_id === hovered);
            if (!c) return null;
            const z = c.zone;
            const st = statusOf(z);
            const col = statusColor(st, t);
            const tx = Math.min(c.cx + 18, SVG_W - 100);
            const ty = Math.max(c.cy - 36, 8);
            return (
              <g style={{ pointerEvents: "none" }}>
                <rect x={tx} y={ty} width="96" height="42" rx="7" fill={t.bgCard} stroke={col} strokeWidth="1.2" opacity="0.96" />
                <text x={tx + 8} y={ty + 14} fontSize="8" fontWeight="700" fill={col}>{z.zone_id} · {z.crop_type || "Unplanted"}</text>
                <text x={tx + 8} y={ty + 26} fontSize="7.5" fill={t.textSub}>💧 {z.soil_moisture_20cm}%  🌿 {z.nitrogen_ppm}N</text>
                <text x={tx + 8} y={ty + 37} fontSize="7" fill={t.textMuted}>pH {z.ph_level}  {z.temperature_c}°C</text>
              </g>
            );
          })()}
        </svg>
      )}

      {/* ── No boundary notice ── */}
      {!isEmpty && !zones.some(z => z.boundary_coords?.length) && (
        <div style={{
          position: "absolute", bottom: 8, left: 0, right: 0,
          textAlign: "center",
          fontSize: "0.63rem", color: t.textMuted,
        }}>
          Approximate positions shown · Rover boundary scan pending
        </div>
      )}
    </div>
  );
}

// ─── Grid partition fallback (no GPS at all) ──────────────────────────────────

function buildGridPartitions(zones) {
  const n    = zones.length;
  const cols = Math.ceil(Math.sqrt(n));
  const rows = Math.ceil(n / cols);
  const cw   = (SVG_W - PAD * 2) / cols;
  const ch   = (SVG_H - PAD * 2) / rows;

  const polygons = zones.map((zone, i) => {
    const col = i % cols;
    const row = Math.floor(i / cols);
    const x   = PAD + col * cw;
    const y   = PAD + row * ch;
    const GAP = 6;
    const verts = [
      { x: x + GAP,      y: y + GAP },
      { x: x + cw - GAP, y: y + GAP },
      { x: x + cw - GAP, y: y + ch - GAP },
      { x: x + GAP,      y: y + ch - GAP },
    ];
    const pointsStr = verts.map(v => `${v.x.toFixed(1)},${v.y.toFixed(1)}`).join(" ");
    return { zone, verts, pointsStr };
  });

  const centroids = polygons.map(({ zone, verts }) => ({
    zone,
    cx: verts.reduce((s, v) => s + v.x, 0) / verts.length,
    cy: verts.reduce((s, v) => s + v.y, 0) / verts.length,
  }));

  return { polygons, centroids };
}
