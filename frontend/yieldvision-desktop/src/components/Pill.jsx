/**
 * Pill — small rounded status / label badge
 * Props:
 *   label   string
 *   color   bg colour string
 *   textCol text colour string (defaults to white)
 *   size    "sm" | "md" (default "sm")
 *   dot     show a leading coloured dot (boolean)
 */
export default function Pill({
  label,
  color,
  textCol = "#fff",
  size = "sm",
  dot = false,
  style = {},
}) {
  const padY = size === "md" ? "5px" : "3px";
  const padX = size === "md" ? "12px" : "9px";
  const fs   = size === "md" ? "0.78rem" : "0.7rem";

  return (
    <span
      style={{
        display:      "inline-flex",
        alignItems:   "center",
        gap:          dot ? "5px" : undefined,
        padding:      `${padY} ${padX}`,
        borderRadius: "99px",
        background:   color,
        color:        textCol,
        fontSize:     fs,
        fontWeight:   700,
        letterSpacing:"0.02em",
        whiteSpace:   "nowrap",
        ...style,
      }}
    >
      {dot && (
        <span
          style={{
            width:        "6px",
            height:       "6px",
            borderRadius: "50%",
            background:   textCol,
            flexShrink:   0,
            opacity:      0.85,
          }}
        />
      )}
      {label}
    </span>
  );
}
