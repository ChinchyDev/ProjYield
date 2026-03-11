/**
 * sensor_gps.h
 * YieldVision — GY-NEO6MV2 GPS Module
 *
 * Module: GY-NEO6MV2 (u-blox NEO-6M core)
 * Library: TinyGPS++ by Mikal Hart (install via Library Manager)
 *
 * Wiring to Arduino Mega:
 *   GPS VCC  → 5V (GY-NEO6MV2 board has onboard 3.3V regulator)
 *   GPS GND  → GND
 *   GPS TX   → RX2 (pin 17) on Mega
 *   GPS RX   → TX2 (pin 16) on Mega  (only needed if you send config to GPS)
 *
 * Baud rate: 9600 (NEO-6M default)
 *
 * What this module does for YieldVision:
 *   1. Gets a GPS fix at rover boot
 *   2. Used by farm_profile.h to identify which zone the rover is in
 *      (point-in-polygon against zones stored on SD card)
 *   3. Stamps every sensor reading with GPS coordinates
 *   4. Logs accuracy estimate (HDOP-based)
 *
 * Notes:
 *   - First fix after cold start can take 30–90 seconds outdoors
 *   - Fix is retained across soft resets (warm start = faster)
 *   - HDOP < 2.0 = good accuracy. We only trust fix if HDOP < 5.
 */

#ifndef SENSOR_GPS_H
#define SENSOR_GPS_H

#include <Arduino.h>
#include <TinyGPS++.h>

#define GPS_SERIAL    Serial2   // Mega pins 16 (TX2) / 17 (RX2)
#define GPS_BAUD      9600
#define GPS_HDOP_MAX  5.0       // Discard fix if HDOP worse than this
#define GPS_FIX_TIMEOUT_MS 120000  // 2 min max wait for first fix

static TinyGPSPlus _gps;

// ── Data struct ───────────────────────────────────────────────────────────────
struct GpsReading {
  double  lat;
  double  lon;
  float   accuracy_m;   // Estimated from HDOP × ~3m baseline
  uint8_t satellites;
  float   hdop;
  bool    valid;        // true only if fix acquired and HDOP acceptable
};

// ── Public API ────────────────────────────────────────────────────────────────

void gps_begin() {
  GPS_SERIAL.begin(GPS_BAUD);
  Serial.println(F("[GPS] Initialised. Waiting for fix..."));
}

/**
 * Feed GPS serial data and check if we have a valid fix.
 * Call this frequently in a loop — does NOT block.
 */
void gps_feed() {
  while (GPS_SERIAL.available()) {
    _gps.encode(GPS_SERIAL.read());
  }
}

/**
 * Block until GPS fix acquired or timeout reached.
 * Shows dot progress on Serial.
 * Returns true if fix acquired within timeout.
 */
bool gps_waitForFix(unsigned long timeoutMs = GPS_FIX_TIMEOUT_MS) {
  Serial.print(F("[GPS] Acquiring fix "));
  unsigned long start = millis();

  while (millis() - start < timeoutMs) {
    gps_feed();

    if (_gps.location.isValid() && _gps.location.isUpdated()) {
      float hdop = _gps.hdop.isValid() ? _gps.hdop.value() / 100.0 : 99.0;
      if (hdop < GPS_HDOP_MAX) {
        Serial.println(F(" OK"));
        return true;
      }
    }

    if ((millis() - start) % 2000 < 50) Serial.print('.');
    delay(50);
  }

  Serial.println(F(" TIMEOUT"));
  return false;
}

/**
 * Read current GPS position.
 * Call gps_feed() regularly before calling this.
 */
GpsReading gps_read() {
  GpsReading r;
  r.valid = false;

  gps_feed();

  if (!_gps.location.isValid()) {
    r.lat = 0; r.lon = 0;
    r.accuracy_m = 999;
    r.satellites = 0;
    r.hdop = 99;
    return r;
  }

  float hdop = _gps.hdop.isValid() ? _gps.hdop.value() / 100.0 : 99.0;
  if (hdop > GPS_HDOP_MAX) {
    // Fix exists but quality is poor — return data but mark invalid
    r.lat = _gps.location.lat();
    r.lon = _gps.location.lng();
    r.hdop = hdop;
    r.satellites = _gps.satellites.isValid() ? _gps.satellites.value() : 0;
    r.accuracy_m = hdop * 3.0;  // rough estimate: HDOP × ~3m circular error
    r.valid = false;
    return r;
  }

  r.lat        = _gps.location.lat();
  r.lon        = _gps.location.lng();
  r.hdop       = hdop;
  r.satellites = _gps.satellites.isValid() ? _gps.satellites.value() : 0;
  r.accuracy_m = hdop * 3.0;
  r.valid      = true;
  return r;
}

void gps_print(const GpsReading& r) {
  Serial.println(F("--- GPS ---"));
  Serial.print(F("  Lat        : ")); Serial.println(r.lat, 6);
  Serial.print(F("  Lon        : ")); Serial.println(r.lon, 6);
  Serial.print(F("  Accuracy   : ")); Serial.print(r.accuracy_m, 1); Serial.println(F(" m"));
  Serial.print(F("  Satellites : ")); Serial.println(r.satellites);
  Serial.print(F("  HDOP       : ")); Serial.println(r.hdop, 2);
  Serial.print(F("  Valid      : ")); Serial.println(r.valid ? F("YES") : F("NO — poor fix"));
}

#endif // SENSOR_GPS_H
