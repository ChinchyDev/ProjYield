/**
 * sensor_dht22.h
 * YieldVision — DHT22 Air Temperature & Humidity
 *
 * Sensor: DHT22 (AM2302)
 * Library: DHT sensor library by Adafruit (install via Library Manager)
 * Also install: Adafruit Unified Sensor (dependency)
 *
 * Wiring to Arduino Mega:
 *   DHT22 pin 1 (VCC)  → 5V
 *   DHT22 pin 2 (DATA) → Digital pin 22  (+ 10kΩ pull-up to 5V)
 *   DHT22 pin 4 (GND)  → GND
 *
 * Used for:
 *   - Hargreaves-Samani ET₀ calculation (FAO56 Eq. 52)
 *   - Air humidity context for recommendations
 *   - Daily Tmax/Tmin tracking to improve ET₀ accuracy over time
 */

#ifndef SENSOR_DHT22_H
#define SENSOR_DHT22_H

#include <Arduino.h>
#include <DHT.h>

#define DHT_PIN  22
#define DHT_TYPE DHT22

// ── Internal state — tracks daily min/max for better ET₀ ─────────────────────
static DHT _dht(DHT_PIN, DHT_TYPE);

// Track min/max within current day for Hargreaves-Samani
static float _tMax = -999.0;
static float _tMin =  999.0;

// ── Data struct ───────────────────────────────────────────────────────────────
struct AirReading {
  float temperature_c;
  float humidity_pct;
  float tmax_c;      // Rolling daily max (updated each call)
  float tmin_c;      // Rolling daily min (updated each call)
  bool  valid;
};

// ── Public API ────────────────────────────────────────────────────────────────

void dht22_begin() {
  _dht.begin();
  delay(2000);  // DHT22 needs 2s after power-on before first read
}

/** Reset daily min/max — call this at midnight or start of a new reading day */
void dht22_resetDailyMinMax() {
  _tMax = -999.0;
  _tMin =  999.0;
}

/**
 * Read temperature and humidity.
 * Updates rolling daily Tmax/Tmin internally.
 * Returns valid=false if sensor fails to respond.
 */
AirReading dht22_read() {
  AirReading r;

  float h = _dht.readHumidity();
  float t = _dht.readTemperature();  // Celsius

  if (isnan(h) || isnan(t)) {
    r.valid = false;
    r.temperature_c = -999;
    r.humidity_pct  = -999;
    r.tmax_c = _tMax > -999 ? _tMax : -999;
    r.tmin_c = _tMin <  999 ? _tMin :  999;
    Serial.println(F("[DHT22] Read failed — check wiring and pull-up resistor"));
    return r;
  }

  // Sanity range checks
  if (t < -40 || t > 80 || h < 0 || h > 100) {
    r.valid = false;
    r.temperature_c = -999;
    r.humidity_pct  = -999;
    r.tmax_c = _tMax; r.tmin_c = _tMin;
    Serial.println(F("[DHT22] Value out of range — check probe placement"));
    return r;
  }

  // Update daily min/max
  if (t > _tMax) _tMax = t;
  if (t < _tMin) _tMin = t;

  r.temperature_c = t;
  r.humidity_pct  = h;
  r.tmax_c = _tMax;
  r.tmin_c = _tMin;
  r.valid  = true;
  return r;
}

void dht22_print(const AirReading& r) {
  Serial.println(F("--- DHT22 Air Sensor ---"));
  Serial.print(F("  Temperature : ")); Serial.print(r.temperature_c, 1); Serial.println(F(" °C"));
  Serial.print(F("  Humidity    : ")); Serial.print(r.humidity_pct, 1);  Serial.println(F(" %"));
  Serial.print(F("  Today Tmax  : ")); Serial.print(r.tmax_c, 1);        Serial.println(F(" °C"));
  Serial.print(F("  Today Tmin  : ")); Serial.print(r.tmin_c, 1);        Serial.println(F(" °C"));
  Serial.print(F("  Valid       : ")); Serial.println(r.valid ? F("YES") : F("NO"));
}

#endif // SENSOR_DHT22_H
