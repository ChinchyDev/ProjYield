import { useState, useEffect, useCallback } from "react";
import Icon from "@mdi/react";
import {
  mdiAlertCircle,
  mdiAlertOutline,
  mdiInformationOutline,
  mdiCheckAll,
  mdiClockOutline,
} from "@mdi/js";
import { getPendingRecommendations } from "../api";
import { urgencyColors } from "../theme";
import Spinner from "../components/Spinner";

const LEVELS  = ["CRITICAL", "HIGH", "MEDIUM"];
const LEVEL_ICONS = {
  CRITICAL: mdiAlertCircle,
  HIGH:     mdiAlertOutline,
  MEDIUM:   mdiInformationOutline,
};

export default function AlertsScreen({ farmId, t }) {
  const [recs,    setRecs]    = useState([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    getPendingRecommendations(farmId)
      .then(r => {
        const all = Array.isArray(r) ? r : (r.recommendations || []);
        setRecs(all.filter(x => x.status === "pending"));
      })
      .catch(() => setRecs([]))
      .finally(() => setLoading(false));
  }, [farmId]);

  useEffect(() => { load(); }, [load]);

  const grouped = LEVELS.reduce((acc, lvl) => {
    acc[lvl] = recs.filter(r => (r.urgency || "").toUpperCase() === lvl);
    return acc;
  }, {});

  const total = recs.length;

  return (
    <div className="h-full flex flex-col" style={{ paddingBottom: "90px" }}>
      {/* ── Header ────────────────────────────────────────────────────────── */}
      <div
        className="flex-shrink-0 px-6 pt-6 pb-4"
        style={{ borderBottom: `1px solid ${t.border}` }}
      >
        <h1 className="text-xl font-bold" style={{ color: t.textPrimary }}>Alerts</h1>
        <p className="text-sm mt-0.5" style={{ color: t.textSub }}>
          {total > 0 ? `${total} active alert${total > 1 ? "s" : ""}` : "No active alerts"}
        </p>
      </div>

      {/* ── Body ──────────────────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto px-6 py-4 flex flex-col gap-6">
        {loading && <Spinner t={t} />}

        {!loading && total === 0 && (
          <div className="flex flex-col items-center gap-3 py-16 text-center">
            <Icon path={mdiCheckAll} size={2.5} color={t.green} />
            <p className="font-semibold text-base" style={{ color: t.textPrimary }}>
              All clear!
            </p>
            <p className="text-sm max-w-xs" style={{ color: t.textSub }}>
              No alerts right now. Your farm zones are within acceptable ranges.
            </p>
          </div>
        )}

        {!loading && LEVELS.map(lvl => {
          const alerts = grouped[lvl];
          if (!alerts.length) return null;

          const colors = urgencyColors(lvl, t);

          return (
            <section key={lvl}>
              {/* Section header */}
              <div className="flex items-center gap-2 mb-3">
                <div
                  className="flex items-center justify-center rounded-xl"
                  style={{
                    width: "28px", height: "28px",
                    background: colors.muted,
                  }}
                >
                  <Icon path={LEVEL_ICONS[lvl]} size={0.65} color={colors.bg} />
                </div>
                <span className="font-bold text-sm" style={{ color: colors.bg }}>
                  {lvl === "CRITICAL" ? "Act Today" : lvl === "HIGH" ? "This Week" : "Monitor"}
                </span>
                <span
                  className="rounded-full px-2 py-0.5 text-xs font-bold"
                  style={{ background: colors.muted, color: colors.bg }}
                >
                  {alerts.length}
                </span>
              </div>

              {/* Alert cards */}
              <div className="flex flex-col gap-2.5">
                {alerts.map(alert => (
                  <AlertCard key={alert.id} alert={alert} colors={colors} t={t} />
                ))}
              </div>
            </section>
          );
        })}
      </div>
    </div>
  );
}

function AlertCard({ alert, colors, t }) {
  const ts = alert.created_at
    ? new Date(alert.created_at).toLocaleString("en-KE", {
        day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
      })
    : null;

  return (
    <div
      className="rounded-2xl overflow-hidden"
      style={{
        background: colors.muted,
        border:     `1.5px solid ${colors.border}33`,
      }}
    >
      {/* Top stripe */}
      <div style={{ height: "3px", background: colors.bg }} />

      <div className="p-4 flex flex-col gap-2">
        {/* Zone label */}
        <div className="flex items-center gap-2">
          <span
            className="rounded-full px-2.5 py-0.5 text-xs font-bold"
            style={{ background: colors.bg + "22", color: colors.bg }}
          >
            Zone {alert.zone_id}
          </span>
          {ts && (
            <div className="flex items-center gap-1 ml-auto">
              <Icon path={mdiClockOutline} size={0.5} color={t.textMuted} />
              <span style={{ fontSize: "0.7rem", color: t.textMuted }}>{ts}</span>
            </div>
          )}
        </div>

        {/* Message */}
        <p className="text-sm font-medium leading-snug" style={{ color: t.textPrimary }}>
          {alert.action || alert.recommendation || "Zone needs attention."}
        </p>

        {/* Confidence */}
        {alert.confidence != null && (
          <ConfidenceBar value={alert.confidence} color={colors.bg} t={t} />
        )}
      </div>
    </div>
  );
}

function ConfidenceBar({ value, color, t }) {
  const pct = Math.round((value || 0) * 100);
  return (
    <div className="flex items-center gap-2 mt-1">
      <div
        className="flex-1 rounded-full overflow-hidden"
        style={{ height: "4px", background: t.border }}
      >
        <div
          style={{ width: `${pct}%`, height: "100%", background: color, borderRadius: "99px" }}
        />
      </div>
      <span style={{ fontSize: "0.68rem", color: t.textMuted, fontWeight: 700 }}>
        {pct}% conf.
      </span>
    </div>
  );
}
