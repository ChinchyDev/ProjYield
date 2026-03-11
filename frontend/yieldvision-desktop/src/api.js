/**
 * api.js — YieldVision API client
 *
 * All backend communication lives here.
 * In Electron the base URL comes from the main process via IPC.
 * In browser/PWA it falls back to the env var or localhost:8000.
 */

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

// ────── Mock mode toggle ──────
// Set to true to explore the UI without a backend.
const useMock = true;

// ────── In‑memory mock data ──────
const MOCK_FARM_ID = "mock_farm_001";
const MOCK_ZONES = [
  {
    zone_id: "A1",
    gps_lat: -1.2921, gps_lon: 36.8219,
    // boundary_coords: array of [lat, lon] polygon vertices sent by rover
    boundary_coords: [
      [-1.2916, 36.8214], [-1.2916, 36.8224],
      [-1.2924, 36.8226], [-1.2926, 36.8215],
    ],
    soil_moisture_5cm: 28, soil_moisture_20cm: 22,
    nitrogen_ppm: 45, phosphorus_ppm: 22, potassium_ppm: 120,
    ph_level: 6.1, temperature_c: 24.5,
    organic_matter_percent: 3.2,
    crop_type: "Maize",
    area_ha: 1.2,
    yield_estimate: { current_kg_ha: 2800, potential_kg_ha: 4500, confidence: 0.78, limiting_factor: "Nitrogen deficiency" },
    last_updated: new Date().toISOString(),
  },
  {
    zone_id: "A2",
    gps_lat: -1.2925, gps_lon: 36.8223,
    boundary_coords: [
      [-1.2916, 36.8224], [-1.2916, 36.8232],
      [-1.2924, 36.8234], [-1.2924, 36.8226],
    ],
    soil_moisture_5cm: 55, soil_moisture_20cm: 48,
    nitrogen_ppm: 92, phosphorus_ppm: 35, potassium_ppm: 140,
    ph_level: 6.5, temperature_c: 25.1,
    organic_matter_percent: 3.9,
    crop_type: "Beans",
    area_ha: 0.9,
    yield_estimate: { current_kg_ha: 1650, potential_kg_ha: 1800, confidence: 0.91, limiting_factor: null },
    last_updated: new Date().toISOString(),
  },
  {
    zone_id: "B1",
    gps_lat: -1.2930, gps_lon: 36.8220,
    boundary_coords: [
      [-1.2926, 36.8215], [-1.2924, 36.8226],
      [-1.2932, 36.8228], [-1.2934, 36.8216],
    ],
    soil_moisture_5cm: 18, soil_moisture_20cm: 12,
    nitrogen_ppm: 28, phosphorus_ppm: 15, potassium_ppm: 95,
    ph_level: 5.6, temperature_c: 26.8,
    organic_matter_percent: 2.6,
    crop_type: null,
    area_ha: 1.4,
    yield_estimate: { current_kg_ha: 0, potential_kg_ha: 3200, confidence: 0.62, limiting_factor: "Severe moisture stress + unplanted" },
    last_updated: new Date().toISOString(),
  },
  {
    zone_id: "B2",
    gps_lat: -1.2934, gps_lon: 36.8224,
    boundary_coords: [
      [-1.2924, 36.8226], [-1.2924, 36.8234],
      [-1.2932, 36.8236], [-1.2932, 36.8228],
    ],
    soil_moisture_5cm: 62, soil_moisture_20cm: 58,
    nitrogen_ppm: 110, phosphorus_ppm: 38, potassium_ppm: 155,
    ph_level: 6.8, temperature_c: 23.9,
    organic_matter_percent: 4.1,
    crop_type: "Sorghum",
    area_ha: 1.1,
    yield_estimate: { current_kg_ha: 3100, potential_kg_ha: 3300, confidence: 0.89, limiting_factor: null },
    last_updated: new Date().toISOString(),
  },
  {
    zone_id: "C1",
    gps_lat: -1.2940, gps_lon: 36.8216,
    boundary_coords: [
      [-1.2934, 36.8216], [-1.2932, 36.8228],
      [-1.2942, 36.8230], [-1.2944, 36.8214],
    ],
    soil_moisture_5cm: 31, soil_moisture_20cm: 27,
    nitrogen_ppm: 58, phosphorus_ppm: 28, potassium_ppm: 130,
    ph_level: 6.3, temperature_c: 24.2,
    organic_matter_percent: 3.5,
    crop_type: "Cassava",
    area_ha: 1.8,
    yield_estimate: { current_kg_ha: 8200, potential_kg_ha: 12000, confidence: 0.74, limiting_factor: "Below-optimal moisture" },
    last_updated: new Date().toISOString(),
  },
];

