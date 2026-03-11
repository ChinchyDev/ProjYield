/**
 * sensor_test.ino
 * YieldVision — Sensor Diagnostic Test
 *
 * USE THIS FIRST before flashing rover_controller.ino.
 * Tests each sensor independently so you can verify hardware connections
 * one at a time before putting everything together.
 *
 * Serial monitor: 115200 baud
 *
 * How to use:
 *   1. Set TEST_SENSOR below to the sensor you want to test
 *   2. Upload this sketch
 *   3. Open Serial Monitor at 115200
 *   4. Watch output — should see real readings if wired correctly
 */

// ── Pick ONE to test ──────────────────────────────────────────────────────────
#define TEST_DHT22
// #define TEST_GPS
// #define TEST_SD
// #define TEST_7IN1
// #define TEST_WIFI

// ── Tests ─────────────────────────────────────────────────────────────────────

#ifdef TEST_DHT22
// ─────────────────────────────────────────────
// DHT22 Test
// Expected output every 3s:
//   Temperature: XX.X °C   Humidity: XX.X %
// If you see NaN or "Read failed":
//   - Check pin 22 wired to DATA pin of DHT22
//   - Check 10kΩ pull-up between DATA and 5V
//   - Check VCC and GND
// ─────────────────────────────────────────────
#include "sensor_dht22.h"

void setup() {
  Serial.begin(115200);
  Serial.println(F("=== DHT22 Test ==="));
  dht22_begin();
}

void loop() {
  AirReading r = dht22_read();
  dht22_print(r);
  delay(3000);
}
#endif // TEST_DHT22


#ifdef TEST_GPS
// ─────────────────────────────────────────────
// GPS Test
// Take outside or near a window.
// First fix may take 30–90 seconds.
// Expected output once fixed:
//   Lat: -0.123456  Lon: 36.789012  Satellites: 6  HDOP: 1.20
// If no fix after 2 min indoors — that's normal. GPS needs sky view.
// If no data at all:
//   - Check TX (GPS) → RX2 (Mega pin 17)
//   - Check VCC and GND
// ─────────────────────────────────────────────
#include "sensor_gps.h"

void setup() {
  Serial.begin(115200);
  Serial.println(F("=== GPS Test ==="));
  gps_begin();
  Serial.println(F("Waiting for fix... (go outside if no fix after 2 minutes)"));
}

void loop() {
  gps_feed();
  GpsReading r = gps_read();
  gps_print(r);
  delay(2000);
}
#endif // TEST_GPS


#ifdef TEST_SD
// ─────────────────────────────────────────────
// SD Card Test
// Expected output:
//   [SD] Card OK
//   [SD] Write test passed
//   [SD] Read test passed: Hello YieldVision
// If "Init failed":
//   - Check CS pin 53, SCK 52, MOSI 51, MISO 50
//   - Make sure card is FAT32 formatted
//   - Check your SD module has level conversion (should have small IC on board)
// ─────────────────────────────────────────────
#include "sd_storage.h"

void setup() {
  Serial.begin(115200);
  Serial.println(F("=== SD Card Test ==="));

  if (!sd_begin()) {
    Serial.println(F("FAIL: SD card init failed. Check wiring."));
    return;
  }

  // Write test
  File f = SD.open("/TEST.txt", FILE_WRITE);
  if (!f) { Serial.println(F("FAIL: Cannot open test file")); return; }
  f.println(F("Hello YieldVision"));
  f.close();
  Serial.println(F("[SD] Write test passed"));

  // Read test
  f = SD.open("/TEST.txt", FILE_READ);
  if (!f) { Serial.println(F("FAIL: Cannot read test file")); return; }
  String content = f.readStringUntil('\n');
  f.close();
  Serial.print(F("[SD] Read test passed: ")); Serial.println(content);

  // Check for farm profile
  if (SD.exists("/FARM_PROFILE.json")) {
    Serial.println(F("[SD] FARM_PROFILE.json found"));
    sd_loadFarmProfile();
  } else {
    Serial.println(F("[SD] FARM_PROFILE.json not found — run Python setup tool"));
  }

  Serial.println(F("[SD] Test complete."));
}

void loop() {}
#endif // TEST_SD


#ifdef TEST_7IN1
// ─────────────────────────────────────────────
// 7-in-1 Soil Sensor Test
// Reads all 9 parameters every 5 seconds.
// Expected output:
//   Humidity: XX.X %   Temperature: XX.X °C
//   EC: XXXX µS/cm    pH: X.X
//   N: XXX  P: XXX  K: XXX  (mg/kg)
// If all values are 0 or sensor not responding:
//   - Check MAX485 wiring
//   - Check DE/RE pin is 4
//   - Check sensor brown → 5-12V, black → GND
//   - Check yellow → MAX485 A, blue → MAX485 B
//   - Sensor takes ~1 second to warm up after power-on
// ─────────────────────────────────────────────
#include "sensor_7in1.h"

void setup() {
  Serial.begin(115200);
  Serial.println(F("=== 7-in-1 Soil Sensor Test ==="));
  sensor7in1_begin();
  Serial.println(F("Waiting 2s for sensor to warm up..."));
  delay(2000);
}

void loop() {
  Serial.println(F("\nReading..."));
  SoilReading7in1 r = sensor7in1_readAll();
  sensor7in1_print(r);

  if (!r.valid) {
    Serial.println(F("\nTROUBLESHOOT:"));
    Serial.println(F("  1. Is MAX485 DE/RE tied together and connected to pin 4?"));
    Serial.println(F("  2. Is sensor powered? (Brown=5V+, Black=GND)"));
    Serial.println(F("  3. Yellow → MAX485 A, Blue → MAX485 B?"));
    Serial.println(F("  4. Is Mega TX1(18) → MAX485 DI, RX1(19) → MAX485 RO?"));
  }

  delay(5000);
}
#endif // TEST_7IN1


#ifdef TEST_WIFI
// ─────────────────────────────────────────────
// WiFi (ESP8266) Test
// Tests AT communication with ESP8266 module,
// then connects to your WiFi, then pings the server.
// Expected output:
//   [WiFi] ESP8266 responding: OK
//   [WiFi] Connected to YourNetworkName
//   [WiFi] Server reachable: YES
// If ESP8266 not responding:
//   - Check RX3(15)→ESP TX, TX3(14)→ESP RX (via voltage divider!)
//   - Check ESP is powered from 3.3V (NOT 5V)
//   - Check EN/CH_PD pin is pulled HIGH to 3.3V
// ─────────────────────────────────────────────
#include "wifi_uploader.h"

void setup() {
  Serial.begin(115200);
  Serial.println(F("=== ESP8266 WiFi Test ==="));

  if (!wifi_begin()) {
    Serial.println(F("FAIL: WiFi init failed. See troubleshooting above."));
    return;
  }

  Serial.print(F("Testing server at "));
  Serial.print(SERVER_HOST); Serial.print(F(":")); Serial.println(SERVER_PORT);

  bool ok = wifi_testServer();
  Serial.print(F("[WiFi] Server reachable: "));
  Serial.println(ok ? F("YES") : F("NO — check SERVER_HOST in wifi_uploader.h"));

  wifi_disconnect();
  Serial.println(F("[WiFi] Test complete."));
}

void loop() {}
#endif // TEST_WIFI
