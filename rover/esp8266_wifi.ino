/*
 * esp8266_wifi.ino
 * YieldVision — ESP8266 WiFi Access Point + Command Bridge + Data Relay
 *
 * BASED ON YOUR ORIGINAL wifi_code.txt — all original motor control kept intact.
 * ADDED:
 *   - DATA: prefix detection → forwards JSON to laptop FastAPI
 *   - /status endpoint for React frontend connection check
 *   - /setcontext endpoint for React to push farm_id and zone_id to Mega
 *   - CORS headers on everything so React app can fetch without errors
 *
 * ─── WHAT THIS SKETCH DOES ──────────────────────────────────────────────────
 *
 *  1. Creates WiFi AP "YieldVision" (laptop connects to this)
 *  2. Receives HTTP GET /cmd?dir=X from React → forwards char to Mega via Serial
 *  3. Receives JSON lines from Mega Serial (prefixed "DATA:") → HTTP POSTs to
 *     laptop FastAPI at POST /readings/single
 *  4. React calls GET /status → ESP returns JSON with connection info
 *  5. React calls POST /setcontext → ESP sends farm_id and zone_id to Mega
 *
 * ─── WIRING ──────────────────────────────────────────────────────────────────
 *
 *  ESP8266 TX  → Mega RX2 (pin 17)
 *  ESP8266 RX  → Mega TX2 (pin 16)
 *  ESP8266 GND → Mega GND  ← REQUIRED, common ground
 *  ESP8266 VCC → 3.3V
 *  ESP8266 CH_PD/EN → 3.3V
 *
 * ─── NETWORK SETUP ───────────────────────────────────────────────────────────
 *
 *  ESP8266 AP:  SSID "YieldVision", IP 192.168.4.1
 *  Laptop:      connects to YieldVision AP, gets IP 192.168.4.2
 *  FastAPI:     runs on laptop at http://192.168.4.2:8000
 *  React app:   runs on laptop, talks to FastAPI at same address
 *
 *  If your laptop gets a different IP, change LAPTOP_IP below.
 *  Run `ipconfig` (Windows) or `ip addr` (Linux) while connected to
 *  YieldVision AP to confirm your laptop's IP.
 *
 * ─── LIBRARIES ───────────────────────────────────────────────────────────────
 *  ESP8266WiFi        — built into ESP8266 Arduino core
 *  ESP8266WebServer   — built into ESP8266 Arduino core
 *  ESP8266HTTPClient  — built into ESP8266 Arduino core
 */

#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include <ESP8266HTTPClient.h>
#include <WiFiClient.h>

// ============================================================================
// CONFIGURATION — change these if needed
// ============================================================================

const char* AP_SSID     = "YieldVision";
const char* AP_PASSWORD = "rover1234";

// Laptop's IP on the YieldVision network.
// Connect laptop to YieldVision AP, run ipconfig, look for the 192.168.4.x address.
// It's almost always 192.168.4.2 — only change if it isn't.
const char* LAPTOP_IP   = "192.168.4.2";
const int   API_PORT    = 8000;

// FastAPI endpoint to receive live readings
// Matches POST /readings/single in main_server.py
const char* API_READING_ENDPOINT = "/readings/single";

// ============================================================================
// GLOBALS
// ============================================================================

ESP8266WebServer server(80);
WiFiClient       wifiClient;

char  lastCmd        = ' ';
bool  lastSendOk     = false;
int   totalSent      = 0;
int   totalFailed    = 0;

// Line buffer for reading JSON from Mega Serial
String incomingLine  = "";
bool   lineReady     = false;

// ============================================================================
// SETUP
// ============================================================================

void setup() {
  // Talk to Mega on Serial
  // ESP8266 Serial = hardware UART = talks to Mega RX2/TX2
  Serial.begin(115200);

  // Create WiFi AP
  WiFi.softAP(AP_SSID, AP_PASSWORD);

  // Register HTTP routes
  server.on("/",           HTTP_GET,  handleRoot);
  server.on("/cmd",        HTTP_GET,  handleCommand);
  server.on("/status",     HTTP_GET,  handleStatus);
  server.on("/setcontext", HTTP_POST, handleSetContext);

  // OPTIONS preflight for React fetch
  server.on("/cmd",        HTTP_OPTIONS, handleOptions);
  server.on("/setcontext", HTTP_OPTIONS, handleOptions);

  server.onNotFound(handleNotFound);
  server.begin();
}

