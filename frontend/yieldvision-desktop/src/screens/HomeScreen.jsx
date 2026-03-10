import { useState, useEffect, useCallback } from "react";
import Icon from "@mdi/react";
import {
  mdiAlertCircle,
  mdiCheckCircle,
  mdiAlertOutline,
  mdiRefresh,
  mdiRobotMower,
  mdiClockOutline,
  mdiArrowRight,
  mdiLeaf,
  mdiWater,
  mdiThermometer,
  mdiMapMarker,
} from "@mdi/js";
import { getFarmSummary, getRoverSchedule, getPendingRecommendations } from "../api";
import { zoneStatus, statusColor, statusLabel, sortByUrgency } from "../utils/health";
import Spinner from "../components/Spinner";
import SectionHeader from "../components/SectionHeader";
import Pill from "../components/Pill";

// ── Unsplash free farm & crop images ────────────────────────────────
const FARM_HERO =
  "https://images.unsplash.com/photo-1500382017468-9049fed747ef?w=1400&h=260&fit=crop&crop=bottom&auto=format&q=80";

const CROP_IMGS = {
  Maize:   "https://images.unsplash.com/photo-1601593346740-925612772716?w=420&h=160&fit=crop&auto=format&q=75",
  Beans:   "https://images.unsplash.com/photo-1567306226416-28f0efdc88ce?w=420&h=160&fit=crop&auto=format&q=75",
  Sorghum: "https://images.unsplash.com/photo-1574943320219-553eb213f72d?w=420&h=160&fit=crop&auto=format&q=75",
  Cassava: "https://images.unsplash.com/photo-1597916829826-02e5bb4a54e0?w=420&h=160&fit=crop&auto=format&q=75",
  Wheat:   "https://images.unsplash.com/photo-1574943320219-553eb213f72d?w=420&h=160&fit=crop&auto=format&q=75",
};
const FIELD_DEFAULT = "https://images.unsplash.com/photo-1416879595882-3373a0480b5b?w=420&h=160&fit=crop&auto=format&q=75";
const FIELD_DRY     = "https://images.unsplash.com/photo-1560493676-04071c5f467b?w=420&h=160&fit=crop&auto=format&q=75";

function getCropImg(cropType, status) {
  if (status === "CRITICAL" || status === "DANGER") return FIELD_DRY;
  return CROP_IMGS[cropType] || FIELD_DEFAULT;
}

function greeting() {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}

function fmtDate() {
  return new Date().toLocaleDateString("en-KE", {
    weekday: "long", day: "numeric", month: "long",
  });
}

function MetricChip({ icon, value, t }) {
  return (
    <div className="flex items-center gap-1">
      <Icon path={icon} size={0.48} color={t.textMuted} />
      <span style={{ fontSize: "0.68rem", color: t.textMuted, fontWeight: 500 }}>{value}</span>
    </div>
  );
}

const URGENCY_ICON = {
  CRITICAL: mdiAlertCircle,
  HIGH:     mdiAlertOutline,
  MEDIUM:   mdiAlertOutline,
  LOW:      mdiCheckCircle,
};

const URGENCY_COL = {
  CRITICAL: "#E53935",
  HIGH:     "#FF6F00",
  MEDIUM:   "#F9A825",
  LOW:      "#388E3C",
};

