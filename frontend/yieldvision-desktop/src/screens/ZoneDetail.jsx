import { useState, useEffect } from "react";
import Icon from "@mdi/react";
import {
  mdiArrowLeft,
  mdiWater,
  mdiThermometer,
  mdiLeaf,
  mdiFlask,
  mdiCheckCircle,
  mdiCloseCircleOutline,
  mdiReload,
  mdiSprout,
  mdiAlertCircle,
  mdiChevronDown,
  mdiChevronUp,
  mdiSeed,
  mdiCalendarMonth,
} from "@mdi/js";
import { getZoneState, generateRecommendations, applyRecommendation } from "../api";
import {
  zoneStatus, statusColor, statusLabel,
  moistureLabel, nitrogenLabel, phLabel,
  suggestCrops,
} from "../utils/health";
import { urgencyColors } from "../theme";
import StatCard from "../components/StatCard";
import Pill from "../components/Pill";
import Spinner from "../components/Spinner";

export default function ZoneDetail({ zoneId, farmId, onBack, t }) {
  const [state,    setState]    = useState(null);
  const [recs,     setRecs]     = useState([]);
  const [loadSt,   setLoadSt]   = useState(true);
  const [loadRec,  setLoadRec]  = useState(false);
  const [err,      setErr]      = useState("");
  const [acting,   setActing]   = useState({});
  const [showRaw,  setShowRaw]  = useState(false);

  // Load zone state
  useEffect(() => {
    if (!zoneId) return;
    setLoadSt(true);
    setErr("");
    getZoneState(zoneId, farmId)
      .then(data => setState(data))
      .catch(() => setErr("Could not load zone data."))
      .finally(() => setLoadSt(false));
  }, [zoneId, farmId]);

  // Auto-generate recommendations once state loaded
  useEffect(() => {
    if (!state) return;
    setLoadRec(true);
    generateRecommendations(zoneId, farmId)
      .then(data => {
        const all = Array.isArray(data) ? data : (data.recommendations || data.top_actions || []);
        // Sort: CRITICAL → HIGH → MEDIUM → LOW
        const ORDER = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 };
        setRecs([...all].sort(
          (a, b) => (ORDER[(a.urgency || "LOW").toUpperCase()] ?? 3)
                  - (ORDER[(b.urgency || "LOW").toUpperCase()] ?? 3)
        ));
      })
      .catch(() => setRecs([]))
      .finally(() => setLoadRec(false));
  }, [state, zoneId, farmId]);

  async function handleApply(rec, wasApplied) {
    const key = wasApplied ? "applying" : "skipping";
    setActing(prev => ({ ...prev, [rec.id]: key }));
    try {
      await applyRecommendation(rec.id, farmId, wasApplied);
      setRecs(prev =>
        prev.map(r => r.id === rec.id
          ? { ...r, status: wasApplied ? "applied" : "skipped" }
          : r
        )
      );
    } catch {
      // silent
    } finally {
      setActing(prev => { const n = { ...prev }; delete n[rec.id]; return n; });
    }
  }

  if (loadSt) return (
    <div className="h-full flex items-center justify-center">
      <Spinner t={t} />
    </div>
  );

  if (err) return (
    <div className="h-full flex flex-col items-center justify-center gap-3 p-8 text-center">
      <Icon path={mdiAlertCircle} size={2} color={t.red} />
      <p style={{ color: t.textSub, fontSize: "0.88rem" }}>{err}</p>
      <button
        onClick={() => window.location.reload()}
        className="rounded-xl px-4 py-2 font-semibold text-sm no-focus-ring"
        style={{ background: t.accentMuted, color: t.accent }}
      >
        Retry
      </button>
    </div>
  );

  if (!state) return null;

  const readings   = state.readings || state;
  const st         = zoneStatus(readings);
  const stColor    = statusColor(st, t);
  const hasCrop    = !!(state.crop_type || readings.crop_type);
  const cropName   = state.crop_type || readings.crop_type || "";
  const lastScan   = state.last_updated || state.timestamp;
  const cropSugg   = !hasCrop ? suggestCrops(readings) : [];

  return (
    <div className="h-full overflow-y-auto flex flex-col" style={{ paddingBottom: "90px" }}>

      {/* ── Header bar ────────────────────────────────────────────────── */}
      <div
        className="flex-shrink-0 flex items-center gap-3 px-5 py-3 sticky top-0 z-10 glass"
        style={{ background: t.bgCard, borderBottom: `1px solid ${t.border}` }}
      >
        <button
          onClick={onBack}
          className="flex items-center justify-center rounded-xl no-focus-ring transition-opacity hover:opacity-70"
          style={{ width: "34px", height: "34px", background: t.panelLight }}
          aria-label="Back"
        >
          <Icon path={mdiArrowLeft} size={0.7} color={t.textSub} />
        </button>

        <div className="flex-1 min-w-0">
          <h2 className="font-bold text-base leading-tight truncate" style={{ color: t.textPrimary }}>
            Zone {zoneId}
          </h2>
          {lastScan && (
            <p className="text-xs truncate" style={{ color: t.textMuted }}>
              Scanned {new Date(lastScan).toLocaleString("en-KE", {
                day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
              })}
            </p>
          )}
        </div>

        <Pill label={statusLabel(st)} color={stColor} size="md" />
      </div>

      <div className="flex flex-col gap-5 px-5 pt-4">

        {/* ── Crop badge ─────────────────────────────────────────────── */}
        <div className="flex items-center gap-2">
          <Icon path={mdiSprout} size={0.72} color={hasCrop ? t.accent : t.textMuted} />
          {hasCrop
            ? <span className="font-semibold text-sm" style={{ color: t.textPrimary }}>{cropName}</span>
            : <span className="text-sm" style={{ color: t.textMuted }}>No crop detected in this zone</span>
          }
        </div>

        {/* ── Metrics grid ───────────────────────────────────────────── */}
        <div className="grid grid-cols-2 gap-3">
          <StatCard
            icon={mdiWater}
            label="Soil Moisture"
            value={readings.soil_moisture_20cm != null
              ? `${readings.soil_moisture_20cm.toFixed(0)}%`
              : "—"}
            sub={moistureLabel(readings.soil_moisture_20cm).text}
            color={resolveColor(moistureLabel(readings.soil_moisture_20cm).color, t)}
            t={t}
          />
          <StatCard
            icon={mdiThermometer}
            label="Temperature"
            value={readings.temperature_c != null
              ? `${readings.temperature_c.toFixed(1)}°C`
              : "—"}
            sub={readings.temperature_c < 15 ? "Cool"
               : readings.temperature_c > 35 ? "Hot"
               : "Normal"}
            color={readings.temperature_c > 35 ? t.orange
                 : readings.temperature_c < 15 ? t.amber
                 : t.green}
            t={t}
          />
          <StatCard
            icon={mdiLeaf}
            label="Nitrogen"
            value={readings.nitrogen_ppm != null
              ? `${readings.nitrogen_ppm.toFixed(0)} ppm`
              : "—"}
            sub={nitrogenLabel(readings.nitrogen_ppm).text}
            color={resolveColor(nitrogenLabel(readings.nitrogen_ppm).color, t)}
            t={t}
          />
          <StatCard
            icon={mdiFlask}
            label="Soil pH"
            value={readings.ph_level != null
              ? readings.ph_level.toFixed(1)
              : "—"}
            sub={phLabel(readings.ph_level).text}
            color={resolveColor(phLabel(readings.ph_level).color, t)}
            t={t}
          />
        </div>

        {/* ── Raw data toggle (progressive disclosure) ───────────────── */}
        <button
          onClick={() => setShowRaw(v => !v)}
          className="flex items-center gap-1.5 text-sm no-focus-ring transition-opacity hover:opacity-70"
          style={{ color: t.textMuted, fontWeight: 600 }}
        >
          <Icon path={showRaw ? mdiChevronUp : mdiChevronDown} size={0.62} />
          {showRaw ? "Hide sensor details" : "Show sensor details"}
        </button>

        {showRaw && (
          <div
            className="rounded-2xl p-4 grid grid-cols-2 gap-x-6 gap-y-2"
            style={{ background: t.panelLight, fontSize: "0.78rem" }}
          >
            {[
              ["Moisture 5cm",  readings.soil_moisture_5cm,  "%"],
              ["Moisture 20cm", readings.soil_moisture_20cm, "%"],
              ["Nitrogen",      readings.nitrogen_ppm,       "ppm"],
              ["Phosphorus",    readings.phosphorus_ppm,     "ppm"],
              ["Potassium",     readings.potassium_ppm,      "ppm"],
              ["pH",            readings.ph_level,           ""],
              ["Temperature",   readings.temperature_c,      "°C"],
              ["Organic Matter",readings.organic_matter_percent, "%"],
            ].map(([label, val, unit]) => val != null && (
              <div key={label} className="flex justify-between gap-2">
                <span style={{ color: t.textMuted }}>{label}</span>
                <span style={{ color: t.textPrimary, fontWeight: 600 }}>
                  {typeof val === "number" ? val.toFixed(1) : val}{unit}
                </span>
              </div>
            ))}
          </div>
        )}

        {/* ── No-crop: planting suggestions ──────────────────────────── */}
        {!hasCrop && cropSugg.length > 0 && (
          <div>
            <p className="text-xs font-bold uppercase tracking-widest mb-3" style={{ color: t.textMuted }}>
              Recommended Crops for This Zone
            </p>
            <div className="flex flex-col gap-2.5">
              {cropSugg.map(({ crop, icon, suitability, reason, season }) => (
                <div
                  key={crop}
                  className="rounded-2xl p-4 flex gap-3"
                  style={{
                    background: t.bgCard,
                    border:     `1.5px solid ${t.accentBorder}`,
                  }}
                >
                  <div
                    className="flex items-center justify-center rounded-xl flex-shrink-0"
                    style={{ width: "40px", height: "40px", background: t.accentMuted, fontSize: "1.2rem" }}
                  >
                    {icon}
                  </div>
                  <div className="flex flex-col gap-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-sm" style={{ color: t.textPrimary }}>{crop}</span>
                      <Pill
                        label={suitability}
                        color={suitability === "High" ? t.green : t.amber}
                        size="sm"
                      />
                    </div>
                    <p className="text-xs leading-snug" style={{ color: t.textSub }}>{reason}</p>
                    <div className="flex items-center gap-1 mt-0.5">
                      <Icon path={mdiCalendarMonth} size={0.5} color={t.textMuted} />
                      <span style={{ fontSize: "0.7rem", color: t.textMuted }}>{season}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── Recommendations ────────────────────────────────────────── */}
        <div>
          <p className="text-xs font-bold uppercase tracking-widest mb-3" style={{ color: t.textMuted }}>
            Recommendations
          </p>

          {loadRec && (
            <div className="py-4 flex items-center gap-2" style={{ color: t.textMuted, fontSize: "0.85rem" }}>
              <Spinner t={t} size={20} />
            </div>
          )}

          {!loadRec && recs.length === 0 && (
            <div
              className="rounded-2xl px-4 py-5 flex flex-col items-center gap-2 text-center"
              style={{ background: t.panelLight }}
            >
              <Icon path={mdiSeed} size={1.4} color={t.textMuted} />
              <p className="text-sm" style={{ color: t.textSub }}>No recommendations yet.</p>
              <button
                onClick={() => {
                  setLoadRec(true);
                  generateRecommendations(zoneId, farmId)
                    .then(d => {
                      const all = Array.isArray(d) ? d : (d.recommendations || d.top_actions || []);
                      setRecs(all);
                    })
                    .finally(() => setLoadRec(false));
                }}
                className="flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold no-focus-ring"
                style={{ background: t.accentMuted, color: t.accent }}
              >
                <Icon path={mdiReload} size={0.6} />
                Generate recommendations
              </button>
            </div>
          )}

          {/* ALL recommendations shown at once — farmer picks one */}
          {!loadRec && recs.length > 0 && (
            <div className="flex flex-col gap-3">
              {recs.map((rec, idx) => (
                <RecommendationCard
                  key={rec.id || idx}
                  rec={rec}
                  acting={acting[rec.id]}
                  onApply={(wasApplied) => handleApply(rec, wasApplied)}
                  t={t}
                />
              ))}
            </div>
          )}
        </div>

      </div>
    </div>
  );
}

// ─── Single recommendation card ───────────────────────────────────────────────

function RecommendationCard({ rec, acting, onApply, t }) {
  const level  = (rec.urgency || "LOW").toUpperCase();
  const colors = urgencyColors(level, t);
  const isDone = rec.status === "applied" || rec.status === "skipped";
  const conf   = rec.confidence != null ? Math.round(rec.confidence * 100) : null;
  const benefit= rec.net_benefit_usd != null
    ? `~KSh ${(rec.net_benefit_usd * 130).toFixed(0)}`
    : null;

  return (
    <div
      className="rounded-2xl overflow-hidden transition-opacity"
      style={{
        background: isDone ? t.panelLight : colors.muted,
        border:     `1.5px solid ${isDone ? t.border : colors.border + "44"}`,
        opacity:    isDone ? 0.55 : 1,
      }}
    >
      {/* Urgency stripe */}
      <div style={{ height: "3px", background: isDone ? t.border : colors.bg }} />

      <div className="p-4 flex flex-col gap-3">
        {/* Header */}
        <div className="flex items-start gap-2">
          <Pill label={level} color={isDone ? t.border : colors.bg} size="sm" />
          {conf != null && (
            <span
              className="ml-auto text-xs font-bold"
              style={{ color: isDone ? t.textMuted : colors.bg }}
            >
              {conf}% confidence
            </span>
          )}
        </div>

        {/* Action title */}
        <p className="text-sm font-semibold leading-snug" style={{ color: t.textPrimary }}>
          {rec.action_label || rec.action || rec.recommendation || "Review zone conditions"}
        </p>

        {/* Description if available */}
        {rec.reason && (
          <p className="text-xs leading-relaxed" style={{ color: t.textSub }}>
            {rec.reason}
          </p>
        )}

        {/* Meta row: benefit + risk */}
        {(benefit || rec.risk) && (
          <div className="flex items-center gap-4">
            {benefit && (
              <span className="text-xs font-semibold" style={{ color: t.accent }}>
                {benefit} est. benefit
              </span>
            )}
            {rec.risk && (
              <span className="text-xs font-medium" style={{ color: t.textMuted }}>
                Risk: {rec.risk}
              </span>
            )}
          </div>
        )}

        {/* Confidence bar */}
        {conf != null && !isDone && (
          <div className="flex items-center gap-2">
            <div
              className="flex-1 rounded-full overflow-hidden"
              style={{ height: "4px", background: t.border }}
            >
              <div
                style={{
                  width:        `${conf}%`,
                  height:       "100%",
                  background:   colors.bg,
                  borderRadius: "99px",
                  transition:   "width 0.4s ease",
                }}
              />
            </div>
          </div>
        )}

        {/* Action buttons */}
        {!isDone && (
          <div className="flex gap-2 mt-1">
            <button
              onClick={() => onApply(true)}
              disabled={!!acting}
              className="flex-1 flex items-center justify-center gap-2 rounded-xl py-2.5 font-semibold text-sm transition-opacity no-focus-ring"
              style={{
                background: colors.bg,
                color:      colors.text,
                opacity:    acting ? 0.6 : 1,
              }}
            >
              <Icon path={mdiCheckCircle} size={0.65} />
              {acting === "applying" ? "Saving…" : "I'll do this"}
            </button>

            <button
              onClick={() => onApply(false)}
              disabled={!!acting}
              className="flex items-center justify-center gap-1.5 rounded-xl px-4 py-2.5 font-semibold text-sm transition-opacity no-focus-ring"
              style={{
                background: t.bgCard,
                color:      t.textSub,
                border:     `1.5px solid ${t.border}`,
                opacity:    acting ? 0.6 : 1,
              }}
            >
              <Icon path={mdiCloseCircleOutline} size={0.62} />
              Skip
            </button>
          </div>
        )}

        {/* Done badge */}
        {isDone && (
          <div className="flex items-center gap-1.5">
            <Icon
              path={rec.status === "applied" ? mdiCheckCircle : mdiCloseCircleOutline}
              size={0.6}
              color={rec.status === "applied" ? t.green : t.textMuted}
            />
            <span className="text-xs font-semibold" style={{ color: t.textMuted }}>
              {rec.status === "applied" ? "Marked as done" : "Skipped"}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Helper ───────────────────────────────────────────────────────────────────

function resolveColor(colorKey, t) {
  switch (colorKey) {
    case "red":    return t.red;
    case "orange": return t.orange;
    case "amber":  return t.amber;
    case "green":  return t.green;
    default:       return t.textMuted;
  }
}
