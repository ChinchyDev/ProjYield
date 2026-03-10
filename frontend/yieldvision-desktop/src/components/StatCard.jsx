import Icon from "@mdi/react";

/**
 * StatCard — metric tile used in Home and Zone detail
 * Props:
 *   icon      MDI path string
 *   label     string  (small label above value)
 *   value     string | number
 *   sub       string  (optional sub-text below value)
 *   color     accent colour string
 *   t         theme object
 */
export default function StatCard({ icon, label, value, sub, color, t }) {
  return (
    <div
      className="flex flex-col gap-2 rounded-2xl p-4 transition-colors"
      style={{
        background: t.bgCard,
        border:     `1px solid ${t.border}`,
        backdropFilter: "blur(12px)",
      }}
    >
      {/* Icon chip */}
      <div
        className="flex items-center justify-center rounded-xl"
        style={{
          width:      "36px",
          height:     "36px",
          background: color ? `${color}22` : t.panelLight,
        }}
      >
        <Icon path={icon} size={0.72} color={color || t.accent} />
      </div>

      {/* Label */}
      <span
        style={{
          fontSize:    "0.68rem",
          fontWeight:  600,
          textTransform: "uppercase",
          letterSpacing: "0.06em",
          color:       t.textMuted,
        }}
      >
        {label}
      </span>

      {/* Value */}
      <span
        style={{
          fontSize:   "1.35rem",
          fontWeight: 700,
          color:      color || t.textPrimary,
          lineHeight: 1,
        }}
      >
        {value ?? "—"}
      </span>

      {/* Sub text */}
      {sub && (
        <span style={{ fontSize: "0.75rem", color: t.textSub, marginTop: "2px" }}>
          {sub}
        </span>
      )}
    </div>
  );
}