export default function HomeScreen({ session, t, onNavigate }) {
  const { farm_id, farm_name, owner_name } = session;
  const [loading, setLoading] = useState(true);
  const [zones,   setZones]   = useState([]);
  const [rover,   setRover]   = useState(null);
  const [tasks,   setTasks]   = useState([]);
  const [error,   setError]   = useState("");

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const [summary, roverData, recData] = await Promise.all([
        getFarmSummary(farm_id),
        getRoverSchedule(farm_id).catch(() => null),
        getPendingRecommendations(farm_id).catch(() => ({ recommendations: [] })),
      ]);
      setZones(sortByUrgency(summary.zones || [], z => zoneStatus(z)));
      setRover(roverData);
      const recs = Array.isArray(recData)
        ? recData
        : (recData?.recommendations || recData?.top_actions || []);
      setTasks(sortByUrgency(recs.filter(r => r.status === "pending"), r => r.urgency));
    } catch (e) {
      setError(e.message || "Failed to load farm data.");
    } finally {
      setLoading(false);
    }
  }, [farm_id]);

  useEffect(() => { load(); }, [load]);

  const criticalZones = zones.filter(z =>
    ["CRITICAL", "DANGER"].includes(zoneStatus(z)));

  const counts = {
    total:    zones.length,
    healthy:  zones.filter(z => zoneStatus(z) === "GOOD").length,
    watch:    zones.filter(z => ["MEDIUM", "HIGH"].includes(zoneStatus(z))).length,
    critical: criticalZones.length,
  };

  return (
    <div className="h-full overflow-y-auto" style={{ background: t.bg }}>

      {/* ── Hero banner ───────────────────────────────────────────────── */}
      <div style={{ position: "relative", height: 200, overflow: "hidden", flexShrink: 0 }}>
        <img
          src={FARM_HERO} alt="Farm"
          style={{ width: "100%", height: "100%", objectFit: "cover", objectPosition: "center 60%" }}
        />
        <div style={{
          position: "absolute", inset: 0,
          background: "linear-gradient(120deg, rgba(0,0,0,0.72) 0%, rgba(0,0,0,0.3) 55%, rgba(0,0,0,0.08) 100%)",
        }} />
        <div style={{ position: "absolute", bottom: 0, left: 0, right: 0, padding: "0 24px 20px" }}>
          <p style={{ color: "rgba(255,255,255,0.72)", fontSize: "0.73rem", fontWeight: 500, marginBottom: 4 }}>
            {fmtDate()}
          </p>
          <h1 style={{ color: "#fff", fontWeight: 800, fontSize: "1.55rem", lineHeight: 1.1, margin: 0 }}>
            {greeting()}, {(owner_name || "Farmer").split(" ")[0]}
          </h1>
          <div className="flex items-center gap-1.5" style={{ marginTop: 6 }}>
            <Icon path={mdiMapMarker} size={0.48} color="rgba(255,255,255,0.62)" />
            <span style={{ color: "rgba(255,255,255,0.62)", fontSize: "0.76rem" }}>{farm_name}</span>
          </div>
        </div>
        <button
          onClick={load}
          className="no-focus-ring"
          style={{
            position: "absolute", top: 14, right: 14,
            display: "flex", alignItems: "center", gap: 5,
            background: "rgba(0,0,0,0.38)", border: "1px solid rgba(255,255,255,0.2)",
            backdropFilter: "blur(8px)", borderRadius: 12,
            padding: "6px 12px", color: "#fff", fontSize: "0.75rem", fontWeight: 600,
            cursor: "pointer",
          }}
        >
          <Icon path={mdiRefresh} size={0.5} />
          Refresh
        </button>
      </div>

      {/* ── Body ──────────────────────────────────────────────────────── */}
      {loading ? (
        <div style={{ display: "flex", justifyContent: "center", padding: "60px 0" }}>
          <Spinner t={t} />
        </div>
      ) : error ? (
        <div style={{ margin: 20, padding: 16, borderRadius: 16, background: t.red + "22", color: t.red, fontSize: "0.85rem" }}>
          {error}
        </div>
      ) : (
        <div style={{ padding: "20px 20px 100px" }}>

          {/* ─── Two-column layout ─────────────────────────────────── */}
          <div style={{ display: "flex", gap: 20, alignItems: "flex-start" }}>

            {/* ── LEFT: critical banner + zone cards ───────────────── */}
            <div style={{ flex: 1, minWidth: 0 }}>

              {/* Critical alert banner */}
              {criticalZones.length > 0 && (
                <button
                  onClick={() => onNavigate?.("alerts")}
                  className="no-focus-ring w-full"
                  style={{
                    display: "flex", alignItems: "center", gap: 12,
                    background: "#E53935",
                    boxShadow: "0 4px 18px rgba(229,57,53,0.40)",
                    borderRadius: 16, padding: "12px 16px",
                    marginBottom: 16, cursor: "pointer", border: "none", textAlign: "left", width: "100%",
                  }}
                >
                  <Icon path={mdiAlertCircle} size={0.9} color="#fff" />
                  <div style={{ flex: 1 }}>
                    <p style={{ color: "#fff", fontWeight: 700, fontSize: "0.88rem", margin: 0 }}>
                      {criticalZones.length === 1
                        ? `Zone ${criticalZones[0].zone_id} needs action now`
                        : `${criticalZones.length} zones need urgent attention`}
                    </p>
                    <p style={{ color: "rgba(255,255,255,0.82)", fontSize: "0.73rem", marginTop: 2 }}>
                      {criticalZones[0].soil_moisture_20cm != null
                        ? `Soil critically dry — ${criticalZones[0].soil_moisture_20cm}% moisture`
                        : "Tap to view recommendations"}
                    </p>
                  </div>
                  <Icon path={mdiArrowRight} size={0.7} color="rgba(255,255,255,0.65)" />
                </button>
              )}

              {/* Zone grid header */}
              <SectionHeader
                title={`Zone Status · ${zones.length} zones`}
                t={t}
                action={{ label: "View map →", onClick: () => onNavigate?.("farm") }}
              />

              {/* Zone cards — auto-fill 3-column grid */}
              <div style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(190px, 1fr))",
                gap: 12,
                marginTop: 10,
              }}>
                {zones.map(zone => {
                  const st  = zoneStatus(zone);
                  const col = statusColor(st, t);
                  const img = getCropImg(zone.crop_type, st);
                  return (
                    <button
                      key={zone.zone_id}
                      onClick={() => onNavigate?.("farm")}
                      className="no-focus-ring"
                      style={{
                        background: t.bgCard,
                        border: `1px solid ${t.border}`,
                        borderTop: `3px solid ${col}`,
                        borderRadius: 16,
                        overflow: "hidden",
                        cursor: "pointer",
                        textAlign: "left",
                        transition: "transform 0.13s, box-shadow 0.13s",
                        boxShadow: "0 2px 10px rgba(0,0,0,0.07)",
                      }}
                      onMouseEnter={e => {
                        e.currentTarget.style.transform = "translateY(-3px)";
                        e.currentTarget.style.boxShadow = "0 8px 24px rgba(0,0,0,0.13)";
                      }}
                      onMouseLeave={e => {
                        e.currentTarget.style.transform = "";
                        e.currentTarget.style.boxShadow = "0 2px 10px rgba(0,0,0,0.07)";
                      }}
                    >
                      {/* Crop photo */}
                      <div style={{ position: "relative", height: 92 }}>
                        <img
                          src={img}
                          alt={zone.crop_type || "Field"}
                          style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
                          onError={e => { e.target.src = FIELD_DEFAULT; }}
                        />
                        <div style={{
                          position: "absolute", inset: 0,
                          background: "linear-gradient(to bottom, rgba(0,0,0,0.08) 0%, rgba(0,0,0,0.58) 100%)",
                        }} />
                        {/* Zone label */}
                        <div style={{
                          position: "absolute", bottom: 0, left: 0, right: 0,
                          padding: "0 10px 8px",
                          display: "flex", alignItems: "flex-end", justifyContent: "space-between",
                        }}>
                          <span style={{ color: "#fff", fontWeight: 700, fontSize: "0.82rem" }}>
                            Zone {zone.zone_id}
                          </span>
                          {zone.crop_type && (
                            <span style={{ color: "rgba(255,255,255,0.8)", fontSize: "0.63rem", fontStyle: "italic" }}>
                              {zone.crop_type}
                            </span>
                          )}
                        </div>
                        {/* Status glow dot */}
                        <div style={{
                          position: "absolute", top: 8, right: 8,
                          width: 9, height: 9, borderRadius: "50%",
                          background: col, boxShadow: `0 0 7px ${col}`,
                        }} />
                      </div>

                      {/* Card body */}
                      <div style={{ padding: "10px 12px 12px" }}>
                        <span style={{
                          display: "inline-block",
                          background: col + "28", color: col,
                          fontSize: "0.63rem", fontWeight: 700,
                          borderRadius: 999, padding: "2px 8px", marginBottom: 8,
                        }}>
                          {statusLabel(st)}
                        </span>
                        <div style={{ display: "flex", gap: 12 }}>
                          {zone.soil_moisture_20cm != null && (
                            <MetricChip icon={mdiWater} value={`${zone.soil_moisture_20cm}%`} t={t} />
                          )}
                          {zone.nitrogen_ppm != null && (
                            <MetricChip icon={mdiLeaf} value={`${zone.nitrogen_ppm}N`} t={t} />
                          )}
                          {zone.temperature_c != null && (
                            <MetricChip icon={mdiThermometer} value={`${zone.temperature_c}°`} t={t} />
                          )}
                        </div>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* ── RIGHT: stats + tasks + rover ─────────────────────── */}
            <div style={{ width: 272, flexShrink: 0, display: "flex", flexDirection: "column", gap: 18 }}>

              {/* Farm stat tiles 2×2 */}
              <div>
                <SectionHeader title="Farm Overview" t={t} />
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginTop: 10 }}>
                  {[
                    { label: "Total Zones", val: counts.total,    col: t.accent },
                    { label: "Healthy",     val: counts.healthy,  col: t.green  },
                    { label: "Watch",       val: counts.watch,    col: t.amber  },
                    { label: "Critical",    val: counts.critical, col: t.red    },
                  ].map(s => (
                    <div
                      key={s.label}
                      style={{
                        background: t.bgCard, border: `1px solid ${t.border}`,
                        borderRadius: 14, padding: "12px 14px",
                      }}
                    >
                      <span style={{ display: "block", fontSize: "1.6rem", fontWeight: 800, color: s.col, lineHeight: 1 }}>
                        {s.val}
                      </span>
                      <span style={{ display: "block", fontSize: "0.7rem", color: t.textMuted, marginTop: 4 }}>
                        {s.label}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Urgent tasks */}
              {tasks.length > 0 && (
                <div>
                  <SectionHeader
                    title="Urgent Tasks"
                    t={t}
                    action={{ label: "All →", onClick: () => onNavigate?.("tasks") }}
                  />
                  <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 10 }}>
                    {tasks.slice(0, 3).map(task => {
                      const col = URGENCY_COL[task.urgency] || t.textSub;
                      return (
                        <div
                          key={task.id}
                          style={{
                            background: t.bgCard,
                            border: `1px solid ${t.border}`,
                            borderLeft: `3px solid ${col}`,
                            borderRadius: 12,
                            padding: "10px 12px",
                            display: "flex", alignItems: "flex-start", gap: 8,
                          }}
                        >
                          <Icon
                            path={URGENCY_ICON[task.urgency] || mdiAlertOutline}
                            size={0.65} color={col}
                            style={{ flexShrink: 0, marginTop: 1 }}
                          />
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <p style={{ color: t.textPrimary, fontSize: "0.75rem", fontWeight: 600, margin: 0, lineHeight: 1.35 }}>
                              {task.action_label}
                            </p>
                            <p style={{ color: t.textMuted, fontSize: "0.68rem", marginTop: 2 }}>
                              Zone {task.zone_id}
                            </p>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Rover */}
              {rover && (
                <div>
                  <SectionHeader title="Rover" t={t} />
                  <div style={{
                    marginTop: 10, background: t.bgCard, border: `1px solid ${t.border}`,
                    borderRadius: 14, padding: "12px 14px",
                    display: "flex", alignItems: "center", gap: 12,
                  }}>
                    <div style={{
                      width: 40, height: 40, borderRadius: 12, flexShrink: 0,
                      background: t.panelLight,
                      display: "flex", alignItems: "center", justifyContent: "center",
                    }}>
                      <Icon path={mdiRobotMower} size={0.85} color={t.accent} />
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <p style={{ color: t.textPrimary, fontWeight: 600, fontSize: "0.82rem", margin: 0 }}>
                        {rover.rover_id || "Rover"}
                      </p>
                      <div style={{ display: "flex", alignItems: "center", gap: 4, marginTop: 3 }}>
                        <Icon path={mdiClockOutline} size={0.48} color={t.textMuted} />
                        <span style={{ fontSize: "0.68rem", color: t.textMuted }}>
                          {rover.last_scan
                            ? `Last: ${new Date(rover.last_scan).toLocaleTimeString("en-KE", { hour: "2-digit", minute: "2-digit" })}`
                            : "No scan data"}
                        </span>
                      </div>
                    </div>
                    <Pill
                      label={rover.status === "scanning" ? "Active" : "Idle"}
                      color={rover.status === "scanning" ? t.green : t.panelLight}
                      textCol={rover.status === "scanning" ? "#fff" : t.textSub}
                    />
                  </div>
                </div>
              )}

              {/* Empty state (no zones) */}
              {zones.length === 0 && (
                <div style={{
                  background: t.bgCard, border: `1px solid ${t.border}`,
                  borderRadius: 16, padding: "24px 16px",
                  display: "flex", flexDirection: "column", alignItems: "center", gap: 10, textAlign: "center",
                }}>
                  <Icon path={mdiRobotMower} size={1.8} color={t.textMuted} />
                  <p style={{ color: t.textPrimary, fontWeight: 600, fontSize: "0.85rem", margin: 0 }}>No zones yet</p>
                  <p style={{ color: t.textSub, fontSize: "0.75rem", margin: 0 }}>Deploy the rover to scan your farm.</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
