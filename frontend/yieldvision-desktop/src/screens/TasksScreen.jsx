import { useState, useEffect, useCallback } from "react";
import Icon from "@mdi/react";
import {
  mdiCheckCircle,
  mdiCloseCircleOutline,
  mdiAlertCircle,
  mdiAlertOutline,
  mdiInformationOutline,
  mdiClipboardCheckOutline,
  mdiLeaf,
  mdiWater,
  mdiChartBar,
  mdiFlask,
  mdiThermometer,
  mdiPh,
} from "@mdi/js";
import { getPendingRecommendations, applyRecommendation, getFarmSummary } from "../api";
import { sortByUrgency } from "../utils/health";
import { urgencyColors } from "../theme";
import Spinner from "../components/Spinner";
import Pill from "../components/Pill";
import SectionHeader from "../components/SectionHeader";

const URGENCY_ICON = {
  CRITICAL: mdiAlertCircle,
  HIGH:     mdiAlertOutline,
  MEDIUM:   mdiInformationOutline,
  LOW:      mdiClipboardCheckOutline,
};

const TABS = ["Tasks", "Reports"];
const FILTERS = ["All", "Pending", "Done"];

export default function TasksScreen({ farmId, t, onRefreshAlerts }) {
  const [mainTab, setMainTab] = useState("Tasks");
  const [tasks,   setTasks]   = useState([]);
  const [zones,   setZones]   = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter,  setFilter]  = useState("All");
  const [acting,  setActing]  = useState({});

  const load = useCallback(() => {
    setLoading(true);
    Promise.allSettled([
      getPendingRecommendations(farmId),
      getFarmSummary(farmId),
    ]).then(([recRes, sumRes]) => {
      if (recRes.status === "fulfilled") {
        const r = recRes.value;
        const recs = Array.isArray(r) ? r : (r.recommendations || []);
        setTasks(sortByUrgency(recs, x => x.urgency));
      }
      if (sumRes.status === "fulfilled") {
        setZones(sumRes.value.zones || []);
      }
    }).finally(() => setLoading(false));
  }, [farmId]);

  useEffect(() => { load(); }, [load]);

  async function handleApply(rec, wasApplied) {
    const key = wasApplied ? "applying" : "skipping";
    setActing(prev => ({ ...prev, [rec.id]: key }));
    try {
      await applyRecommendation(rec.id, farmId, wasApplied);
      setTasks(prev => prev.map(tk =>
        tk.id === rec.id ? { ...tk, status: wasApplied ? "applied" : "skipped" } : tk
      ));
      if (onRefreshAlerts) onRefreshAlerts();
    } catch {
      // silent
    } finally {
      setActing(prev => { const n = { ...prev }; delete n[rec.id]; return n; });
    }
  }

  const visible = tasks.filter(tk => {
    if (filter === "Pending") return tk.status === "pending";
    if (filter === "Done")    return tk.status === "applied" || tk.status === "skipped";
    return true;
  });

  const pending = tasks.filter(tk => tk.status === "pending").length;
  const done    = tasks.filter(tk => tk.status === "applied" || tk.status === "skipped").length;

  return (
    <div className="h-full flex flex-col" style={{ paddingBottom: "90px" }}>
      {/* ── Top tab bar: Tasks / Reports ────────────────────────────────── */}
      <div
        className="flex-shrink-0 px-6 pt-5 pb-0"
        style={{ borderBottom: `1px solid ${t.border}` }}
      >
        <div className="flex items-end justify-between mb-3">
          <div>
            <h1 className="text-xl font-bold" style={{ color: t.textPrimary }}>
              {mainTab === "Tasks" ? "Today's Tasks" : "Farm Reports"}
            </h1>
            {mainTab === "Tasks" && (
              <p className="text-sm mt-0.5" style={{ color: t.textSub }}>
                {pending} pending · {done} done
              </p>
            )}
          </div>
        </div>

        <div className="flex gap-1">
          {TABS.map(tab => (
            <button
              key={tab}
              onClick={() => setMainTab(tab)}
              className="no-focus-ring px-4 py-2 text-sm font-semibold transition-all"
              style={{
                borderBottom: mainTab === tab ? `2px solid ${t.accent}` : "2px solid transparent",
                color: mainTab === tab ? t.accent : t.textSub,
                background: "transparent",
                border: "none",
                cursor: "pointer",
              }}
            >
              <Icon
                path={tab === "Tasks" ? mdiClipboardCheckOutline : mdiChartBar}
                size={0.55}
                style={{ display: "inline", marginRight: 5, verticalAlign: "middle" }}
                color={mainTab === tab ? t.accent : t.textSub}
              />
              {tab}
            </button>
          ))}

          {/* filter pills — only in Tasks tab */}
          {mainTab === "Tasks" && (
            <div className="flex gap-2 ml-4">
              {FILTERS.map(f => (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  className="rounded-full px-3 py-1 text-xs font-semibold transition-all no-focus-ring"
                  style={{
                    background: filter === f ? t.accent     : t.panelLight,
                    color:      filter === f ? t.accentText : t.textSub,
                    border: "none", cursor: "pointer",
                  }}
                >
                  {f}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ── Body ────────────────────────────────────────────────────────── */}
      {loading ? (
        <div className="flex-1 flex items-center justify-center"><Spinner t={t} /></div>
      ) : mainTab === "Tasks" ? (
        <TaskList
          visible={visible} filter={filter} acting={acting}
          handleApply={handleApply} t={t}
        />
      ) : (
        <ReportsPanel zones={zones} tasks={tasks} t={t} />
      )}
    </div>
  );
}

// ─── Tasks list ───────────────────────────────────────────────────────────────

function TaskList({ visible, filter, acting, handleApply, t }) {
  return (
    <div className="flex-1 overflow-y-auto px-6 py-4 flex flex-col gap-3">
      {visible.length === 0 && (
        <div className="flex flex-col items-center gap-3 py-16 text-center">
          <Icon path={mdiCheckCircle} size={2.2} color={t.green} />
          <p className="font-semibold" style={{ color: t.textPrimary }}>
            {filter === "Pending" ? "No pending tasks" : "No tasks here"}
          </p>
          <p className="text-sm" style={{ color: t.textSub }}>
            {filter === "Pending"
              ? "All caught up! Your farm is in good shape."
              : "Switch filter to see other tasks."}
          </p>
        </div>
      )}

      {visible.map(task => {
        const level    = (task.urgency || "LOW").toUpperCase();
        const colors   = urgencyColors(level, t);
        const isDone   = task.status === "applied" || task.status === "skipped";
        const isActing = !!acting[task.id];

        return (
          <div
            key={task.id}
            className="rounded-2xl overflow-hidden transition-opacity"
            style={{
              background: isDone ? t.panelLight : colors.muted,
              border:     `1.5px solid ${isDone ? t.border : colors.border + "55"}`,
              opacity:    isDone ? 0.6 : 1,
            }}
          >
            <div style={{ height: "3px", background: isDone ? t.border : colors.bg }} />
            <div className="p-4 flex flex-col gap-3">
              <div className="flex items-center gap-2">
                <Icon path={URGENCY_ICON[level] || mdiInformationOutline} size={0.7}
                  color={isDone ? t.textMuted : colors.bg} />
                <Pill label={level} color={isDone ? t.border : colors.bg} size="sm" />
                <span className="text-xs font-semibold ml-auto" style={{ color: t.textMuted }}>
                  Zone {task.zone_id}
                </span>
              </div>

              <p className="text-sm font-semibold leading-snug" style={{ color: t.textPrimary }}>
                {task.action_label || task.action || task.recommendation || "Review zone conditions"}
              </p>

              {task.reason && (
                <p className="text-xs leading-relaxed" style={{ color: t.textSub }}>{task.reason}</p>
              )}

              {task.confidence != null && (
                <div>
                  <div className="flex justify-between mb-1">
                    <span style={{ fontSize: "0.68rem", color: t.textMuted }}>Confidence</span>
                    <span style={{ fontSize: "0.68rem", color: t.textSub, fontWeight: 600 }}>
                      {(task.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                  <div style={{ height: 4, borderRadius: 99, background: t.border }}>
                    <div style={{
                      height: "100%", borderRadius: 99,
                      width: `${(task.confidence * 100).toFixed(0)}%`,
                      background: colors.bg,
                    }} />
                  </div>
                </div>
              )}

              {!isDone && (
                <div className="flex gap-2 mt-1">
                  <button
                    onClick={() => handleApply(task, true)}
                    disabled={isActing}
                    className="flex-1 flex items-center justify-center gap-2 rounded-xl py-2.5 font-semibold text-sm transition-opacity no-focus-ring"
                    style={{ background: colors.bg, color: colors.text, opacity: isActing ? 0.6 : 1,
                      border: "none", cursor: "pointer" }}
                  >
                    <Icon path={mdiCheckCircle} size={0.65} />
                    {acting[task.id] === "applying" ? "Saving…" : "Done"}
                  </button>
                  <button
                    onClick={() => handleApply(task, false)}
                    disabled={isActing}
                    className="flex items-center justify-center gap-1.5 rounded-xl px-4 py-2.5 font-semibold text-sm transition-opacity no-focus-ring"
                    style={{ background: t.bgCard, color: t.textSub, border: `1.5px solid ${t.border}`,
                      opacity: isActing ? 0.6 : 1, cursor: "pointer" }}
                  >
                    <Icon path={mdiCloseCircleOutline} size={0.62} />
                    Skip
                  </button>
                </div>
              )}

              {isDone && (
                <div className="flex items-center gap-1.5">
                  <Icon
                    path={task.status === "applied" ? mdiCheckCircle : mdiCloseCircleOutline}
                    size={0.6} color={task.status === "applied" ? t.green : t.textMuted}
                  />
                  <span className="text-xs font-semibold" style={{ color: t.textMuted }}>
                    {task.status === "applied" ? "Completed" : "Skipped"}
                  </span>
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ─── Reports panel ────────────────────────────────────────────────────────────

function ReportsPanel({ zones, tasks, t }) {
  const [metric, setMetric] = useState("moisture");

  const METRIC_OPTS = [
    { key: "moisture",   label: "Moisture",    icon: mdiWater,       unit: "%",   field: "soil_moisture_20cm", lo: 0,   hi: 100, okLo: 35,  okHi: 65  },
    { key: "nitrogen",   label: "Nitrogen",    icon: mdiLeaf,        unit: "ppm", field: "nitrogen_ppm",       lo: 0,   hi: 200, okLo: 60,  okHi: 140 },
    { key: "ph",         label: "pH",          icon: mdiPh,          unit: "",    field: "ph_level",           lo: 4,   hi: 9,   okLo: 6.0, okHi: 7.5 },
    { key: "temp",       label: "Temp",        icon: mdiThermometer, unit: "°C",  field: "temperature_c",      lo: 15,  hi: 40,  okLo: 20,  okHi: 30  },
    { key: "phosphorus", label: "Phosphorus",  icon: mdiFlask,       unit: "ppm", field: "phosphorus_ppm",     lo: 0,   hi: 80,  okLo: 20,  okHi: 60  },
  ];

  const sel = METRIC_OPTS.find(m => m.key === metric);
  const pending = tasks.filter(t => t.status === "pending").length;
  const done    = tasks.filter(t => t.status === "applied" || t.status === "skipped").length;

  return (
    <div className="flex-1 overflow-y-auto px-6 py-5" style={{ paddingBottom: 100 }}>

      {/* ── Summary stat row ── */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10, marginBottom: 24 }}>
        {[
          { label: "Total Zones",    val: zones.length,                                         col: t.accent },
          { label: "Pending Tasks",  val: pending,                                               col: t.amber  },
          { label: "Completed",      val: done,                                                  col: t.green  },
          { label: "Avg Moisture",   val: avg(zones, "soil_moisture_20cm").toFixed(0) + "%",     col: t.accent },
        ].map(s => (
          <div key={s.label} style={{ background: t.bgCard, border: `1px solid ${t.border}`, borderRadius: 14, padding: "12px 14px" }}>
            <span style={{ display: "block", fontSize: "1.5rem", fontWeight: 800, color: s.col, lineHeight: 1 }}>{s.val}</span>
            <span style={{ display: "block", fontSize: "0.7rem", color: t.textMuted, marginTop: 4 }}>{s.label}</span>
          </div>
        ))}
      </div>

      {/* ── Metric selector ── */}
      <SectionHeader title="Sensor Readings by Zone" t={t} />
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 10, marginBottom: 16 }}>
        {METRIC_OPTS.map(m => (
          <button
            key={m.key}
            onClick={() => setMetric(m.key)}
            className="no-focus-ring"
            style={{
              display: "flex", alignItems: "center", gap: 5,
              padding: "5px 12px", borderRadius: 99,
              background: metric === m.key ? t.accent : t.panelLight,
              color: metric === m.key ? t.accentText : t.textSub,
              fontSize: "0.75rem", fontWeight: 600,
              border: "none", cursor: "pointer",
            }}
          >
            <Icon path={m.icon} size={0.45} color={metric === m.key ? t.accentText : t.textSub} />
            {m.label}
          </button>
        ))}
      </div>

      {/* ── Bar chart ── */}
      {zones.length > 0 ? (
        <BarChart zones={zones} sel={sel} t={t} />
      ) : (
        <div style={{ textAlign: "center", padding: "40px 0", color: t.textMuted, fontSize: "0.85rem" }}>
          No zone data yet.
        </div>
      )}

      {/* ── All-zone comparison table ── */}
      <div style={{ marginTop: 28 }}>
        <SectionHeader title="All-Zone Sensor Summary" t={t} />
        <div style={{ marginTop: 12, borderRadius: 14, overflow: "hidden", border: `1px solid ${t.border}` }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.78rem" }}>
            <thead>
              <tr style={{ background: t.panelLight }}>
                {["Zone", "Crop", "Moisture", "Nitrogen", "pH", "Temp", "P", "K"].map(h => (
                  <th key={h} style={{ padding: "9px 12px", textAlign: "left", color: t.textMuted, fontWeight: 600, fontSize: "0.7rem" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {zones.map((z, i) => (
                <tr key={z.zone_id} style={{ background: i % 2 === 0 ? t.bgCard : t.panelLight, borderTop: `1px solid ${t.border}` }}>
                  <td style={{ padding: "9px 12px", fontWeight: 700, color: t.textPrimary }}>{z.zone_id}</td>
                  <td style={{ padding: "9px 12px", color: t.textSub }}>{z.crop_type || "—"}</td>
                  <TdVal val={z.soil_moisture_20cm} unit="%" lo={35} hi={65} t={t} />
                  <TdVal val={z.nitrogen_ppm}       unit=" ppm" lo={60} hi={140} t={t} />
                  <TdVal val={z.ph_level}           unit=""  lo={6.0} hi={7.5} t={t} />
                  <TdVal val={z.temperature_c}      unit="°" lo={20} hi={30} t={t} />
                  <TdVal val={z.phosphorus_ppm}     unit=" ppm" lo={20} hi={60} t={t} />
                  <TdVal val={z.potassium_ppm}      unit=" ppm" lo={100} hi={180} t={t} />
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── Task urgency breakdown ── */}
      <div style={{ marginTop: 28 }}>
        <SectionHeader title="Task Urgency Breakdown" t={t} />
        <UrgencyDonut tasks={tasks} t={t} />
      </div>
    </div>
  );
}

// ─── Bar chart ────────────────────────────────────────────────────────────────

function BarChart({ zones, sel, t }) {
  const W = 640, H = 180, PAD_L = 40, PAD_B = 28, PAD_T = 16;
  const innerW = W - PAD_L - 20;
  const innerH = H - PAD_B - PAD_T;
  const barW   = Math.min(50, (innerW / zones.length) * 0.55);
  const gap    = innerW / zones.length;

  const vals = zones.map(z => z[sel.field] ?? 0);
  const rangeHi = Math.max(sel.hi, ...vals);

  function toY(v) { return PAD_T + innerH - ((v - sel.lo) / (rangeHi - sel.lo)) * innerH; }
  function clamp(v) { return Math.max(sel.lo, Math.min(rangeHi, v)); }

  // Ref lines at okLo and okHi
  const yOkLo = toY(clamp(sel.okLo));
  const yOkHi = toY(clamp(sel.okHi));

  return (
    <div style={{ background: t.bgCard, border: `1px solid ${t.border}`, borderRadius: 14, padding: "16px 12px 8px", overflowX: "auto" }}>
      <p style={{ fontSize: "0.7rem", color: t.textMuted, marginBottom: 8 }}>
        {sel.label} ({sel.unit}) — shaded band = optimal range
      </p>
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", minWidth: 320, display: "block" }}>
        {/* Optimal band */}
        <rect
          x={PAD_L} y={yOkHi}
          width={innerW} height={yOkLo - yOkHi}
          fill={t.green} opacity="0.08"
        />
        <line x1={PAD_L} y1={yOkLo} x2={PAD_L + innerW} y2={yOkLo}
          stroke={t.green} strokeWidth="0.8" strokeDasharray="4 3" opacity="0.5" />
        <line x1={PAD_L} y1={yOkHi} x2={PAD_L + innerW} y2={yOkHi}
          stroke={t.green} strokeWidth="0.8" strokeDasharray="4 3" opacity="0.5" />

        {/* Y axis */}
        <line x1={PAD_L} y1={PAD_T} x2={PAD_L} y2={PAD_T + innerH}
          stroke={t.border} strokeWidth="1" />
        {[sel.lo, sel.okLo, sel.okHi, rangeHi].map(v => (
          <text key={v} x={PAD_L - 4} y={toY(clamp(v)) + 3}
            textAnchor="end" fontSize="7.5" fill={t.textMuted}>{v}</text>
        ))}

        {/* Bars */}
        {zones.map((z, i) => {
          const val  = z[sel.field] ?? 0;
          const x    = PAD_L + gap * i + gap * 0.225;
          const yTop = toY(clamp(val));
          const yBot = toY(sel.lo);
          const bh   = Math.max(2, yBot - yTop);
          const outOfRange = val < sel.okLo || val > sel.okHi;
          const color = outOfRange ? t.red : t.green;

          return (
            <g key={z.zone_id}>
              <rect x={x} y={yTop} width={barW} height={bh}
                fill={color} opacity="0.82" rx="3" />
              <text x={x + barW / 2} y={yTop - 3}
                textAnchor="middle" fontSize="7.5" fill={t.textSub} fontWeight="600">
                {typeof val === "number" ? val.toFixed(sel.key === "ph" ? 1 : 0) : "—"}
              </text>
              <text x={x + barW / 2} y={H - 6}
                textAnchor="middle" fontSize="8" fill={t.textMuted} fontWeight="700">
                {z.zone_id}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

// ─── Urgency donut ────────────────────────────────────────────────────────────

function UrgencyDonut({ tasks, t }) {
  const counts = { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0 };
  tasks.forEach(tk => { const k = (tk.urgency || "LOW").toUpperCase(); if (counts[k] != null) counts[k]++; });
  const total = Object.values(counts).reduce((a, b) => a + b, 0);
  if (total === 0) return <p style={{ color: t.textMuted, fontSize: "0.8rem", marginTop: 10 }}>No tasks recorded.</p>;

  const COLS = { CRITICAL: "#E53935", HIGH: "#FF6F00", MEDIUM: "#F9A825", LOW: t.green };
  const CX = 70, CY = 70, R = 50, R_IN = 32;
  let startAngle = -Math.PI / 2;

  const slices = Object.entries(counts).filter(([, v]) => v > 0).map(([key, val]) => {
    const sweep = (val / total) * Math.PI * 2;
    const end   = startAngle + sweep;
    const x1 = CX + R * Math.cos(startAngle), y1 = CY + R * Math.sin(startAngle);
    const x2 = CX + R * Math.cos(end),         y2 = CY + R * Math.sin(end);
    const ix1 = CX + R_IN * Math.cos(startAngle), iy1 = CY + R_IN * Math.sin(startAngle);
    const ix2 = CX + R_IN * Math.cos(end),         iy2 = CY + R_IN * Math.sin(end);
    const large = sweep > Math.PI ? 1 : 0;
    const midA  = startAngle + sweep / 2;
    const midX  = CX + (R + 12) * Math.cos(midA);
    const midY  = CY + (R + 12) * Math.sin(midA);
    const d = `M ${x1} ${y1} A ${R} ${R} 0 ${large} 1 ${x2} ${y2} L ${ix2} ${iy2} A ${R_IN} ${R_IN} 0 ${large} 0 ${ix1} ${iy1} Z`;
    startAngle = end;
    return { key, val, d, col: COLS[key], midX, midY };
  });

  return (
    <div style={{ display: "flex", gap: 24, alignItems: "center", marginTop: 12 }}>
      <svg viewBox="0 0 160 140" style={{ width: 160, flexShrink: 0 }}>
        {slices.map(s => (
          <g key={s.key}>
            <path d={s.d} fill={s.col} opacity="0.88" />
            {(s.val / total) > 0.08 && (
              <text x={s.midX} y={s.midY + 3} textAnchor="middle" fontSize="8"
                fill="#fff" fontWeight="700">{s.val}</text>
            )}
          </g>
        ))}
        <text x={CX} y={CY + 3} textAnchor="middle" fontSize="13"
          fontWeight="800" fill={t.textPrimary}>{total}</text>
        <text x={CX} y={CY + 14} textAnchor="middle" fontSize="7"
          fill={t.textMuted}>tasks</text>
      </svg>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {Object.entries(counts).map(([key, val]) => (
          <div key={key} style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div style={{ width: 10, height: 10, borderRadius: 3, background: COLS[key], flexShrink: 0 }} />
            <span style={{ fontSize: "0.75rem", color: t.textSub, fontWeight: 600, width: 70 }}>{key}</span>
            <div style={{ flex: 1, height: 6, background: t.border, borderRadius: 99 }}>
              <div style={{ height: "100%", borderRadius: 99, background: COLS[key],
                width: total ? `${(val / total * 100).toFixed(0)}%` : "0%" }} />
            </div>
            <span style={{ fontSize: "0.72rem", color: t.textMuted, width: 20, textAlign: "right" }}>{val}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Table cell with color coding ─────────────────────────────────────────────

function TdVal({ val, unit, lo, hi, t }) {
  if (val == null) return <td style={{ padding: "9px 12px", color: t.textMuted }}>—</td>;
  const ok  = val >= lo && val <= hi;
  const col = ok ? t.green : (val < lo * 0.7 || val > hi * 1.3) ? t.red : t.amber;
  return (
    <td style={{ padding: "9px 12px" }}>
      <span style={{ color: col, fontWeight: 600 }}>{typeof val === "number" ? val.toFixed(val < 10 ? 1 : 0) : val}{unit}</span>
    </td>
  );
}

function avg(arr, field) {
  const vals = arr.map(z => z[field]).filter(v => v != null);
  return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : 0;
}

