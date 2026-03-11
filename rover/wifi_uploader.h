/**
 * wifi_uploader.h
 * YieldVision — WiFi Batch Upload (ESP8266/ESP32 AT module or built-in WiFi)
 *
 * OPTION A — Arduino Mega + ESP8266 WiFi module (AT commands via Serial3)
 * OPTION B — Arduino Mega + WiFiEsp library (uncomment sections below)
 *
 * This is the SYNC step in the offline-first flow:
 *   Rover collects → saves to SD → returns to base → WiFi available → upload
 *
 * How it works:
 *   1. Connect to WiFi (SSID/password hardcoded or from SD config)
 *   2. Open each unsynced CSV file from SD
 *   3. Parse CSV rows into JSON batch payload
 *   4. POST to /readings/upload on YieldVision server
 *   5. On HTTP 200, mark file as synced in SYNCED.log
 *
 * Library: WiFiEsp by bportaluri (install via Library Manager)
 *          — OR — use ESP32 and its native WiFi.h (much easier)
 *
 * Wiring (Mega + ESP8266):
 *   ESP8266 VCC  → 3.3V  (NOT 5V — use a 3.3V regulator)
 *   ESP8266 GND  → GND
 *   ESP8266 TX   → RX3 (pin 15) on Mega
 *   ESP8266 RX   → TX3 (pin 14) on Mega  (through 1kΩ+2kΩ voltage divider to 3.3V)
 *   ESP8266 RST  → pin WIFI_RST_PIN
 *   ESP8266 CH_PD / EN → 3.3V (always HIGH to enable chip)
 *
 * NOTE: If you switch to an ESP32 for the rover, delete this file and use
 *       WiFi.h directly. This file is for Mega + external ESP8266.
 */

#ifndef WIFI_UPLOADER_H
#define WIFI_UPLOADER_H

#include <Arduino.h>
#include <SD.h>
#include "sd_storage.h"

// ── Config — CHANGE THESE ─────────────────────────────────────────────────────
#define WIFI_SSID       "YourNetworkName"
#define WIFI_PASSWORD   "YourPassword"
#define SERVER_HOST     "192.168.1.100"   // IP of computer running main_server.py
#define SERVER_PORT     8000
#define ROVER_ID        "ROVER_01"

#define WIFI_SERIAL     Serial3           // Mega pins 14/15
#define WIFI_RST_PIN    6
#define WIFI_BAUD       115200

// ── Timeouts ─────────────────────────────────────────────────────────────────
#define WIFI_CONNECT_TIMEOUT_MS  15000
#define HTTP_RESPONSE_TIMEOUT_MS 10000
#define MAX_READINGS_PER_BATCH   20       // Rows per HTTP POST

// ── AT command helper ─────────────────────────────────────────────────────────

/**
 * Send an AT command and wait for expected response string.
 * Returns true if response contains expected substring within timeoutMs.
 */
static bool atCmd(const char* cmd, const char* expected, unsigned long timeoutMs = 5000) {
  WIFI_SERIAL.println(cmd);
  unsigned long start = millis();
  String resp = "";
  while (millis() - start < timeoutMs) {
    while (WIFI_SERIAL.available()) resp += (char)WIFI_SERIAL.read();
    if (resp.indexOf(expected) >= 0) return true;
    delay(10);
  }
  return false;
}

static bool atCmdStr(const String& cmd, const char* expected, unsigned long timeoutMs = 5000) {
  return atCmd(cmd.c_str(), expected, timeoutMs);
}

// ── Public API ────────────────────────────────────────────────────────────────

/**
 * Initialise ESP8266 and connect to WiFi.
 * Call once when rover enters WiFi zone.
 * Returns true if connected.
 */
bool wifi_begin() {
  Serial.println(F("[WiFi] Initialising ESP8266..."));
  WIFI_SERIAL.begin(WIFI_BAUD);

  // Hardware reset ESP8266
  pinMode(WIFI_RST_PIN, OUTPUT);
  digitalWrite(WIFI_RST_PIN, LOW);  delay(200);
  digitalWrite(WIFI_RST_PIN, HIGH); delay(1000);

  if (!atCmd("AT", "OK")) {
    Serial.println(F("[WiFi] ESP8266 not responding — check wiring"));
    return false;
  }
  atCmd("ATE0", "OK");              // Echo off
  atCmd("AT+CWMODE=1", "OK");       // Station mode

  // Connect to WiFi
  String connectCmd = String("AT+CWJAP=\"") + WIFI_SSID + "\",\"" + WIFI_PASSWORD + "\"";
  Serial.print(F("[WiFi] Connecting to "));
  Serial.println(WIFI_SSID);

  if (!atCmdStr(connectCmd, "WIFI CONNECTED", WIFI_CONNECT_TIMEOUT_MS)) {
    Serial.println(F("[WiFi] Connection failed"));
    return false;
  }

  Serial.println(F("[WiFi] Connected"));
  return true;
}