// ============================================================================
// LOOP
// ============================================================================

void loop() {
  server.handleClient();

  // Read lines from Mega Serial
  // Regular single-char motor commands come through without newline
  // DATA: lines from Mega come with \n terminator
  while (Serial.available()) {
    char c = Serial.read();

    if (c == '\n') {
      lineReady = true;
    } else {
      incomingLine += c;
    }

    if (lineReady) {
      processSerialLine(incomingLine);
      incomingLine = "";
      lineReady    = false;
    }
  }
}

// ============================================================================
// PROCESS A COMPLETE LINE FROM MEGA
// ============================================================================

/*
 * Lines from Mega are either:
 *   "DATA:{...json...}"  → forward to FastAPI
 *   (anything else)      → ignore (debug prints from Mega show up here)
 */
void processSerialLine(String& line) {
  line.trim();
  if (line.startsWith("DATA:")) {
    String json = line.substring(5);  // strip the "DATA:" prefix
    forwardToApi(json);
  }
  // Everything else (Serial.println debug output from Mega) is silently ignored
}

// ============================================================================
// FORWARD READING TO LAPTOP FASTAPI
// ============================================================================

void forwardToApi(const String& json) {
  if (WiFi.softAPgetStationNum() == 0) {
    // No laptop connected to the AP — can't send
    lastSendOk = false;
    totalFailed++;
    return;
  }

  HTTPClient http;
  String url = "http://";
  url += LAPTOP_IP;
  url += ":";
  url += API_PORT;
  url += API_READING_ENDPOINT;

  http.begin(wifiClient, url);
  http.addHeader("Content-Type", "application/json");

  int responseCode = http.POST(json);

  if (responseCode == 200 || responseCode == 201) {
    lastSendOk = true;
    totalSent++;
  } else {
    lastSendOk = false;
    totalFailed++;
    // Send ACK back to Mega so it can retry
    Serial.println("SEND_FAILED");
  }

  http.end();
}

// ============================================================================
// HTTP HANDLERS
// ============================================================================

void addCORS() {
  server.sendHeader("Access-Control-Allow-Origin",  "*");
  server.sendHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  server.sendHeader("Access-Control-Allow-Headers", "Content-Type");
}

void handleOptions() {
  addCORS();
  server.send(204, "text/plain", "");
}

// GET /cmd?dir=X  — motor command from React (same as your original)
void handleCommand() {
  addCORS();
  if (!server.hasArg("dir")) {
    server.send(400, "text/plain", "Bad Request");
    return;
  }
  String cmd = server.arg("dir");
  char   c   = cmd[0];
  lastCmd    = c;

  // Forward single char to Mega Serial — exactly as your original
  Serial.print(c);
  server.send(200, "text/plain", "OK");
}

/*
 * POST /setcontext  body: {"farm_id":"...","zone_id":"...","zone_label":"..."}
 *
 * React calls this after the user selects a farm and zone in the UI.
 * ESP8266 forwards the IDs to Mega so readings get the right farm/zone stamped.
 *
 * Mega side reads lines prefixed with 'F' (farm) and 'Z' (zone).
 */
void handleSetContext() {
  addCORS();

  String body = server.arg("plain");
  if (body.length() == 0) {
    server.send(400, "text/plain", "Empty body");
    return;
  }

  // Simple string extraction — no JSON library on ESP8266 needed
  // Extract farm_id
  String farmId = extractJsonValue(body, "farm_id");
  // Extract zone_id
  String zoneId = extractJsonValue(body, "zone_id");
  // Extract zone_label
  String zoneLabel = extractJsonValue(body, "zone_label");

  if (farmId.length() > 0) {
    Serial.print('F');
    Serial.print(farmId);
    Serial.print('\n');
  }

  if (zoneId.length() > 0) {
    Serial.print('Z');
    Serial.print(zoneId);
    Serial.print('|');
    Serial.print(zoneLabel);
    Serial.print('\n');
  }

  server.send(200, "application/json",
    "{\"status\":\"ok\",\"farm_id\":\"" + farmId +
    "\",\"zone_id\":\"" + zoneId + "\"}");
}

