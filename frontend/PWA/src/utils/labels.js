/* Plain-language translators — HCI: match system to real world */

export function moistureLabel(v) {
  if (v == null)   return { text: 'No sensor data',                    colour: 'var(--slate)' };
  if (v < 20)      return { text: '💧 Soil is DRY — needs water today', colour: 'var(--red)' };
  if (v < 30)      return { text: '💧 Soil is a bit dry',               colour: 'var(--orange)' };
  if (v <= 50)     return { text: '✅ Moisture is just right',           colour: 'var(--green-lt)' };
  return           { text: '🌊 Too much water in soil',                 colour: 'var(--slate)' };
}

export function nitrogenLabel(v) {
  if (v == null)   return { text: 'No sensor data',                        colour: 'var(--slate)' };
  if (v < 40)      return { text: '🌿 Nitrogen LOW — apply fertiliser',    colour: 'var(--red)' };
  if (v < 80)      return { text: '🌿 Nitrogen is moderate',               colour: 'var(--orange)' };
  return           { text: '✅ Nitrogen is good',                          colour: 'var(--green-lt)' };
}

export function phLabel(v) {
  if (v == null)        return { text: 'No sensor data',                 colour: 'var(--slate)' };
  if (v < 5.5)          return { text: '⚠️ Too acidic — add lime',       colour: 'var(--red)' };
  if (v > 7.8)          return { text: '⚠️ Too alkaline',                colour: 'var(--orange)' };
  if (v >= 6.0 && v <= 7.0) return { text: '✅ Soil acidity just right', colour: 'var(--green-lt)' };
  return                { text: '🔸 Acidity is acceptable',              colour: 'var(--amber)' };
}

export function zoneHealth(m, n, ph) {
  const scores = [];
  if (m  != null) scores.push(m  < 20 ? 0 : m  < 30 ? 1 : 2);
  if (n  != null) scores.push(n  < 40 ? 0 : n  < 80 ? 1 : 2);
  if (ph != null) scores.push((ph < 5.5 || ph > 7.8) ? 0 : (ph < 6.0 || ph > 7.0) ? 1 : 2);
  if (!scores.length) return ['unknown', '❓ No data'];
  const avg = scores.reduce((a, b) => a + b, 0) / scores.length;
  if (avg < 0.7)  return ['danger',  '❌ Needs action now'];
  if (avg < 1.5)  return ['average', '⚠️ Watch closely'];
  return ['good', '✅ Healthy'];
}

export function statusPillClass(status) {
  return `pill pill--${status || 'unknown'}`;
}

export function confWord(conf) {
  if (conf >= 0.75) return 'HIGH';
  if (conf >= 0.5)  return 'MEDIUM';
  return 'LOW';
}

export function confColour(conf) {
  if (conf >= 0.75) return 'var(--green-lt)';
  if (conf >= 0.5)  return 'var(--amber)';
  return 'var(--red)';
}
