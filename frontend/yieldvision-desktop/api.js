/**
 * api.js — YieldVision API client
 *
 * All communication with the FastAPI backend lives here.
 * In Electron, the base URL comes from the main process via IPC.
 * In browser/PWA, it falls back to the env var or localhost:8000.
 *
 * Offline behaviour: functions throw on network errors —
 * callers are responsible for catching and showing offline state.
 */

// Resolve base URL: Electron IPC → env var → localhost fallback
async function resolveBase() {
  if (window.electronAPI?.getApiUrl) {
    return window.electronAPI.getApiUrl();
  }
  return process.env.REACT_APP_API_URL || "http://localhost:8000";
}

let _baseUrl = null;
async function base() {
  if (!_baseUrl) _baseUrl = await resolveBase();
  return _baseUrl;
}

async function request(path, opts = {}) {
  const url = `${await base()}${path}`;
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json();
}


// ─── Health ──────────────────────────────────────────────────────────────────

export const checkHealth = () => request("/health");


// ─── Farm management ─────────────────────────────────────────────────────────

export const getFarmSummary    = (farmId) => request(`/farms/${farmId}/summary`);

export const registerFarm      = (data)   => request("/farms/register", {
  method: "POST",
  body: JSON.stringify(data),
});

export const registerZone      = (data)   => request("/zones/register", {
  method: "POST",
  body: JSON.stringify(data),
});

export const detectFarmFromGps = (lat, lon) =>
  request(`/farms/detect?lat=${lat}&lon=${lon}`);


// ─── Zone data ───────────────────────────────────────────────────────────────

export const getZoneState = (zoneId, farmId) =>
  request(`/zones/${zoneId}/state?farm_id=${farmId}`);

export const generateRecommendations = (zoneId, farmId) =>
  request(`/zones/${zoneId}/recommend?farm_id=${farmId}`, { method: "POST" });


// ─── Recommendations ─────────────────────────────────────────────────────────

export const getPendingRecommendations = (farmId) =>
  request(`/farms/${farmId}/recommendations`);

export const applyRecommendation = (recId, farmId, wasApplied, feedback = "") =>
  request(`/recommendations/${recId}/apply?farm_id=${farmId}`, {
    method: "PATCH",
    body: JSON.stringify({
      was_applied: wasApplied,
      applied_at: new Date().toISOString(),
      farmer_feedback: feedback || null,
    }),
  });


// ─── Rover ───────────────────────────────────────────────────────────────────

export const getRoverSchedule = (farmId) => request(`/rover/schedule/${farmId}`);


// ─── Crops & market ──────────────────────────────────────────────────────────

export const getCropVarieties = (cropName) =>
  request(cropName ? `/crops/varieties?crop_name=${encodeURIComponent(cropName)}` : "/crops/varieties");

export const getMarketPrice = (cropName) =>
  request(`/market/prices/${encodeURIComponent(cropName)}`);