/** Disconnect WiFi to save power */
void wifi_disconnect() {
  atCmd("AT+CWQAP", "OK", 3000);
  Serial.println(F("[WiFi] Disconnected"));
}

/**
 * Build a JSON batch payload from up to MAX_READINGS_PER_BATCH CSV rows.
 * CSV format matches what sd_storage.h writes.
 * Returns number of readings included in payload.
 */
static int _buildJsonBatch(File& f, char* buf, size_t bufSize, uint16_t& seqStart) {
  int count = 0;
  size_t pos = 0;

  // Start JSON
  pos += snprintf(buf + pos, bufSize - pos,
    "{\"rover_id\":\"%s\",\"readings\":[", ROVER_ID);

  // Skip header row (already at position if file freshly opened)
  // Caller should have seeked past header

  while (f.available() && count < MAX_READINGS_PER_BATCH) {
    String line = f.readStringUntil('\n');
    line.trim();
    if (line.length() < 10) continue;

    // Parse CSV — order matches sd_storage.h header
    // timestamp,zone_id,zone_label,farm_id,nitrogen,phosphorus,potassium,
    // ph,moisture,soil_temp,ec,air_temp,air_hum,lat,lon,gps_acc,quality,seq

    char cols[18][40];
    uint8_t col = 0;
    int start = 0;
    for (int i = 0; i <= (int)line.length() && col < 18; i++) {
      if (line[i] == ',' || line[i] == '\0' || i == (int)line.length()) {
        line.substring(start, i).toCharArray(cols[col], 40);
        col++;
        start = i + 1;
      }
    }

    if (col < 17) continue;  // Malformed row

    if (count > 0) buf[pos++] = ',';

    pos += snprintf(buf + pos, bufSize - pos,
      "{"
      "\"zone_id\":\"%s\","
      "\"farm_id\":\"%s\","
      "\"collected_at\":\"%s\","
      "\"nitrogen_ppm\":%s,"
      "\"phosphorus_ppm\":%s,"
      "\"potassium_ppm\":%s,"
      "\"ph_level\":%s,"
      "\"soil_moisture_pct\":%s,"
      "\"soil_temperature_c\":%s,"
      "\"electrical_conductivity\":%s,"
      "\"air_temperature_c\":%s,"
      "\"air_humidity_pct\":%s,"
      "\"gps_lat\":%s,"
      "\"gps_lon\":%s,"
      "\"gps_accuracy_m\":%s,"
      "\"sequence_number\":%s,"
      "\"synced_from_sd\":true"
      "}",
      cols[1],   // zone_id
      cols[3],   // farm_id
      cols[0],   // timestamp
      strcmp(cols[4], "NA") == 0 ? "null" : cols[4],   // nitrogen
      strcmp(cols[5], "NA") == 0 ? "null" : cols[5],   // phosphorus
      strcmp(cols[6], "NA") == 0 ? "null" : cols[6],   // potassium
      strcmp(cols[7], "NA") == 0 ? "null" : cols[7],   // ph
      strcmp(cols[8], "NA") == 0 ? "null" : cols[8],   // moisture
      strcmp(cols[9], "NA") == 0 ? "null" : cols[9],   // soil_temp
      strcmp(cols[10],"NA") == 0 ? "null" : cols[10],  // ec
      strcmp(cols[11],"NA") == 0 ? "null" : cols[11],  // air_temp
      strcmp(cols[12],"NA") == 0 ? "null" : cols[12],  // air_hum
      strcmp(cols[13],"NA") == 0 ? "null" : cols[13],  // lat
      strcmp(cols[14],"NA") == 0 ? "null" : cols[14],  // lon
      strcmp(cols[15],"NA") == 0 ? "null" : cols[15],  // gps_acc
      cols[17]   // sequence
    );

    count++;
    if (pos > bufSize - 500) break;  // Safety margin
  }

  pos += snprintf(buf + pos, bufSize - pos, "]}");
  return count;
}

/**
 * POST a JSON string to the server's /readings/upload endpoint.
 * Returns true on HTTP 200.
 */
