/**
 * rover_controller.ino
 * YieldVision — Main Rover Controller
 * Hardware: Arduino Mega 2560
 *
 * ═══════════════════════════════════════════════════════════════════════════
 * HARDWARE CONNECTIONS SUMMARY
 * ═══════════════════════════════════════════════════════════════════════════
 *
 *  7-in-1 Soil Sensor (via MAX485):
 *    MAX485 DI   → TX1  (pin 18)
 *    MAX485 RO   → RX1  (pin 19)
 *    MAX485 DE   → pin 4  (tied to RE)
 *    MAX485 RE   → pin 4  (tied to DE)
 *    MAX485 A    → Sensor Yellow (RS485 A+)
 *    MAX485 B    → Sensor Blue   (RS485 B-)
 *    Sensor Brown → 5V–12V DC
 *    Sensor Black → GND
 *
 *  DHT22 Air Sensor:
 *    DATA  → pin 22  (+ 10kΩ pull-up to 5V)
 *    VCC   → 5V
 *    GND   → GND
 *
 *  GPS (GY-NEO6MV2):
 *    TX    → RX2  (pin 17)
 *    RX    → TX2  (pin 16)
 *    VCC   → 5V
 *    GND   → GND
 *
 *  SD Card Module:
 *    CS    → pin 53
 *    SCK   → pin 52
 *    MOSI  → pin 51
 *    MISO  → pin 50
 *    VCC   → 5V
 *    GND   → GND
 *
 *  ESP8266 WiFi (optional — only active at base):
 *    TX    → RX3  (pin 15)
 *    RX    → TX3  (pin 14)  via 1kΩ+2kΩ divider
 *    RST   → pin 6
 *    EN    → 3.3V
 *    VCC   → 3.3V  (NOT 5V — use separate LDO regulator)
 *    GND   → GND
 *
 *  Status LED:
 *    LED   → pin 13  (built-in) or external via 220Ω resistor
 *
 * ═══════════════════════════════════════════════════════════════════════════
 * ROVER BEHAVIOUR (offline-first)
 * ═══════════════════════════════════════════════════════════════════════════
 *
 *  BOOT:
 *    1. Init all hardware
 *    2. Load farm profile from SD card (FARM_PROFILE.json)
 *    3. Wait for GPS fix
 *    4. Detect which zone rover is in (point-in-polygon)
 *    5. Enter collection loop
 *
 *  COLLECTION LOOP (every READING_INTERVAL_MS):
 *    1. Read GPS position → update zone if moved
 *    2. Read DHT22 (air temp/humidity)
 *    3. Read soil sensor (7-in-1 or NPK-PH depending on #define below)
 *    4. Validate readings
 *    5. Log to SD card CSV
 *    6. Blink LED to confirm
 *
 *  WIFI SYNC (triggered manually or by switch):
 *    1. Connect to WiFi
 *    2. POST unsynced CSV files to server
 *    3. Mark synced files in SYNCED.log
 *    4. Disconnect WiFi
 *
 * ═══════════════════════════════════════════════════════════════════════════
 * SENSOR SELECT — uncomment the one you have
 * ═══════════════════════════════════════════════════════════════════════════
 */

// ── Choose your sensor ────────────────────────────────────────────────────────
#define SENSOR_7IN1          // 7-in-1: NPK+pH+Moisture+Temp+EC+Salinity+TDS
// #define SENSOR_NPKPH      // NPK+pH only (when that module arrives)

#include "sensor_dht22.h"
#include "sensor_gps.h"
#include "sd_storage.h"
#include "wifi_uploader.h"

#ifdef SENSOR_7IN1
  #include "sensor_7in1.h"
#endif
#ifdef SENSOR_NPKPH
  #include "sensor_npkph.h"   // Not generated yet — placeholder for future
#endif

// ── Pin config ────────────────────────────────────────────────────────────────
#define LED_PIN          13
#define WIFI_SYNC_PIN    7    // Pull LOW to trigger WiFi sync (connect a switch here)
#define SENSOR_POWER_PIN 8    // Optional: cut power to sensor between readings to save battery

// ── Timing ───────────────────────────────────────────────────────────────────
#define READING_INTERVAL_MS   300000UL  // 5 minutes between readings
#define GPS_UPDATE_INTERVAL_MS 30000UL  // Re-check zone every 30s (rover may have moved)
#define BOOT_BLINK_COUNT      3

// ── State ─────────────────────────────────────────────────────────────────────
const ZoneProfile* currentZone = nullptr;
uint16_t readingSequence = 0;
unsigned long lastReadingTime = 0;
unsigned long lastGpsUpdateTime = 0;
bool gpsFixed = false;
GpsReading lastGps;

// ── Utilities ─────────────────────────────────────────────────────────────────
void blinkLed(uint8_t times, uint16_t onMs = 150, uint16_t offMs = 150) {
  for (uint8_t i = 0; i < times; i++) {
    digitalWrite(LED_PIN, HIGH); delay(onMs);
    digitalWrite(LED_PIN, LOW);  delay(offMs);
  }
}