// GET /status  — React polls this to confirm ESP is alive and show stats
void handleStatus() {
  addCORS();
  String json = "{";
  json += "\"status\":\"ok\",";
  json += "\"ssid\":\"" + String(AP_SSID) + "\",";
  json += "\"ip\":\"" + WiFi.softAPIP().toString() + "\",";
  json += "\"clients_connected\":" + String(WiFi.softAPgetStationNum()) + ",";
  json += "\"last_cmd\":\"" + String(lastCmd) + "\",";
  json += "\"last_send_ok\":" + String(lastSendOk ? "true" : "false") + ",";
  json += "\"readings_sent\":" + String(totalSent) + ",";
  json += "\"readings_failed\":" + String(totalFailed) + ",";
  json += "\"laptop_target\":\"http://" + String(LAPTOP_IP) + ":" + String(API_PORT) + "\"";
  json += "}";
  server.send(200, "application/json", json);
}

// GET /  — original browser control page (backup, untouched from your original)
void handleRoot() {
  addCORS();
  String html = "<html><head><meta name='viewport' content='width=device-width'>";
  html += "<style>";
  html += "body{display:flex;justify-content:center;align-items:center;height:100vh;margin:0;background:#111;color:#fff;font-family:sans-serif;}";
  html += ".controls{text-align:center;}";
  html += "button{width:70px;height:70px;margin:5px;font-size:22px;border-radius:8px;border:none;background:#2d6a2d;color:#fff;cursor:pointer;}";
  html += "button:active{background:#1a4a1a;}";
  html += ".stop{background:#6a2d2d;}";
  html += "</style>";
  html += "<script>";
  html += "function sendCommand(cmd){fetch('/cmd?dir='+cmd);}";
  html += "document.addEventListener('keydown',function(e){";
  html += "const k=e.key.toLowerCase();";
  html += "if(['w','a','s','d','b','c',' '].includes(k)){e.preventDefault();sendCommand(k);}";
  html += "});";
  html += "</script></head><body>";
  html += "<div class='controls'>";
  html += "<p style='color:#888;font-size:13px'>YieldVision Rover — Backup Control</p>";
  html += "<div><button onclick=\"sendCommand('w')\">&#9650;</button></div>";
  html += "<div>";
  html += "<button onclick=\"sendCommand('a')\">&#9664;</button>";
  html += "<button class='stop' onclick=\"sendCommand(' ')\">&#9632;</button>";
  html += "<button onclick=\"sendCommand('d')\">&#9654;</button>";
  html += "</div>";
  html += "<div><button onclick=\"sendCommand('s')\">&#9660;</button></div>";
  html += "<div style='margin-top:10px'>";
  html += "<button onclick=\"sendCommand('b')\" style='width:100px'>Burnout</button>";
  html += "<button onclick=\"sendCommand('c')\" style='width:100px'>Circle</button>";
  html += "<button onclick=\"sendCommand('r')\" style='width:100px;background:#1a4a6a'>Scan</button>";
  html += "</div></div></body></html>";
  server.send(200, "text/html", html);
}

void handleNotFound() {
  addCORS();
  server.send(404, "text/plain", "Not found");
}

// ============================================================================
// UTILITY — extract a value from a JSON string without a library
// ============================================================================

/*
 * Pulls the string value for a given key out of a flat JSON object.
 * e.g. extractJsonValue("{\"farm_id\":\"abc123\"}", "farm_id") → "abc123"
 * Works for simple string values only — enough for our context payload.
 */
String extractJsonValue(const String& json, const String& key) {
  String searchFor = "\"" + key + "\":\"";
  int start = json.indexOf(searchFor);
  if (start < 0) return "";
  start += searchFor.length();
  int end = json.indexOf("\"", start);
  if (end < 0) return "";
  return json.substring(start, end);
}
