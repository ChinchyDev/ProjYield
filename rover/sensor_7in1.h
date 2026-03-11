/**
 * sensor_7in1.h
 * YieldVision — ComWinTop 7-in-1 Soil Sensor (RS485 / Modbus RTU)
 *
 * Sensor: NPKPHCTH-S (5-pin probe, RS485)
 * Manual: CWT CO., LIMITED 5PIN Probe Type Manual v1.0
 * Default comms: 4800 baud, 8N1, device address 0x01
 *
 * Register map (read function code 0x03):
 *   0x0000  Humidity       ÷10  → %RH
 *   0x0001  Temperature    ÷10  → °C  (negative = complement, see manual p.5)
 *   0x0002  Conductivity   ×1   → µS/cm
 *   0x0003  pH             ÷10  → pH
 *   0x0004  Nitrogen             → mg/kg (ppm)
 *   0x0005  Phosphorus           → mg/kg (ppm)
 *   0x0006  Potassium            → mg/kg (ppm)
 *   0x0007  Salinity       ×1   → mg/L
 *   0x0008  TDS            ×1   → mg/L
 *
 * Wiring (from manual):
 *   Brown  → Power +  (5–30V DC)
 *   Black  → GND
 *   Yellow → RS485 A+ (to MAX485 A pin)
 *   Blue   → RS485 B- (to MAX485 B pin)
 *
 * MAX485 to Arduino Mega:
 *   MAX485 DI  → TX1 (pin 18)
 *   MAX485 RO  → RX1 (pin 19)
 *   MAX485 DE  → pin RE_DE_PIN (defined below)
 *   MAX485 RE  → same pin as DE (tied together)
 */

#ifndef SENSOR_7IN1_H
#define SENSOR_7IN1_H

#include <Arduino.h>

// ── Pin config ────────────────────────────────────────────────────────────────
#define RE_DE_PIN   4         // MAX485 DE+RE tied together
#define SOIL_SERIAL Serial1   // Hardware serial on Mega pins 18/19
#define SOIL_BAUD   4800

// ── Timing (ms) ───────────────────────────────────────────────────────────────
#define SEND_DELAY     10     // Hold DE HIGH this long before first byte
#define RESPONSE_DELAY 100    // Wait after last byte sent for sensor to respond
#define RESPONSE_BYTES 7      // Every single-register read returns 7 bytes

// ── Modbus request frames — from Instructables reference code ─────────────────
// Format: [addr][fn][reg_hi][reg_lo][count_hi][count_lo][crc_lo][crc_hi]
static const byte CMD_HUMIDITY[]     = {0x01, 0x03, 0x00, 0x00, 0x00, 0x01, 0x84, 0x0A};
static const byte CMD_TEMPERATURE[]  = {0x01, 0x03, 0x00, 0x01, 0x00, 0x01, 0xD5, 0xCA};
static const byte CMD_CONDUCTIVITY[] = {0x01, 0x03, 0x00, 0x02, 0x00, 0x01, 0x25, 0xCA};
static const byte CMD_PH[]           = {0x01, 0x03, 0x00, 0x03, 0x00, 0x01, 0x74, 0x0A};
static const byte CMD_NITROGEN[]     = {0x01, 0x03, 0x00, 0x04, 0x00, 0x01, 0xC5, 0xCB};
static const byte CMD_PHOSPHORUS[]   = {0x01, 0x03, 0x00, 0x05, 0x00, 0x01, 0x94, 0x0B};
static const byte CMD_POTASSIUM[]    = {0x01, 0x03, 0x00, 0x06, 0x00, 0x01, 0x64, 0x0B};
static const byte CMD_SALINITY[]     = {0x01, 0x03, 0x00, 0x07, 0x00, 0x01, 0x35, 0xCB};
static const byte CMD_TDS[]          = {0x01, 0x03, 0x00, 0x08, 0x00, 0x01, 0x05, 0xC8};

// ── Data struct ───────────────────────────────────────────────────────────────
struct SoilReading7in1 {
  float humidity_pct;        // %RH
  float temperature_c;       // °C  (soil)
  float conductivity_us_cm;  // µS/cm (EC)
  float ph;
  float nitrogen_ppm;
  float phosphorus_ppm;
  float potassium_ppm;
  float salinity_mg_l;
  float tds_mg_l;
  bool  valid;               // false if any read failed
};

// ── Low-level send/receive ────────────────────────────────────────────────────

/**
 * Send a Modbus RTU command and read back response_bytes bytes.
 * Returns true if we got a full response.
 */
static bool sendModbus(const byte* cmd, uint8_t cmdLen,
                       byte* buf, uint8_t expectedBytes) {
  // Flush any leftovers
  while (SOIL_SERIAL.available()) SOIL_SERIAL.read();

  // Switch MAX485 to transmit
  digitalWrite(RE_DE_PIN, HIGH);
  delay(SEND_DELAY);

  for (uint8_t i = 0; i < cmdLen; i++) SOIL_SERIAL.write(cmd[i]);
  SOIL_SERIAL.flush();  // Wait until TX buffer is fully sent

  // Switch MAX485 to receive
  digitalWrite(RE_DE_PIN, LOW);
  delay(RESPONSE_DELAY);

  uint8_t count = 0;
  unsigned long deadline = millis() + 300;  // 300 ms timeout
  while (count < expectedBytes && millis() < deadline) {
    if (SOIL_SERIAL.available()) {
      buf[count++] = SOIL_SERIAL.read();
    }
  }

  return (count == expectedBytes);
}