/**
 * Build a timestamp string "YYYY-MM-DDTHH:MM:SS"
 * If GPS has time data, use it. Otherwise use boot-relative time.
 * Full RTC module (e.g. DS3231) would be ideal — GPS time is good enough for now.
 */
void buildTimestamp(char* buf, size_t bufLen) {
  // GPS provides UTC time when fix is acquired
  // TinyGPS++ exposes _gps object internally — we access it via the gps module
  // For now: use millis()-based relative timestamp until RTC is added
  unsigned long upMs = millis();
  unsigned long s = upMs / 1000;
  unsigned long m = s / 60; s %= 60;
  unsigned long h = m / 60; m %= 60;

  // If you add a DS3231 RTC later, replace this with RTC.now() formatting
  snprintf(buf, bufLen, "2026-03-11T%02lu:%02lu:%02lu", h % 24, m, s);
}

void buildDateStr(char* buf, size_t bufLen) {
  snprintf(buf, bufLen, "20260311");  // TODO: replace with real date from RTC/GPS
}

// ── Data quality score ────────────────────────────────────────────────────────
/**
 * Simple quality score 0.0–1.0 based on what we know about this reading.
 * The Python validation layer will do a deeper check after upload.
 */
float computeQuality(bool soilValid, bool airValid, bool gpsValid) {
  float score = 0.0;
  if (soilValid) score += 0.6;
  if (airValid)  score += 0.3;
  if (gpsValid)  score += 0.1;
  return score;
}

// ── SETUP ─────────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  while (!Serial && millis() < 3000);  // Wait up to 3s for Serial on Mega

  Serial.println(F("\n========================================"));
  Serial.println(F("  YieldVision Rover v2.0 — Arduino Mega"));
  Serial.println(F("========================================"));

  pinMode(LED_PIN, OUTPUT);
  pinMode(WIFI_SYNC_PIN, INPUT_PULLUP);
  blinkLed(BOOT_BLINK_COUNT);

  // ── SD card (must come first — everything else depends on farm profile) ──
  Serial.println(F("\n[1/5] SD Card..."));
  if (!sd_begin()) {
    Serial.println(F("FATAL: SD card required. Insert card and reset."));
    while (true) { blinkLed(10, 50, 50); delay(1000); }
  }

  if (!sd_loadFarmProfile()) {
    Serial.println(F("WARN: No farm profile found. Run setup tool to create FARM_PROFILE.json"));
    Serial.println(F("      Continuing without zone detection..."));
  }

  // ── Soil sensor ──────────────────────────────────────────────────────────
  Serial.println(F("\n[2/5] Soil Sensor..."));
  #ifdef SENSOR_7IN1
    sensor7in1_begin();
    Serial.println(F("  7-in-1 sensor initialised (RS485)"));
  #endif
  #ifdef SENSOR_NPKPH
    // sensorNpkPh_begin();
    Serial.println(F("  NPK+pH sensor initialised (RS485)"));
  #endif

  // ── DHT22 ────────────────────────────────────────────────────────────────
  Serial.println(F("\n[3/5] DHT22 Air Sensor..."));
  dht22_begin();
  AirReading testAir = dht22_read();
  if (testAir.valid) {
    Serial.print(F("  OK — ")); Serial.print(testAir.temperature_c, 1);
    Serial.print(F("°C, ")); Serial.print(testAir.humidity_pct, 1); Serial.println(F("%"));
  } else {
    Serial.println(F("  WARN: DHT22 not responding. Check wiring."));
  }

  // ── GPS ──────────────────────────────────────────────────────────────────
  Serial.println(F("\n[4/5] GPS..."));
  gps_begin();
  Serial.println(F("  Waiting for GPS fix (up to 2 minutes outdoors)..."));
  gpsFixed = gps_waitForFix(120000);

  if (gpsFixed) {
    lastGps = gps_read();
    gps_print(lastGps);

    // Initial zone detection
    if (_farm.loaded && lastGps.valid) {
      currentZone = sd_detectZone(lastGps.lat, lastGps.lon);
    }
  } else {
    Serial.println(F("  GPS fix not acquired. Readings will have no coordinates."));
    Serial.println(F("  Continuing — zone must be set manually if GPS fails."));
  }

  // ── Ready ─────────────────────────────────────────────────────────────────
  Serial.println(F("\n[5/5] Ready."));
  if (currentZone) {
    Serial.print(F("  Active zone: ")); Serial.println(currentZone->zone_label);
    Serial.print(F("  Crop: "));       Serial.println(currentZone->crop_name);
    Serial.print(F("  Soil: "));       Serial.println(currentZone->soil_type);
  } else {
    Serial.println(F("  No zone matched. Readings saved with zone_id=unknown."));
  }

  Serial.println(F("  Pull WIFI_SYNC_PIN LOW to trigger upload."));
  Serial.println(F("  Collecting readings every 5 minutes.\n"));
  blinkLed(2, 300, 100);

  lastReadingTime   = millis() - READING_INTERVAL_MS;  // Take first reading immediately
  lastGpsUpdateTime = millis();
}

