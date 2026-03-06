/* YieldVision PWA — API client */

const BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const CACHE_KEY = 'yieldvision_cache';
const CACHE_TTL = 2 * 60 * 60 * 1000; // 2 hours

function readCache(key) {
  try {
    const raw = localStorage.getItem(`${CACHE_KEY}_${key}`);
    if (!raw) return null;
    const { data, ts } = JSON.parse(raw);
    if (Date.now() - ts > CACHE_TTL) return null;
    return data;
  } catch { return null; }
}

function writeCache(key, data) {
  try {
    localStorage.setItem(`${CACHE_KEY}_${key}`, JSON.stringify({ data, ts: Date.now() }));
  } catch {}
}

async function apiFetch(path, opts = {}) {
  const cacheKey = path.replace(/\//g, '_');
  try {
    const res = await fetch(`${BASE}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...opts,
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (!opts.method || opts.method === 'GET') writeCache(cacheKey, data);
    return { data, offline: false };
  } catch (err) {
    const cached = readCache(cacheKey);
    if (cached) return { data: cached, offline: true };
    throw err;
  }
}

export async function getZonesSummary() {
  return apiFetch('/api/precision/zones/summary');
}

export async function getZoneDecisions(zoneId) {
  return apiFetch(`/api/precision/zone/${zoneId}/decisions`);
}

export async function getSystemStatus() {
  return apiFetch('/api/precision/status');
}

export async function getAutoDecisions() {
  return apiFetch('/api/precision/auto-decisions');
}

export async function planIrrigation(zoneId, cropType, targetYield) {
  return apiFetch('/api/irrigation/plan-from-yield-goal', {
    method: 'POST',
    body: JSON.stringify({
      zone_id: zoneId,
      crop_type: cropType,
      target_yield_kg_per_zone: targetYield,
    }),
  });
}