const MOCK_RECOMMENDATIONS = [
  {
    id: "rec_001",
    zone_id: "B1",
    urgency: "CRITICAL",
    action_label: "Irrigate Zone B1 now — soil is critically dry",
    reason: "Moisture at 12% risks crop stress. Immediate watering recommended.",
    confidence: 0.94,
    net_benefit_usd: 85,
    yield_impact: { loss_kg_ha: 1200, recovery_kg_ha: 900, pct_recovery: 75 },
    risk: "Low — timely irrigation prevents yield loss.",
    status: "pending",
    created_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
  },
  {
    id: "rec_002",
    zone_id: "A1",
    urgency: "HIGH",
    action_label: "Apply nitrogen fertilizer to Zone A1",
    reason: "Nitrogen at 45 ppm is below optimal for Maize. Top‑dressing will boost growth.",
    confidence: 0.88,
    net_benefit_usd: 62,
    yield_impact: { loss_kg_ha: 420, recovery_kg_ha: 380, pct_recovery: 90 },
    risk: "Medium — over‑application can cause leaf burn.",
    status: "pending",
    created_at: new Date(Date.now() - 5 * 60 * 60 * 1000).toISOString(),
  },
  {
    id: "rec_003",
    zone_id: "C1",
    urgency: "MEDIUM",
    action_label: "Monitor Zone C1 pH",
    reason: "pH 6.3 is acceptable but trending down. Consider lime in the next season.",
    confidence: 0.71,
    net_benefit_usd: 18,
    yield_impact: { loss_kg_ha: 80, recovery_kg_ha: 60, pct_recovery: 75 },
    risk: "Low — monitoring only.",
    status: "pending",
    created_at: new Date(Date.now() - 8 * 60 * 60 * 1000).toISOString(),
  },
  {
    id: "rec_004",
    zone_id: "A2",
    urgency: "LOW",
    action_label: "Optional: add potassium to Zone A2",
    reason: "Potassium is adequate; a small boost could improve root strength.",
    confidence: 0.55,
    net_benefit_usd: 9,
    yield_impact: { loss_kg_ha: 40, recovery_kg_ha: 35, pct_recovery: 88 },
    risk: "Low — optional.",
    status: "pending",
    created_at: new Date(Date.now() - 12 * 60 * 60 * 1000).toISOString(),
  },
];

