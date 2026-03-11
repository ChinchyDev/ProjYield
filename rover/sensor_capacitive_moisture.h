/**
 * sensor_capacitive_moisture.h
 * YieldVision — Capacitive Soil Moisture Sensor v2.0
 *
 * Use this when you have the NPK+PH RS485 sensor but NOT the 7-in-1.
 * The NPK+PH sensor has no moisture reading — this fills that gap.
 *
 * Sensor: Capacitive Soil Moisture Sensor v2.0 (analog output)
 * NOT the resistive type (resistive corrodes in weeks — don't use it).
 *
 * Wiring to Arduino Mega:
 *   VCC  → 3.3V or 5V
 *   GND  → GND
 *   AOUT → A0
 *
 * How it reads:
 *   Dry soil  → HIGH analog value (~720–880)
 *   Wet soil  → LOW  analog value (~280–380)
 *   Output is inverted — higher raw = drier.
 *
 * CALIBRATE BEFORE USE — every board is slightly different.
 * Run moisture_calibrate() once, note the values, paste them below.
 */

#ifndef SENSOR_CAPACITIVE_MOISTURE_H
#define SENSOR_CAPACITIVE_MOISTURE_H

#include <Arduino.h>

#define MOISTURE_PIN      A0

// ── SET THESE after running moisture_calibrate() ──────────────────────────
#define MOISTURE_RAW_DRY  720    // Raw reading in dry air
#define MOISTURE_RAW_WET  310    // Raw reading submerged in water

#define MOISTURE_SAMPLES        10
#define MOISTURE_SAMPLE_DELAY_MS 5

struct MoistureReading {
  int   raw;
  float moisture_pct;
  bool  valid;
  bool  needs_calibration;
};

void moisture_begin() {
  pinMode(MOISTURE_PIN, INPUT);
  delay(100);
}

MoistureReading moisture_read() {
  MoistureReading r;
  long total = 0;
  for (int i = 0; i < MOISTURE_SAMPLES; i++) {
    total += analogRead(MOISTURE_PIN);
    delay(MOISTURE_SAMPLE_DELAY_MS);
  }
  r.raw = total / MOISTURE_SAMPLES;

  float pct = map(r.raw, MOISTURE_RAW_DRY, MOISTURE_RAW_WET, 0, 100);
  r.moisture_pct = constrain(pct, 0.0, 100.0);
  r.needs_calibration = (r.raw > MOISTURE_RAW_DRY + 50 || r.raw < MOISTURE_RAW_WET - 50);
  r.valid = !r.needs_calibration;
  return r;
}

void moisture_print(const MoistureReading& r) {
  Serial.println(F("--- Capacitive Moisture v2 ---"));
  Serial.print(F("  Raw ADC  : ")); Serial.println(r.raw);
  Serial.print(F("  Moisture : ")); Serial.print(r.moisture_pct, 1); Serial.println(F(" %"));
  if (r.needs_calibration)
    Serial.println(F("  WARN: Run moisture_calibrate() to set accurate thresholds"));
}

/**
 * Calibration helper — run once with your specific sensor board.
 * Prints the two #define values you should paste back into this file.
 */
void moisture_calibrate() {
  Serial.println(F("\n=== MOISTURE CALIBRATION ==="));
  Serial.println(F("Hold sensor in DRY AIR. Press any key..."));
  while (!Serial.available()) delay(100);
  while (Serial.available()) Serial.read();

  long dry = 0;
  for (int i = 0; i < 20; i++) { dry += analogRead(MOISTURE_PIN); delay(50); }
  int dry_raw = dry / 20;
  Serial.print(F("Dry raw: ")); Serial.println(dry_raw);

  Serial.println(F("Push sensor into WATER. Press any key..."));
  while (!Serial.available()) delay(100);
  while (Serial.available()) Serial.read();

  long wet = 0;
  for (int i = 0; i < 20; i++) { wet += analogRead(MOISTURE_PIN); delay(50); }
  int wet_raw = wet / 20;
  Serial.print(F("Wet raw: ")); Serial.println(wet_raw);

  Serial.println(F("\nPaste these into sensor_capacitive_moisture.h:"));
  Serial.print(F("#define MOISTURE_RAW_DRY  ")); Serial.println(dry_raw);
  Serial.print(F("#define MOISTURE_RAW_WET  ")); Serial.println(wet_raw);
}

#endif // SENSOR_CAPACITIVE_MOISTURE_H
