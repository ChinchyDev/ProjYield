import { useState, useEffect, useCallback } from "react";
import Icon from "@mdi/react";
import {
  mdiRefresh,
  mdiViewGridOutline,
  mdiFormatListBulletedSquare,
  mdiMapSearchOutline,
} from "@mdi/js";
import { getFarmSummary } from "../api";
import { zoneStatus, statusColor, statusLabel, sortByUrgency } from "../utils/health";
import ZoneMap    from "./ZoneMap";
import ZoneDetail from "./ZoneDetail";
import Spinner    from "../components/Spinner";
import Pill       from "../components/Pill";
import SectionHeader from "../components/SectionHeader";

const VIEW_MODES = [
  { id: "map",  icon: mdiMapSearchOutline },
  { id: "grid", icon: mdiViewGridOutline  },
  { id: "list", icon: mdiFormatListBulletedSquare },
];

export default function FarmScreen({ farmId, farmName, t }) {
  const [zones,      setZones]      = useState([]);
  const [loading,    setLoading]    = useState(true);
  const [refresh,    setRefresh]    = useState(0);
  const [viewMode,   setViewMode]   = useState("map");
  const [selectedId, setSelectedId] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    getFarmSummary(farmId)
      .then(data => setZones(sortByUrgency(data.zones || [], z => zoneStatus(z))))
      .catch(() => setZones([]))
      .finally(() => setLoading(false));
  }, [farmId, refresh]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { load(); }, [load]);

  function openZone(zone)  { setSelectedId(zone.zone_id); }
  function closeZone()     { setSelectedId(null); }

  return (
    <div className="h-full flex overflow-hidden">

      {/* ── Left pane: map + zone list ────────────────────────────────── */}
      <div
        className="flex flex-col overflow-hidden transition-all duration-200"
        style={{ width: selectedId ? "42%" : "100%", minWidth: 0 }}
      >
        {/* Toolbar */}
        <div
          className="flex-shrink-0 flex items-center gap-3 px-5 py-3"
          style={{ borderBottom: `1px solid ${t.border}`, background: t.bgCard }}
        >
          <h1 className="text-base font-bold flex-1" style={{ color: t.textPrimary }}>
            {farmName || "My Farm"}
          </h1>
          <span className="text-sm" style={{ color: t.textMuted }}>
            {zones.length} zones
          </span>

          {/* View-mode toggle */}
          <div
            className="flex rounded-xl overflow-hidden"
            style={{ border: `1px solid ${t.border}` }}
          >
            {VIEW_MODES.map(({ id, icon }) => (
              <button
                key={id}
                onClick={() => setViewMode(id)}
                className="flex items-center justify-center transition-colors no-focus-ring"
                style={{
                  width:      "32px",
                  height:     "32px",
                  background: viewMode === id ? t.panel : "transparent",
                }}
                aria-label={id}
              >
                <Icon path={icon} size={0.6} color={viewMode === id ? t.panelText : t.textMuted} />
              </button>
            ))}
          </div>

          <button
            onClick={() => setRefresh(r => r + 1)}
            className="flex items-center justify-center rounded-xl no-focus-ring transition-opacity hover:opacity-70"
            style={{ width: "32px", height: "32px", background: t.panelLight }}
            aria-label="Refresh zones"
          >
            <Icon path={mdiRefresh} size={0.62} color={t.textSub} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto">
          {loading && <Spinner t={t} />}

          {!loading && zones.length === 0 && (
            <div className="flex flex-col items-center gap-3 py-16 text-center px-6">
              <Icon path={mdiMapSearchOutline} size={2.5} color={t.textMuted} />
              <p className="font-semibold" style={{ color: t.textPrimary }}>No zones found</p>
              <p className="text-sm" style={{ color: t.textSub }}>
                Deploy your rover to scan and map your farm zones.
              </p>
            </div>
          )}

          {!loading && zones.length > 0 && (
            <div className="px-5 pt-4 flex flex-col gap-4" style={{ paddingBottom: "90px" }}>
              {/* Map view */}
              {viewMode === "map" && (
                <>
                  <ZoneMap
                    zones={zones}
                    selectedId={selectedId}
                    onSelect={openZone}
                    statusOf={z => zoneStatus(z)}
                    t={t}
                  />
                  <SectionHeader title="All Zones" t={t} />
                  <ZoneList zones={zones} selectedId={selectedId} onSelect={openZone} t={t} />
                </>
              )}

              {/* Grid view */}
              {viewMode === "grid" && (
                <ZoneCardGrid zones={zones} selectedId={selectedId} onSelect={openZone} t={t} />
              )}

              {/* List view */}
              {viewMode === "list" && (
                <ZoneList zones={zones} selectedId={selectedId} onSelect={openZone} t={t} />
              )}
            </div>
          )}
        </div>
      </div>

      {/* ── Right pane: zone detail ───────────────────────────────────── */}
      {selectedId && (
        <div
          className="flex-1 overflow-hidden border-l animate-slide-in"
          style={{ borderColor: t.border, background: t.bg }}
        >
          <ZoneDetail
            zoneId={selectedId}
            farmId={farmId}
            onBack={closeZone}
            t={t}
          />
        </div>
      )}
    </div>
  );
}

