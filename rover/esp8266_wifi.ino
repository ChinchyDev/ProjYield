/*
 * esp8266_wifi.ino
 * YieldVision — ESP8266 WiFi Access Point + Command Bridge
 *
 * BASED ON YOUR ORIGINAL wifi_code.txt — structure kept identical.
 * Extended to work with the React/Electron desktop app (CORS headers added).
 *
 * What this sketch does:
 *   - ESP8266 creates its own WiFi hotspot (no router needed)
 *   - Laptop connects to "YieldVision" network
 *   - React/Electron app sends HTTP GET to /cmd?dir=X
 *   - ESP8266 forwards single character to Mega via Serial (TX→RX1 on Mega)
 *   - Also hosts the original browser control page at / (still works as backup)
 *
 * Hardware:
 *   ESP8266 TX  →  Mega RX1 (pin 19)
 *   ESP8266 RX  →  Mega TX1 (pin 18)  [only if Mega needs to reply — optional]
 *   ESP8266 GND →  Mega GND  (common ground — REQUIRED)
 *   ESP8266 VCC →  3.3V
 *
 * Command characters (same as your original):
 *   W = forward      S = backward
 *   A = turn left    D = turn right
 *   B = burnout spin C = circle
 *   Space = stop
 *
 * New endpoint for Electron app:
 *   GET /status  →  returns JSON {"status":"ok","ip":"192.168.4.1"}
 *   Used by the GUI to confirm connection before sending commands.
 *
 * CORS headers are added to ALL responses so Electron's renderer process
 * can fetch without being blocked by browser security policy.
 */

#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>

// ── WiFi AP config ─────────────────────────────────────────────────────────
const char* ssid     = "YieldVision";   // Electron app connects to this network
const char* password = "rover1234";     // Change to something you'll remember

ESP8266WebServer server(80);

// ── Track last command for /status ─────────────────────────────────────────
char lastCmd = ' ';

// ── CORS helper — call at start of every handler ───────────────────────────
// Electron makes requests from a file:// origin. Without these headers,
// the fetch() call in React will be blocked.
void addCORSHeaders() {
  server.sendHeader("Access-Control-Allow-Origin",  "*");
  server.sendHeader("Access-Control-Allow-Methods", "GET, OPTIONS");
  server.sendHeader("Access-Control-Allow-Headers", "Content-Type");
}

// ── Setup ──────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);   // → Mega RX1 (pin 19). This IS the command channel.

  WiFi.softAP(ssid, password);
  IPAddress myIP = WiFi.softAPIP();

  // Print IP for reference (Mega can read this on boot if needed)
  Serial.flush();  // Don't accidentally send boot message as a command
  // NOTE: We don't Serial.println the IP here because the Mega reads
  // everything on Serial as a command character. IP is always 192.168.4.1.

  // Routes
  server.on("/",       HTTP_GET,     handleRoot);
  server.on("/cmd",    HTTP_GET,     handleCommand);
  server.on("/status", HTTP_GET,     handleStatus);
  server.on("/cmd",    HTTP_OPTIONS, handleOptions);  // Preflight for Electron
  server.onNotFound(handleNotFound);

  server.begin();
}

// ── Loop ───────────────────────────────────────────────────────────────────
void loop() {
  server.handleClient();
}

// ── Handlers ───────────────────────────────────────────────────────────────

// OPTIONS preflight — Electron sends this before some GET requests
void handleOptions() {
  addCORSHeaders();
  server.send(204, "text/plain", "");
}

// /cmd?dir=X — forward command character to Mega
// Same logic as your original, plus CORS headers
void handleCommand() {
  addCORSHeaders();
  if (server.hasArg("dir")) {
    String cmd = server.arg("dir");
    char c = cmd[0];
    lastCmd = c;
    Serial.print(c);    // → Mega Serial1 → executes motor command
    server.send(200, "text/plain", "OK");
  } else {
    server.send(400, "text/plain", "Bad Request");
  }
}

// /status — Electron GUI polls this to confirm connection
// Returns JSON so React can parse it easily
void handleStatus() {
  addCORSHeaders();
  String json = "{";
  json += "\"status\":\"ok\",";
  json += "\"ssid\":\"" + String(ssid) + "\",";
  json += "\"ip\":\"" + WiFi.softAPIP().toString() + "\",";
  json += "\"last_cmd\":\"" + String(lastCmd) + "\",";
  json += "\"clients\":" + String(WiFi.softAPgetStationNum());
  json += "}";
  server.send(200, "application/json", json);
}

// / — original browser control page (still works as a backup)
// Kept exactly as your original with minor style fix
void handleRoot() {
  addCORSHeaders();
  String html = "<html><head><meta name='viewport' content='width=device-width'>";
  html += "<style>";
  html += "body{display:flex;justify-content:center;align-items:center;height:100vh;margin:0;background:#111;color:#fff;font-family:sans-serif;}";
  html += ".controls{text-align:center;}";
  html += "button{width:70px;height:70px;margin:5px;font-size:22px;border-radius:8px;border:none;background:#2d6a2d;color:#fff;cursor:pointer;}";
  html += "button:active{background:#1a4a1a;}";
  html += ".stop{background:#6a2d2d;} .stop:active{background:#4a1a1a;}";
  html += "</style>";
  html += "<script>";
  html += "function sendCommand(cmd){fetch('/cmd?dir='+cmd);}";
  html += "document.addEventListener('keydown',function(e){";
  html += "  const k=e.key.toLowerCase();";
  html += "  if(['w','a','s','d','b','c',' '].includes(k)){e.preventDefault();sendCommand(k);}";
  html += "});";
  html += "</script></head><body>";
  html += "<div class='controls'>";
  html += "<p style='margin-bottom:16px;font-size:14px;color:#888'>YieldVision Rover — Backup Control</p>";
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
  html += "</div></div></body></html>";
  server.send(200, "text/html", html);
}

void handleNotFound() {
  addCORSHeaders();
  server.send(404, "text/plain", "Not found");
}