async function mockResponse(path) {
  // Simulate network latency
  await new Promise(r => setTimeout(r, 300 + Math.random() * 200));

  switch (path) {
    case "/farms/mock_farm_001/summary":
      return {
        farm_id: MOCK_FARM_ID,
        farm_name: "Kamau's Farm",
        owner_name: "John Kamau",
        location: "Nakuru, Kenya",
        zones: MOCK_ZONES,
      };
    case "/zones/A1/state?farm_id=mock_farm_001":
    case "/zones/A2/state?farm_id=mock_farm_001":
    case "/zones/B1/state?farm_id=mock_farm_001":
    case "/zones/B2/state?farm_id=mock_farm_001":
    case "/zones/C1/state?farm_id=mock_farm_001": {
      const zoneId = path.split("/")[2];
      const zone = MOCK_ZONES.find(z => z.zone_id === zoneId);
      if (!zone) throw new Error("Zone not found");
      return { ...zone, farm_id: MOCK_FARM_ID };
    }
    case "/zones/A1/recommend?farm_id=mock_farm_001":
    case "/zones/A2/recommend?farm_id=mock_farm_001":
    case "/zones/B1/recommend?farm_id=mock_farm_001":
    case "/zones/B2/recommend?farm_id=mock_farm_001":
    case "/zones/C1/recommend?farm_id=mock_farm_001": {
      const zoneId = path.split("/")[2];
      const recs = MOCK_RECOMMENDATIONS.filter(r => r.zone_id === zoneId);
      return { recommendations: recs };
    }
    case "/farms/mock_farm_001/recommendations":
      return { recommendations: MOCK_RECOMMENDATIONS };
    case "/rover/schedule/mock_farm_001":
      return {
        rover_id: "RVR-2024-001A",
        status: "idle",
        last_scan: new Date(Date.now() - 4 * 60 * 60 * 1000).toISOString(),
        next_scan: new Date(Date.now() + 12 * 60 * 60 * 1000).toISOString(),
      };
    case "/crops/varieties":
      return [
        { crop_name: "Maize", varieties: ["Hybrid 514", "DH04", "H614"] },
        { crop_name: "Beans", varieties: ["KAT B1", "KAT B9", "Wairimu"] },
        { crop_name: "Sorghum", varieties: ["Gadam", "Serena", "Sila"] },
        { crop_name: "Cassava", varieties: ["Mweru", "KME 08"] },
      ];
    case "/farms/register":
      // For mock, always return the same farm
      return {
        farm_id: MOCK_FARM_ID,
        farm_name: "Kamau's Farm",
        owner_name: "John Kamau",
        location: "Nakuru, Kenya",
        zones: MOCK_ZONES,
      };
    default:
      // Handle POST/PUT actions for apply/skip
      if (path.startsWith("/recommendations/") && path.endsWith("/apply")) {
        const recId = path.split("/")[2];
        const rec = MOCK_RECOMMENDATIONS.find(r => r.id === recId);
        if (rec) rec.status = "applied";
        return { success: true };
      }
      if (path.startsWith("/recommendations/") && path.endsWith("/skip")) {
        const recId = path.split("/")[2];
        const rec = MOCK_RECOMMENDATIONS.find(r => r.id === recId);
        if (rec) rec.status = "skipped";
        return { success: true };
      }
      throw new Error(`Mock not implemented for ${path}`);
  }
}

async function request(path, opts = {}) {
  if (useMock) return mockResponse(path);
  const url = `${await base()}${path}`;
  const res  = await fetch(url, {
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

export const getFarmZones      = (farmId) => request(`/farms/${farmId}/zones`);


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
      was_applied:      wasApplied,
      applied_at:       new Date().toISOString(),
      farmer_feedback:  feedback || null,
    }),
  });


// ─── Rover schedule (via FastAPI) ────────────────────────────────────────────

export const getRoverSchedule = (farmId) => request(`/rover/schedule/${farmId}`);

// ─── Rover direct control (talks to ESP8266 AP at 192.168.4.1) ──────────────
// The ESP8266 creates its own WiFi hotspot "YieldVision".
// Laptop connects to that hotspot, then fetches these URLs directly.
// CORS headers are already added by the ESP8266 firmware.
//
// Commands:  W=forward  S=backward  A=left  D=right
//            B=burnout  C=circle    R=scan  ' '=stop

export async function roverCommand(dir, ip = "192.168.4.1") {
  if (useMock) {
    return { ok: true, mock: true, command: dir };
  }
  try {
    const res = await fetch(`http://${ip}/cmd?dir=${encodeURIComponent(dir)}`, {
      signal: AbortSignal.timeout(2000),
    });
    return { ok: res.ok, command: dir };
  } catch (e) {
    return { ok: false, error: e.message, command: dir };
  }
}

export async function roverStatus(ip = "192.168.4.1") {
  if (useMock) {
    return {
      status: "ok", ssid: "YieldVision", ip: "192.168.4.1",
      last_cmd: "W", clients: 1, mock: true,
    };
  }
  const res = await fetch(`http://${ip}/status`, {
    signal: AbortSignal.timeout(2000),
  });
  if (!res.ok) throw new Error("ESP8266 status request failed");
  return res.json();
}


// ─── Crops ───────────────────────────────────────────────────────────────────

export const getCropVarieties = (cropName) =>
  request(cropName
    ? `/crops/varieties?crop_name=${encodeURIComponent(cropName)}`
    : "/crops/varieties"
  );
