/**
 * SectionHeader — small all-caps section label with optional right action
 */
export default function SectionHeader({ title, action, t }) {
  return (
    <div className="flex items-center justify-between mb-3">
      <span
        style={{
          fontSize:      "0.7rem",
          fontWeight:    700,
          textTransform: "uppercase",
          letterSpacing: "0.08em",
          color:         t.textMuted,
        }}
      >
        {title}
      </span>
      {action && (
        <button
          onClick={action.onClick}
          className="no-focus-ring transition-opacity hover:opacity-70"
          style={{ fontSize: "0.75rem", fontWeight: 600, color: t.accent }}
        >
          {action.label}
        </button>
      )}
    </div>
  );
}
