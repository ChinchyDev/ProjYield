/**
 * health.js — Zone health scoring and plain-language labels
 */

// ─── Status derivation ────────────────────────────────────────────────────────

export function zoneStatus(readings = {}) {
  const { soil_moisture_20cm: m, nitrogen_ppm: n, ph_level: ph } = readings;

  const issues = [];

  if (m  != null) {
    if (m  < 20)  issues.push("CRITICAL");
    else if (m < 30) issues.push("HIGH");
    else if (m > 60) issues.push("MEDIUM");
  }
  if (n  != null) {
    if (n  < 40)  issues.push("CRITICAL");
    else if (n < 80) issues.push("HIGH");
  }
  if (ph != null) {
    if (ph < 5.0 || ph > 8.0)  issues.push("CRITICAL");
    else if (ph < 5.8 || ph > 7.5) issues.push("HIGH");
    else if (ph < 6.0 || ph > 7.2) issues.push("MEDIUM");
  }

  if (issues.includes("CRITICAL")) return "CRITICAL";
  if (issues.includes("HIGH"))     return "HIGH";
  if (issues.includes("MEDIUM"))   return "MEDIUM";
  return "GOOD";
}

export function statusColor(status, t) {
  switch ((status || "").toUpperCase()) {
    case "CRITICAL": return t.red;
    case "HIGH":     return t.orange;
    case "MEDIUM":   return t.amber;
    case "GOOD":     return t.green;
    default:         return t.textMuted;
  }
}

export function statusMuted(status, t) {
  switch ((status || "").toUpperCase()) {
    case "CRITICAL": return t.redMuted;
    case "HIGH":     return t.orangeMuted;
    case "MEDIUM":   return t.amberMuted;
    case "GOOD":     return t.greenMuted;
    default:         return t.panelLight;
  }
}

export function statusLabel(status) {
  switch ((status || "").toUpperCase()) {
    case "CRITICAL": return "Critical";
    case "HIGH":     return "Needs Attention";
    case "MEDIUM":   return "Watch";
    case "GOOD":     return "Healthy";
    default:         return "Unknown";
  }
}


// ─── Plain-language metric labels ────────────────────────────────────────────

export function moistureLabel(v) {
  if (v == null) return { text: "No data",            color: null };
  if (v < 20)    return { text: "Very dry — water now", color: "red" };
  if (v < 30)    return { text: "Dry — water soon",   color: "orange" };
  if (v <= 55)   return { text: "Good",                color: "green" };
  return           { text: "Waterlogged",              color: "amber" };
}

export function nitrogenLabel(v) {
  if (v == null) return { text: "No data",               color: null };
  if (v < 40)    return { text: "Low — fertilise now",   color: "red" };
  if (v < 80)    return { text: "Moderate",              color: "amber" };
  return           { text: "Good",                       color: "green" };
}

export function phLabel(v) {
  if (v == null)        return { text: "No data",                  color: null };
  if (v < 5.0)          return { text: "Very acidic — add lime",   color: "red" };
  if (v < 5.8)          return { text: "Slightly acidic",          color: "orange" };
  if (v >= 6.0 && v <= 7.0) return { text: "Ideal",               color: "green" };
  if (v > 7.5)          return { text: "Alkaline — adjust soil",   color: "amber" };
  return                  { text: "Acceptable",                    color: "green" };
}


// ─── Urgency sort order ───────────────────────────────────────────────────────

export const URGENCY_ORDER = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3, GOOD: 4 };

export function sortByUrgency(items, getLevel = (x) => x.urgency) {
  return [...items].sort(
    (a, b) => (URGENCY_ORDER[getLevel(a)] ?? 5) - (URGENCY_ORDER[getLevel(b)] ?? 5)
  );
}


// ─── Crop suggestions (no crop detected) ─────────────────────────────────────

export function suggestCrops(readings = {}) {
  const { ph_level: ph = 6.5, soil_moisture_20cm: m = 35, nitrogen_ppm: n = 70 } = readings;
  const suggestions = [];

  if (ph >= 5.8 && ph <= 7.2 && m >= 25)
    suggestions.push({
      crop: "Maize",
      icon: "🌽",
      suitability: ph >= 6.0 && ph <= 7.0 ? "High" : "Medium",
      reason: "Good pH and moisture for maize. Will grow well in this zone.",
      season: "Long rains (Mar–May)",
    });

  if (ph >= 6.0 && ph <= 7.5)
    suggestions.push({
      crop: "Beans",
      icon: "🫘",
      suitability: "High",
      reason: "Ideal soil acidity. Beans will also improve nitrogen naturally.",
      season: "Short rains (Oct–Dec)",
    });

  if (ph >= 5.5 && ph <= 7.5)
    suggestions.push({
      crop: "Sorghum",
      icon: "🌾",
      suitability: m < 30 ? "High" : "Medium",
      reason: m < 30
        ? "Drought-tolerant — perfect for your dry soil conditions."
        : "Hardy crop that works well with your soil profile.",
      season: "Long rains (Mar–May)",
    });

  if (n < 60)
    suggestions.push({
      crop: "Cassava",
      icon: "🥔",
      suitability: "Medium",
      reason: "Tolerates low nitrogen and needs minimal inputs.",
      season: "Any season",
    });

  if (ph < 6.5)
    suggestions.push({
      crop: "Sweet Potato",
      icon: "🍠",
      suitability: "Medium",
      reason: "Thrives in slightly acidic soils like yours.",
      season: "Short rains (Oct–Dec)",
    });

  return suggestions.slice(0, 3);
}