// ── LOOP ──────────────────────────────────────────────────────────────────────
void loop() {

  // ── WiFi sync trigger (switch pulled LOW) ─────────────────────────────────
  if (digitalRead(WIFI_SYNC_PIN) == LOW) {
    Serial.println(F("\n[SYNC] WiFi sync triggered..."));
    delay(200);  // debounce

    if (wifi_begin()) {
      if (wifi_testServer()) {
        wifi_uploadAll();
      } else {
        Serial.println(F("[SYNC] Server not reachable — check IP and that server is running"));
      }
      wifi_disconnect();
    }

    // Wait until button released
    while (digitalRead(WIFI_SYNC_PIN) == LOW) delay(100);
  }

  // ── Periodic GPS update ───────────────────────────────────────────────────
  if (millis() - lastGpsUpdateTime >= GPS_UPDATE_INTERVAL_MS) {
    gps_feed();
    GpsReading newGps = gps_read();

    if (newGps.valid) {
      lastGps = newGps;
      gpsFixed = true;

      // Re-check zone if rover moved (update every GPS cycle)
      if (_farm.loaded) {
        const ZoneProfile* detected = sd_detectZone(newGps.lat, newGps.lon);
        if (detected && (!currentZone || strcmp(detected->zone_id, currentZone->zone_id) != 0)) {
          currentZone = detected;
          Serial.print(F("[GPS] Zone updated: ")); Serial.println(currentZone->zone_label);
        }
      }
    }

    lastGpsUpdateTime = millis();
  }

  // ── Sensor reading cycle ──────────────────────────────────────────────────
  if (millis() - lastReadingTime >= READING_INTERVAL_MS) {
    lastReadingTime = millis();
    readingSequence++;

    Serial.print(F("\n[READ] Sequence #")); Serial.println(readingSequence);

    // -- Read soil sensor --
    float n_ppm = -1, p_ppm = -1, k_ppm = -1;
    float ph = -1, moisture = -1, soil_temp = -999, ec = -1;
    bool soilValid = false;

    #ifdef SENSOR_7IN1
      SoilReading7in1 soil = sensor7in1_readAll();
      soilValid     = soil.valid;
      n_ppm         = soil.nitrogen_ppm;
      p_ppm         = soil.phosphorus_ppm;
      k_ppm         = soil.potassium_ppm;
      ph            = soil.ph;
      moisture      = soil.humidity_pct;
      soil_temp     = soil.temperature_c;
      ec            = soil.conductivity_us_cm;
      sensor7in1_print(soil);
    #endif
    #ifdef SENSOR_NPKPH
      // SoilReadingNpkPh soil = sensorNpkPh_readAll();
      // soilValid = soil.valid;
      // n_ppm = soil.nitrogen_ppm; p_ppm = soil.phosphorus_ppm;
      // k_ppm = soil.potassium_ppm; ph = soil.ph;
    #endif

    // -- Read DHT22 --
    AirReading air = dht22_read();
    dht22_print(air);

    // -- Current GPS --
    gps_feed();
    GpsReading gps = gps_read();

    // -- Compute quality score --
    float quality = computeQuality(soilValid, air.valid, gps.valid);

    // -- Build zone and farm IDs --
    const char* zone_id    = currentZone ? currentZone->zone_id    : "UNKNOWN";
    const char* zone_label = currentZone ? currentZone->zone_label : "??";
    const char* farm_id    = sd_getFarmId();

    // -- Build timestamp --
    char timestamp[24];
    char datestr[12];
    buildTimestamp(timestamp, sizeof(timestamp));
    buildDateStr(datestr, sizeof(datestr));

    // -- Log to SD --
    bool logged = sd_logReading(
      timestamp, datestr,
      zone_id, zone_label,
      n_ppm, p_ppm, k_ppm,
      ph,
      moisture, soil_temp, ec,
      air.valid ? air.temperature_c : -999,
      air.valid ? air.humidity_pct  : -1,
      gps.valid ? gps.lat : 0,
      gps.valid ? gps.lon : 0,
      gps.valid ? gps.accuracy_m : 999,
      quality,
      readingSequence
    );

    if (logged) {
      Serial.print(F("[LOG] Saved to SD — zone ")); Serial.print(zone_label);
      Serial.print(F(", quality ")); Serial.println(quality, 2);
      blinkLed(1, 200, 0);
    } else {
      Serial.println(F("[LOG] SD write FAILED"));
      blinkLed(5, 50, 50);  // Rapid blink = error
    }
  }

  // Small delay to avoid hammering the loop
  delay(100);
}
