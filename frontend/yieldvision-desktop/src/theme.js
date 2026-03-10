/**
 * theme.js — YieldVision design tokens
 *
 * Palette B (user-selected):
 *   #1B2727  Deep Teal
 *   #3C5148  Forest
 *   #6B8E4E  Olive
 *   #B2C5B2  Sage
 *   #D5DDDF  Mist
 *
 * 60-30-10 rule:
 *   60% → background / surface  (Mist light / Deep Teal dark)
 *   30% → panels, cards, nav    (Forest)
 *   10% → accent, CTA, healthy  (Olive)
 */

export const LIGHT = {
  // ── Backgrounds (60%) ────────────────────────────────────────
  bg:          "#D5DDDF",
  bgCard:      "rgba(255,255,255,0.72)",
  bgCardSolid: "#ffffff",
  bgInput:     "rgba(255,255,255,0.8)",
  bgHover:     "rgba(60,81,72,0.06)",

  // ── Panels / secondary (30%) ──────────────────────────────────
  panel:       "#3C5148",
  panelLight:  "rgba(60,81,72,0.08)",
  panelText:   "#ffffff",
  panelMuted:  "rgba(255,255,255,0.55)",

  // ── Accent / actions (10%) ────────────────────────────────────
  accent:      "#6B8E4E",
  accentDark:  "#4e6a38",
  accentText:  "#ffffff",
  accentMuted: "rgba(107,142,78,0.14)",
  accentBorder:"rgba(107,142,78,0.35)",

  // ── Typography ────────────────────────────────────────────────
  textPrimary: "#1B2727",
  textSub:     "rgba(27,39,39,0.62)",
  textMuted:   "rgba(27,39,39,0.38)",

  // ── Borders ───────────────────────────────────────────────────
  border:      "rgba(178,197,178,0.45)",
  borderStrong:"rgba(178,197,178,0.85)",

  // ── Semantic status colours ───────────────────────────────────
  red:         "#dc2626",
  redMuted:    "rgba(220,38,38,0.12)",
  orange:      "#ea580c",
  orangeMuted: "rgba(234,88,12,0.12)",
  amber:       "#d97706",
  amberMuted:  "rgba(217,119,6,0.12)",
  green:       "#6B8E4E",
  greenMuted:  "rgba(107,142,78,0.12)",

  // ── Floating bottom nav ───────────────────────────────────────
  navBg:       "rgba(27,39,39,0.88)",
  navBorder:   "rgba(178,197,178,0.10)",
  navIcon:     "rgba(178,197,178,0.38)",
  navActive:   "#B2C5B2",
  navGlow:     "rgba(178,197,178,0.65)",
};

export const DARK = {
  // ── Backgrounds (60%) ────────────────────────────────────────
  bg:          "#111B1B",
  bgCard:      "rgba(27,39,39,0.78)",
  bgCardSolid: "#1B2727",
  bgInput:     "rgba(27,39,39,0.85)",
  bgHover:     "rgba(178,197,178,0.05)",

  // ── Panels / secondary (30%) ──────────────────────────────────
  panel:       "#2a3d36",
  panelLight:  "rgba(60,81,72,0.22)",
  panelText:   "#B2C5B2",
  panelMuted:  "rgba(178,197,178,0.45)",

  // ── Accent / actions (10%) ────────────────────────────────────
  accent:      "#6B8E4E",
  accentDark:  "#4e6a38",
  accentText:  "#ffffff",
  accentMuted: "rgba(107,142,78,0.18)",
  accentBorder:"rgba(107,142,78,0.3)",

  // ── Typography ────────────────────────────────────────────────
  textPrimary: "#D5DDDF",
  textSub:     "rgba(213,221,223,0.62)",
  textMuted:   "rgba(213,221,223,0.35)",

  // ── Borders ───────────────────────────────────────────────────
  border:      "rgba(60,81,72,0.55)",
  borderStrong:"rgba(60,81,72,0.9)",

  // ── Semantic status colours (same across modes) ───────────────
  red:         "#ef4444",
  redMuted:    "rgba(239,68,68,0.15)",
  orange:      "#f97316",
  orangeMuted: "rgba(249,115,22,0.15)",
  amber:       "#f59e0b",
  amberMuted:  "rgba(245,158,11,0.15)",
  green:       "#6B8E4E",
  greenMuted:  "rgba(107,142,78,0.18)",

  // ── Floating bottom nav ───────────────────────────────────────
  navBg:       "rgba(17,27,27,0.92)",
  navBorder:   "rgba(178,197,178,0.08)",
  navIcon:     "rgba(178,197,178,0.32)",
  navActive:   "#B2C5B2",
  navGlow:     "rgba(178,197,178,0.58)",
};

/**
 * urgencyColors(level, t)
 * Returns { bg, text, muted, border } for a given urgency level.
 */
export function urgencyColors(level, t) {
  switch ((level || "").toUpperCase()) {
    case "CRITICAL":
      return { bg: t.red,    text: "#fff", muted: t.redMuted,    border: t.red    };
    case "HIGH":
      return { bg: t.orange, text: "#fff", muted: t.orangeMuted, border: t.orange };
    case "MEDIUM":
      return { bg: t.amber,  text: "#fff", muted: t.amberMuted,  border: t.amber  };
    default:
      return { bg: t.green,  text: "#fff", muted: t.greenMuted,  border: t.green  };
  }
}