/**
 * Read one 16-bit register value from a 7-byte Modbus response.
 * Byte layout: [addr][fn][byteCount][dataHi][dataLo][crcLo][crcHi]
 * Returns raw uint16 — caller applies scaling.
 */
static int16_t parseRegister(const byte* buf) {
  return (int16_t)((buf[3] << 8) | buf[4]);
}

// ── Public API ────────────────────────────────────────────────────────────────

void sensor7in1_begin() {
  pinMode(RE_DE_PIN, OUTPUT);
  digitalWrite(RE_DE_PIN, LOW);   // Start in receive mode
  SOIL_SERIAL.begin(SOIL_BAUD, SERIAL_8N1);
  delay(500);  // Let sensor settle after power-on
}

/**
 * Read all 9 parameters from sensor.
 * Reads each register individually (safest — avoids timeout on bulk reads).
 * Takes ~2 seconds total due to per-register delays.
 */
SoilReading7in1 sensor7in1_readAll() {
  SoilReading7in1 r;
  r.valid = true;
  byte buf[RESPONSE_BYTES];

  // --- Humidity ---
  if (sendModbus(CMD_HUMIDITY, sizeof(CMD_HUMIDITY), buf, RESPONSE_BYTES)) {
    r.humidity_pct = parseRegister(buf) / 10.0;
  } else {
    r.humidity_pct = -1; r.valid = false;
  }
  delay(200);

  // --- Temperature ---
  // Negative temps returned as two's complement per manual p.5
  if (sendModbus(CMD_TEMPERATURE, sizeof(CMD_TEMPERATURE), buf, RESPONSE_BYTES)) {
    int16_t raw = parseRegister(buf);
    r.temperature_c = raw / 10.0;  // int16_t handles negative automatically
  } else {
    r.temperature_c = -999; r.valid = false;
  }
  delay(200);

  // --- Conductivity (EC) ---
  if (sendModbus(CMD_CONDUCTIVITY, sizeof(CMD_CONDUCTIVITY), buf, RESPONSE_BYTES)) {
    r.conductivity_us_cm = (float)((uint16_t)parseRegister(buf));
  } else {
    r.conductivity_us_cm = -1; r.valid = false;
  }
  delay(200);

  // --- pH ---
  if (sendModbus(CMD_PH, sizeof(CMD_PH), buf, RESPONSE_BYTES)) {
    r.ph = parseRegister(buf) / 10.0;
  } else {
    r.ph = -1; r.valid = false;
  }
  delay(200);

  // --- Nitrogen ---
  if (sendModbus(CMD_NITROGEN, sizeof(CMD_NITROGEN), buf, RESPONSE_BYTES)) {
    r.nitrogen_ppm = (float)((uint16_t)parseRegister(buf));
  } else {
    r.nitrogen_ppm = -1; r.valid = false;
  }
  delay(200);

  // --- Phosphorus ---
  if (sendModbus(CMD_PHOSPHORUS, sizeof(CMD_PHOSPHORUS), buf, RESPONSE_BYTES)) {
    r.phosphorus_ppm = (float)((uint16_t)parseRegister(buf));
  } else {
    r.phosphorus_ppm = -1; r.valid = false;
  }
  delay(200);

  // --- Potassium ---
  if (sendModbus(CMD_POTASSIUM, sizeof(CMD_POTASSIUM), buf, RESPONSE_BYTES)) {
    r.potassium_ppm = (float)((uint16_t)parseRegister(buf));
  } else {
    r.potassium_ppm = -1; r.valid = false;
  }
  delay(200);

  // --- Salinity ---
  if (sendModbus(CMD_SALINITY, sizeof(CMD_SALINITY), buf, RESPONSE_BYTES)) {
    r.salinity_mg_l = (float)((uint16_t)parseRegister(buf));
  } else {
    r.salinity_mg_l = -1;
    // Salinity not critical — don't mark invalid
  }
  delay(200);

  // --- TDS ---
  if (sendModbus(CMD_TDS, sizeof(CMD_TDS), buf, RESPONSE_BYTES)) {
    r.tds_mg_l = (float)((uint16_t)parseRegister(buf));
  } else {
    r.tds_mg_l = -1;
    // TDS not critical — don't mark invalid
  }

  return r;
}

/** Print reading to Serial for debugging */
void sensor7in1_print(const SoilReading7in1& r) {
  Serial.println(F("--- 7-in-1 Soil Sensor ---"));
  Serial.print(F("  Humidity    : ")); Serial.print(r.humidity_pct, 1);    Serial.println(F(" %"));
  Serial.print(F("  Temperature : ")); Serial.print(r.temperature_c, 1);   Serial.println(F(" °C"));
  Serial.print(F("  EC          : ")); Serial.print(r.conductivity_us_cm); Serial.println(F(" µS/cm"));
  Serial.print(F("  pH          : ")); Serial.println(r.ph, 1);
  Serial.print(F("  Nitrogen    : ")); Serial.print(r.nitrogen_ppm);       Serial.println(F(" mg/kg"));
  Serial.print(F("  Phosphorus  : ")); Serial.print(r.phosphorus_ppm);     Serial.println(F(" mg/kg"));
  Serial.print(F("  Potassium   : ")); Serial.print(r.potassium_ppm);      Serial.println(F(" mg/kg"));
  Serial.print(F("  Salinity    : ")); Serial.print(r.salinity_mg_l);      Serial.println(F(" mg/L"));
  Serial.print(F("  TDS         : ")); Serial.print(r.tds_mg_l);           Serial.println(F(" mg/L"));
  Serial.print(F("  Valid       : ")); Serial.println(r.valid ? F("YES") : F("NO — check wiring"));
}

#endif // SENSOR_7IN1_H
