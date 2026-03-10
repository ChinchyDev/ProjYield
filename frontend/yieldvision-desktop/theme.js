/**
 * theme.js — YieldVision design tokens
 *
 * Two modes sharing the same palette (Palette B):
 *   #1B2727  #3C5148  #6B8E4E  #B2C5B2  #D5DDDF
 *
 * 60-30-10 rule:
 *   60% → background surface
 *   30% → panels / cards / secondary surfaces
 *   10% → accent (olive #6B8E4E), actions, highlights
 */

export const LIGHT = {
  // Backgrounds (60%)
  bg:          "#D5DDDF",
  bgCard:      "rgba(255,255,255,0.65)",
  bgCardSolid: "#ffffff",
  bgInput:     "rgba(255,255,255,0.7)",

  // Panels / secondary (30%)
  panel:       "#3C5148",
  panelText:   "#ffffff",
  panelMuted:  "rgba(255,255,255,0.6)",

  // Accent / actions (10%)
  accent:      "#6B8E4E",
  accentText:  "#ffffff",
  accentMuted: "rgba(107,142,78,0.15)",

  // Text
  textPrimary: "#1B2727",
  textSub:     "rgba(60,81,72,0.65)",
  textMuted:   "rgba(60,81,72,0.4)",

  // Borders
  border:      "rgba(178,197,178,0.5)",
  borderStrong:"rgba(178,197,178,0.9)",

  // Semantic
  red:         "#dc2626",
  orange:      "#f97316",
  amber:       "#f59e0b",
  green:       "#6B8E4E",

  // Nav bar
  navBg:       "rgba(27,39,39,0.82)",
  navIcon:     "rgba(178,197,178,0.4)",
  navActive:   "#B2C5B2",
  navGlow:     "rgba(178,197,178,0.6)",
};

export const DARK = {
  // Backgrounds (60%)
  bg:          "#111B1B",
  bgCard:      "rgba(27,39,39,0.75)",
  bgCardSolid: "#1B2727",
  bgInput:     "rgba(27,39,39,0.8)",

  // Panels / secondary (30%)
  panel:       "#2a3d36",
  panelText:   "#B2C5B2",
  panelMuted:  "rgba(178,197,178,0.5)",

  // Accent / actions (10%)
  accent:      "#6B8E4E",
  accentText:  "#ffffff",
  accentMuted: "rgba(107,142,78,0.2)",

  // Text
  textPrimary: "#D5DDDF",
  textSub:     "rgba(178,197,178,0.7)",
  textMuted:   "rgba(178,197,178,0.4)",

  // Borders
  border:      "rgba(60,81,72,0.6)",
  borderStrong:"rgba(60,81,72,0.9)",

  // Semantic (same across modes — status colors shouldn't change)
  red:         "#ef4444",
  orange:      "#fb923c",
  amber:       "#fbbf24",
  green:       "#6B8E4E",

  // Nav bar
  navBg:       "rgba(17,27,27,0.9)",
  navIcon:     "rgba(178,197,178,0.35)",
  navActive:   "#B2C5B2",
  navGlow:     "rgba(178,197,178,0.55)",
};

/**
 * urgencyColors(level, t)
 * Returns bg, text, dot, border values for a given urgency level.
 * `t` is the current theme object (LIGHT or DARK).
 */
export function urgencyColors(level, t) {
  switch ((level || "").toUpperCase()) {
    case "CRITICAL":
      return { bg: t.red,    text: "#fff",          dot: t.red,    border: t.red };
    case "HIGH":
      return { bg: t.orange, text: "#fff",          dot: t.orange, border: t.orange };
    case "MEDIUM":
      return { bg: t.amber,  text: t.textPrimary,   dot: t.amber,  border: t.amber };
    default:
      return { bg: t.accent, text: "#fff",          dot: t.accent, border: t.accent };
  }
}