// ─── Zone list (compact rows) ─────────────────────────────────────────────────

function ZoneList({ zones, selectedId, onSelect, t }) {
  return (
    <div
      className="rounded-2xl overflow-hidden"
      style={{ border: `1px solid ${t.border}`, background: t.bgCard }}
    >
      {zones.map((zone, i) => {
        const st      = zoneStatus(zone);
        const color   = statusColor(st, t);
        const isSelect = zone.zone_id === selectedId;

        return (
          <button
            key={zone.zone_id}
            onClick={() => onSelect(zone)}
            className="w-full flex items-center gap-3 px-4 py-3.5 text-left transition-colors no-focus-ring hover:opacity-90"
            style={{
              background:   isSelect ? t.panelLight : "transparent",
              borderBottom: i < zones.length - 1 ? `1px solid ${t.border}` : "none",
            }}
          >
            {/* Status stripe */}
            <div
              className="w-1 rounded-full flex-shrink-0"
              style={{ height: "32px", background: color }}
            />

            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="font-semibold text-sm truncate" style={{ color: t.textPrimary }}>
                  Zone {zone.zone_id}
                </span>
                <Pill label={statusLabel(st)} color={color} size="sm" />
              </div>

              {/* Quick readings */}
              <div className="flex gap-4 mt-0.5">
                {zone.soil_moisture_20cm != null && (
                  <QuickVal label="Moisture" val={`${zone.soil_moisture_20cm.toFixed(0)}%`} t={t} />
                )}
                {zone.nitrogen_ppm != null && (
                  <QuickVal label="N" val={`${zone.nitrogen_ppm.toFixed(0)} ppm`} t={t} />
                )}
                {zone.ph_level != null && (
                  <QuickVal label="pH" val={zone.ph_level.toFixed(1)} t={t} />
                )}
              </div>
            </div>

            <span style={{ color: t.textMuted, fontSize: "1rem" }}>›</span>
          </button>
        );
      })}
    </div>
  );
}

// ─── Zone card grid ───────────────────────────────────────────────────────────

function ZoneCardGrid({ zones, selectedId, onSelect, t }) {
  return (
    <div className="grid grid-cols-2 gap-3">
      {zones.map(zone => {
        const st      = zoneStatus(zone);
        const color   = statusColor(st, t);
        const isSelect = zone.zone_id === selectedId;

        return (
          <button
            key={zone.zone_id}
            onClick={() => onSelect(zone)}
            className="rounded-2xl p-4 flex flex-col gap-3 text-left transition-all no-focus-ring hover:opacity-90"
            style={{
              background: isSelect ? t.panelLight : t.bgCard,
              border:     `2px solid ${isSelect ? color : t.border}`,
              backdropFilter: "blur(10px)",
            }}
          >
            {/* Zone label + status dot */}
            <div className="flex items-center justify-between">
              <span className="font-bold text-sm" style={{ color: t.textPrimary }}>
                Zone {zone.zone_id}
              </span>
              <span
                className="w-2.5 h-2.5 rounded-full"
                style={{ background: color }}
              />
            </div>

            <Pill label={statusLabel(st)} color={color} size="sm" />

            {/* Readings */}
            <div className="flex flex-col gap-1.5">
              {zone.soil_moisture_20cm != null && (
                <MiniBar
                  label="Moisture"
                  val={zone.soil_moisture_20cm}
                  max={100}
                  color={color}
                  t={t}
                />
              )}
              {zone.nitrogen_ppm != null && (
                <MiniBar
                  label="Nitrogen"
                  val={zone.nitrogen_ppm}
                  max={200}
                  color={color}
                  t={t}
                />
              )}
            </div>
          </button>
        );
      })}
    </div>
  );
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function QuickVal({ label, val, t }) {
  return (
    <span style={{ fontSize: "0.7rem", color: t.textMuted }}>
      <span style={{ fontWeight: 600 }}>{label}: </span>
      {val}
    </span>
  );
}

function MiniBar({ label, val, max, color, t }) {
  const pct = Math.min(100, Math.round((val / max) * 100));
  return (
    <div className="flex flex-col gap-0.5">
      <div className="flex justify-between" style={{ fontSize: "0.65rem", color: t.textMuted }}>
        <span>{label}</span>
        <span style={{ fontWeight: 700 }}>{val.toFixed(0)}</span>
      </div>
      <div
        className="w-full rounded-full overflow-hidden"
        style={{ height: "3px", background: t.border }}
      >
        <div
          style={{
            width:        `${pct}%`,
            height:       "100%",
            background:   color,
            borderRadius: "99px",
            transition:   "width 0.4s ease",
          }}
        />
      </div>
    </div>
  );
}