static bool _httpPost(const char* jsonBody, size_t bodyLen) {
  // Open TCP connection
  String cipStart = String("AT+CIPSTART=\"TCP\",\"") + SERVER_HOST + "\"," + SERVER_PORT;
  if (!atCmdStr(cipStart, "CONNECT", 5000)) {
    Serial.println(F("[WiFi] TCP connect failed"));
    return false;
  }

  // Build HTTP request
  String request = String("POST /readings/upload HTTP/1.1\r\n") +
    "Host: " + SERVER_HOST + ":" + SERVER_PORT + "\r\n" +
    "Content-Type: application/json\r\n" +
    "Content-Length: " + bodyLen + "\r\n" +
    "Connection: close\r\n\r\n" +
    String(jsonBody);

  // Tell ESP8266 how many bytes coming
  String sendCmd = String("AT+CIPSEND=") + request.length();
  if (!atCmdStr(sendCmd, ">", 3000)) {
    atCmd("AT+CIPCLOSE", "OK", 2000);
    return false;
  }

  WIFI_SERIAL.print(request);
  delay(500);

  // Wait for HTTP response
  String response = "";
  unsigned long start = millis();
  while (millis() - start < HTTP_RESPONSE_TIMEOUT_MS) {
    while (WIFI_SERIAL.available()) response += (char)WIFI_SERIAL.read();
    if (response.indexOf("HTTP/1.") >= 0 && response.indexOf("\r\n\r\n") >= 0) break;
    delay(50);
  }

  atCmd("AT+CIPCLOSE", "OK", 2000);

  bool success = response.indexOf("200") >= 0 || response.indexOf("\"inserted\"") >= 0;
  if (!success) {
    Serial.print(F("[WiFi] Server returned: "));
    Serial.println(response.substring(0, 100));
  }
  return success;
}

/**
 * Upload all unsynced SD files to the server.
 * Safe to call even if no new files exist.
 * Returns number of files successfully uploaded.
 */
uint8_t wifi_uploadAll() {
  char files[10][32];
  uint8_t count = sd_listUnsyncedFiles(files, 10);

  if (count == 0) {
    Serial.println(F("[WiFi] No new files to upload"));
    return 0;
  }

  Serial.print(F("[WiFi] Uploading ")); Serial.print(count); Serial.println(F(" file(s)..."));

  uint8_t uploaded = 0;

  for (uint8_t fi = 0; fi < count; fi++) {
    Serial.print(F("[WiFi] Processing: ")); Serial.println(files[fi]);

    File f = SD.open(files[fi], FILE_READ);
    if (!f) continue;

    // Skip header
    f.readStringUntil('\n');

    bool file_ok = true;
    uint16_t seqStart = 0;

    while (f.available()) {
      static char jsonBuf[4096];  // 4KB per batch
      int readings = _buildJsonBatch(f, jsonBuf, sizeof(jsonBuf), seqStart);

      if (readings == 0) break;

      Serial.print(F("  Sending ")); Serial.print(readings); Serial.println(F(" readings..."));

      if (!_httpPost(jsonBuf, strlen(jsonBuf))) {
        Serial.println(F("  Upload failed — will retry next sync"));
        file_ok = false;
        break;
      }

      Serial.println(F("  OK"));
      delay(500);  // Brief pause between batches
    }

    f.close();

    if (file_ok) {
      sd_markSynced(files[fi]);
      uploaded++;
      Serial.print(F("[WiFi] Synced: ")); Serial.println(files[fi]);
    }
  }

  Serial.print(F("[WiFi] Upload complete. ")); Serial.print(uploaded); Serial.println(F(" file(s) synced."));
  return uploaded;
}

/** Quick connectivity test — ping server with GET /health */
bool wifi_testServer() {
  String cipStart = String("AT+CIPSTART=\"TCP\",\"") + SERVER_HOST + "\"," + SERVER_PORT;
  if (!atCmdStr(cipStart, "CONNECT", 5000)) return false;

  String req = String("GET /health HTTP/1.1\r\nHost: ") + SERVER_HOST + "\r\nConnection: close\r\n\r\n";
  String sendCmd = String("AT+CIPSEND=") + req.length();
  if (!atCmdStr(sendCmd, ">", 3000)) { atCmd("AT+CIPCLOSE","OK",2000); return false; }

  WIFI_SERIAL.print(req);
  delay(500);

  String resp = "";
  unsigned long start = millis();
  while (millis() - start < 5000) {
    while (WIFI_SERIAL.available()) resp += (char)WIFI_SERIAL.read();
    if (resp.indexOf("200") >= 0) { atCmd("AT+CIPCLOSE","OK",2000); return true; }
    delay(50);
  }
  atCmd("AT+CIPCLOSE","OK",2000);
  return false;
}

#endif // WIFI_UPLOADER_H
