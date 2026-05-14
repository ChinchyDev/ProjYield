/*
 * mega_rover.ino
 * YieldVision — Arduino Mega Main Sketch
 *
 * COMBINES: motor control (your original) + all sensors + WiFi data upload
 * NO SD CARD — readings buffered in RAM, sent to laptop via ESP8266 over WiFi
 *
 * ─── SERIAL PORT MAP ────────────────────────────────────────────────────────
 *
 *  Serial  (pins 0/1,  USB)     Debug output to PC Serial Monitor @ 9600
 *  Serial1 (pins 18/19)         GPS NEO-7M @ 9600  ← confirmed by your tester
 *  Serial2 (pins 16/17)         ESP8266 WiFi module @ 115200
 *  Serial3 (pins 14/15)         7-in-1 RS485 soil sensor via MAX485 @ 4800
 *
 * ─── PIN MAP ────────────────────────────────────────────────────────────────
 *
 *  RS485 MAX485 module:
 *    MAX485 DI    → Mega TX3  (pin 14)
 *    MAX485 RO    → Mega RX3  (pin 15)
 *    MAX485 DE+RE → pin 30    (tied together, direction control)
 *    MAX485 VCC   → 5V
 *    MAX485 GND   → GND
 *    Sensor Brown → 12V (or 5–30V DC)
 *    Sensor Black → GND
 *    Sensor Yellow→ MAX485 A
 *    Sensor Blue  → MAX485 B
 *
 *  DHT22:
 *    Pin 1 (VCC)  → 5V
 *    Pin 2 (DATA) → pin 22   (+ 10kΩ pull-up to 5V)
 *    Pin 4 (GND)  → GND
 *
 *  GPS NEO-7M:
 *    VCC          → 5V
 *    GND          → GND
 *    TX (GPS out) → Mega RX1 (pin 19)
 *    RX (GPS in)  → Mega TX1 (pin 18)   ← optional
 *
 *  ESP8266:
 *    TX           → Mega RX2 (pin 17)
 *    RX           → Mega TX2 (pin 16)
 *    VCC          → 3.3V
 *    GND          → GND (common with Mega GND — REQUIRED)
 *    CH_PD/EN     → 3.3V (enable pin, must be HIGH)
 *
 *  Motor shield (AFMotor) sits on top — uses pins 3,5,6,7,8,11,12.
 *  All pins above are clear of those.
 *
 * ─── COMMANDS (received on Serial2 from ESP8266) ────────────────────────────
 *  W/w  Forward       S/s  Backward
 *  A/a  Turn left     D/d  Turn right
 *  B/b  Burnout       C/c  Circle
 *  ' '  Stop
 *  R/r  Take a sensor reading and send to laptop
 *
 * ─── DATA FLOW ───────────────────────────────────────────────────────────────
 *  Rover collects → Mega formats JSON → sends to ESP8266 over Serial2
 *  ESP8266 receives JSON → POSTs to laptop FastAPI at 192.168.4.2:8000
 *  FastAPI processes → stored in PostgreSQL → appears in React frontend
 *
 * ─── LIBRARIES NEEDED ───────────────────────────────────────────────────────
 *  AFMotor          — Adafruit Motor Shield library
 *  DHT sensor library — Adafruit
 *  Adafruit Unified Sensor — Adafruit (dependency)
 *  TinyGPS++        — Mikal Hart
 */

// ============================================================================
// LIBRARIES
// ============================================================================

#include <AFMotor.h>
#include <DHT.h>
#include <TinyGPS++.h>

// ============================================================================
// PIN & PORT DEFINITIONS
// ============================================================================

#define DHT_PIN       22
#define DHT_TYPE      DHT22
#define RE_DE_PIN     30      // MAX485 direction control

// Serial aliases for readability
#define GPS_SERIAL    Serial1
#define ESP_SERIAL    Serial2
#define SOIL_SERIAL   Serial3

// Baud rates
#define DEBUG_BAUD    9600
#define GPS_BAUD      9600
#define ESP_BAUD      115200
#define SOIL_BAUD     4800

// ============================================================================
// READING BUFFER
// How many readings to hold in RAM before sending.
// Each reading is ~200 bytes of JSON. 10 readings = ~2KB, safe for Mega RAM.
// ============================================================================

#define BUFFER_SIZE   10

struct SensorReading {
  // Soil (7-in-1)
  float soil_moisture;
  float soil_temp;
  float ec;
  float ph;
  float nitrogen;
  float phosphorus;
  float potassium;
  bool  soil_valid;

  // Air (DHT22)
  float air_temp;
  float air_hum;
  bool  air_valid;

  // GPS
  double lat;
  double lon;
  float  gps_accuracy;
  bool   gps_valid;

  // Meta
  uint16_t seq;
  bool     sent;    // true once successfully uploaded
};

SensorReading readingBuffer[BUFFER_SIZE];
uint8_t  bufHead    = 0;   // next slot to write into
uint16_t readingSeq = 0;

// ============================================================================
// SENSOR OBJECTS
// ============================================================================

DHT        dht(DHT_PIN, DHT_TYPE);
TinyGPSPlus gps_module;

// Track daily temp min/max for ET₀
float tMax = -999.0;
float tMin =  999.0;

// Current zone (filled once GPS fix acquired and farm_id known)
// For now these come from the React frontend at session start via ESP8266
char farmId[40]  = "UNKNOWN";
char zoneId[40]  = "UNKNOWN";
char zoneLabel[8] = "??";

// ============================================================================
// MODBUS FRAMES — 7-in-1 RS485 sensor (CWT 5-pin probe manual)
// Register map:
//   0x0000 Humidity    ÷10 → %RH
//   0x0001 Temperature ÷10 → °C   (signed int16)
//   0x0002 Conductivity ×1 → µS/cm
//   0x0003 pH          ÷10 → pH
//   0x0004 Nitrogen    ×1  → mg/kg (ppm)
//   0x0005 Phosphorus  ×1  → mg/kg (ppm)
//   0x0006 Potassium   ×1  → mg/kg (ppm)
// ============================================================================

static const byte CMD_HUMIDITY[]     = {0x01,0x03,0x00,0x00,0x00,0x01,0x84,0x0A};
static const byte CMD_TEMPERATURE[]  = {0x01,0x03,0x00,0x01,0x00,0x01,0xD5,0xCA};
static const byte CMD_CONDUCTIVITY[] = {0x01,0x03,0x00,0x02,0x00,0x01,0x25,0xCA};
static const byte CMD_PH[]           = {0x01,0x03,0x00,0x03,0x00,0x01,0x74,0x0A};
static const byte CMD_NITROGEN[]     = {0x01,0x03,0x00,0x04,0x00,0x01,0xC5,0xCB};
static const byte CMD_PHOSPHORUS[]   = {0x01,0x03,0x00,0x05,0x00,0x01,0x94,0x0B};
static const byte CMD_POTASSIUM[]    = {0x01,0x03,0x00,0x06,0x00,0x01,0x64,0x0B};

// ============================================================================
// MOTOR OBJECTS  (AFMotor — your original setup)
// ============================================================================

AF_DCMotor motor1(1);  // top right
AF_DCMotor motor2(2);  // top left
AF_DCMotor motor3(3);  // bottom left
AF_DCMotor motor4(4);  // bottom right

int motorSpeed  = 220;
int circleSpeed = 100;

// ============================================================================
// LED SETUP  (your original)
// ============================================================================

const int redLED   = 41;
const int greenLED = 34;
unsigned long ledTimer;
bool breathing      = false;
bool alternateBlink = false;
int  brightness     = 0;
bool increasing     = true;

// ============================================================================
// SETUP
// ============================================================================

void setup() {
  // USB debug
  Serial.begin(DEBUG_BAUD);
  Serial.println(F("YieldVision booting..."));

  // GPS
  GPS_SERIAL.begin(GPS_BAUD);
  Serial.println(F("[GPS] Serial1 @ 9600"));

  // ESP8266
  ESP_SERIAL.begin(ESP_BAUD);
  Serial.println(F("[ESP] Serial2 @ 115200"));

  // 7-in-1 soil sensor
  pinMode(RE_DE_PIN, OUTPUT);
  digitalWrite(RE_DE_PIN, LOW);
  SOIL_SERIAL.begin(SOIL_BAUD, SERIAL_8N1);
  delay(500);
  Serial.println(F("[SOIL] Serial3 @ 4800"));

  // DHT22
  dht.begin();
  delay(2000);
  Serial.println(F("[DHT22] Ready"));

  // LEDs
  pinMode(redLED, OUTPUT);
  pinMode(greenLED, OUTPUT);
  digitalWrite(redLED, HIGH);
  digitalWrite(greenLED, HIGH);
  delay(5000);
  digitalWrite(redLED, LOW);
  digitalWrite(greenLED, LOW);
  breathing = true;
  ledTimer  = millis();

  // Init reading buffer
  for (uint8_t i = 0; i < BUFFER_SIZE; i++) readingBuffer[i].sent = true;

  Serial.println(F("Ready. Send 'R' to take reading."));
}

// ============================================================================
// LOOP
// ============================================================================

void loop() {
  // Feed GPS parser in background
  while (GPS_SERIAL.available()) gps_module.encode(GPS_SERIAL.read());

  // Handle commands from ESP8266 (motor + 'R' for reading)
  if (ESP_SERIAL.available()) {
    char cmd = ESP_SERIAL.read();
    handleCommand(cmd);
  }

  // Also accept 'R' directly from USB Serial Monitor for bench testing
  if (Serial.available()) {
    char cmd = Serial.read();
    if (cmd == 'R' || cmd == 'r') takeReading();
  }

  // Retry any unsent readings (e.g. ESP wasn't ready last time)
  retrySend();

  // LED effects
  if (breathing)      ledBreathing();
  else if (alternateBlink) ledAltBlink();
}

// ============================================================================
// COMMAND HANDLER
// ============================================================================

void handleCommand(char cmd) {
  switch (cmd) {
    case 'W': case 'w': moveForward();   break;
    case 'S': case 's': moveBackward();  break;
    case 'A': case 'a': turnLeft();      break;
    case 'D': case 'd': turnRight();     break;
    case 'B': case 'b': burnoutSpin();   break;
    case 'C': case 'c': moveInCircle();  break;
    case ' ':            stopMotors();   break;
    case 'R': case 'r': takeReading();   break;
    // Farm/zone context injected by ESP8266 when React app sets it
    // Format: F<farmId>  or  Z<zoneId>|<zoneLabel>
    default:
      if (cmd == 'F') receiveFarmId();
      if (cmd == 'Z') receiveZoneId();
      break;
  }
}

// ============================================================================
// RECEIVE FARM/ZONE CONTEXT FROM ESP8266
// Called when ESP8266 sends 'F' or 'Z' prefix followed by the ID string
// ============================================================================

void receiveFarmId() {
  // Read until newline, store in farmId
  uint8_t i = 0;
  unsigned long deadline = millis() + 500;
  while (millis() < deadline && i < sizeof(farmId) - 1) {
    if (ESP_SERIAL.available()) {
      char c = ESP_SERIAL.read();
      if (c == '\n') break;
      farmId[i++] = c;
    }
  }
  farmId[i] = '\0';
  Serial.print(F("[CTX] Farm ID set: ")); Serial.println(farmId);
}

void receiveZoneId() {
  // Format sent by ESP: <zone_id>|<zone_label>\n
  char buf[50];
  uint8_t i = 0;
  unsigned long deadline = millis() + 500;
  while (millis() < deadline && i < sizeof(buf) - 1) {
    if (ESP_SERIAL.available()) {
      char c = ESP_SERIAL.read();
      if (c == '\n') break;
      buf[i++] = c;
    }
  }
  buf[i] = '\0';

  // Split on '|'
  char* sep = strchr(buf, '|');
  if (sep) {
    *sep = '\0';
    strncpy(zoneId, buf, sizeof(zoneId) - 1);
    strncpy(zoneLabel, sep + 1, sizeof(zoneLabel) - 1);
  } else {
    strncpy(zoneId, buf, sizeof(zoneId) - 1);
  }
  Serial.print(F("[CTX] Zone: ")); Serial.print(zoneLabel);
  Serial.print(F(" (")); Serial.print(zoneId); Serial.println(F(")"));
}

// ============================================================================
// TAKE A SENSOR READING + BUFFER IT
// ============================================================================

void takeReading() {
  stopMotors();   // pause while reading for cleaner data

  readingSeq++;
  Serial.print(F("\n[READ] #")); Serial.println(readingSeq);

  // Find a free buffer slot (overwrite oldest if full)
  uint8_t slot = bufHead;
  bufHead = (bufHead + 1) % BUFFER_SIZE;
  SensorReading& r = readingBuffer[slot];
  r.sent = false;
  r.seq  = readingSeq;

  // --- Soil sensor ---
  readSoil(r);

  // --- DHT22 ---
  readAir(r);

  // --- GPS ---
  readGps(r);

  // Print summary
  printReading(r);

  // Try to send immediately
  sendReading(r);
}

// ============================================================================
// SOIL — 7-in-1 RS485 (Serial3)
// ============================================================================

bool sendModbus(const byte* cmd, uint8_t len, byte* buf, uint8_t expect) {
  while (SOIL_SERIAL.available()) SOIL_SERIAL.read();  // flush

  digitalWrite(RE_DE_PIN, HIGH);
  delay(10);
  for (uint8_t i = 0; i < len; i++) SOIL_SERIAL.write(cmd[i]);
  SOIL_SERIAL.flush();
  digitalWrite(RE_DE_PIN, LOW);
  delay(100);

  uint8_t count = 0;
  unsigned long deadline = millis() + 400;
  while (count < expect && millis() < deadline) {
    if (SOIL_SERIAL.available()) buf[count++] = SOIL_SERIAL.read();
  }
  return (count == expect);
}

int16_t parseModbus(const byte* buf) {
  return (int16_t)((buf[3] << 8) | buf[4]);
}

void readSoil(SensorReading& r) {
  byte buf[7];
  r.soil_valid = true;

  // Each register read, 200ms between them (sensor needs recovery time)
  if (sendModbus(CMD_HUMIDITY,     8, buf, 7)) r.soil_moisture  = parseModbus(buf) / 10.0;
  else { r.soil_moisture = -1; r.soil_valid = false; }
  delay(200);

  if (sendModbus(CMD_TEMPERATURE,  8, buf, 7)) r.soil_temp      = parseModbus(buf) / 10.0;
  else { r.soil_temp = -999; r.soil_valid = false; }
  delay(200);

  if (sendModbus(CMD_CONDUCTIVITY, 8, buf, 7)) r.ec             = (float)((uint16_t)parseModbus(buf));
  else { r.ec = -1; r.soil_valid = false; }
  delay(200);

  if (sendModbus(CMD_PH,           8, buf, 7)) r.ph             = parseModbus(buf) / 10.0;
  else { r.ph = -1; r.soil_valid = false; }
  delay(200);

  if (sendModbus(CMD_NITROGEN,     8, buf, 7)) r.nitrogen       = (float)((uint16_t)parseModbus(buf));
  else { r.nitrogen = -1; r.soil_valid = false; }
  delay(200);

  if (sendModbus(CMD_PHOSPHORUS,   8, buf, 7)) r.phosphorus     = (float)((uint16_t)parseModbus(buf));
  else { r.phosphorus = -1; r.soil_valid = false; }
  delay(200);

  if (sendModbus(CMD_POTASSIUM,    8, buf, 7)) r.potassium      = (float)((uint16_t)parseModbus(buf));
  else { r.potassium = -1; r.soil_valid = false; }
}

// ============================================================================
// AIR — DHT22 (pin 22)
// ============================================================================

void readAir(SensorReading& r) {
  float h = dht.readHumidity();
  float t = dht.readTemperature();

  if (isnan(h) || isnan(t) || t < -40 || t > 80) {
    r.air_valid = false;
    r.air_temp  = -999;
    r.air_hum   = -999;
    Serial.println(F("[DHT22] Read failed"));
    return;
  }

  if (t > tMax) tMax = t;
  if (t < tMin) tMin = t;

  r.air_temp  = t;
  r.air_hum   = h;
  r.air_valid = true;
}

// ============================================================================
// GPS — NEO-7M (Serial1)
// ============================================================================

void readGps(SensorReading& r) {
  // Feed a bit more GPS data before snapshotting
  unsigned long feed_until = millis() + 200;
  while (millis() < feed_until) {
    while (GPS_SERIAL.available()) gps_module.encode(GPS_SERIAL.read());
  }

  r.gps_valid = false;
  if (!gps_module.location.isValid()) {
    r.lat = 0; r.lon = 0; r.gps_accuracy = 999;
    return;
  }

  float hdop = gps_module.hdop.isValid() ? gps_module.hdop.value() / 100.0 : 99.0;
  r.lat          = gps_module.location.lat();
  r.lon          = gps_module.location.lng();
  r.gps_accuracy = hdop * 3.0;
  r.gps_valid    = (hdop <= 5.0);
}

// ============================================================================
// BUILD & SEND JSON TO ESP8266
// ============================================================================

/*
 * JSON format sent over Serial2 to ESP8266:
 * The ESP8266 receives this string and POSTs it to the laptop's FastAPI
 * at POST /readings/single
 *
 * We wrap it in  DATA:<json>\n  so ESP8266 knows what to forward vs
 * what are command characters (W, S, A, D etc.)
 */
void sendReading(SensorReading& r) {
  // Build JSON manually — no JSON library on Mega, keeps it lean
  // Matches the SensorReading Pydantic model in main_server.py exactly
  String json = "{";
  json += "\"zone_id\":\"";    json += zoneId;    json += "\",";
  json += "\"farm_id\":\"";    json += farmId;    json += "\",";
  json += "\"rover_id\":\"ROVER_01\",";
  json += "\"sequence_number\":"; json += r.seq; json += ",";
  json += "\"synced_from_sd\":false,";

  // GPS
  if (r.gps_valid) {
    json += "\"gps_lat\":";  json += String(r.lat, 6); json += ",";
    json += "\"gps_lon\":";  json += String(r.lon, 6); json += ",";
    json += "\"gps_accuracy_m\":"; json += r.gps_accuracy; json += ",";
  }

  // Soil
  if (r.soil_valid) {
    if (r.nitrogen   >= 0) { json += "\"nitrogen_ppm\":";            json += r.nitrogen;    json += ","; }
    if (r.phosphorus >= 0) { json += "\"phosphorus_ppm\":";          json += r.phosphorus;  json += ","; }
    if (r.potassium  >= 0) { json += "\"potassium_ppm\":";           json += r.potassium;   json += ","; }
    if (r.ph         >= 0) { json += "\"ph_level\":";                json += r.ph;          json += ","; }
    if (r.soil_moisture >= 0) { json += "\"soil_moisture_pct\":";    json += r.soil_moisture; json += ","; }
    if (r.soil_temp  > -900) { json += "\"soil_temperature_c\":";    json += r.soil_temp;   json += ","; }
    if (r.ec         >= 0) { json += "\"electrical_conductivity\":"; json += r.ec;          json += ","; }
  }

  // Air
  if (r.air_valid) {
    json += "\"air_temperature_c\":"; json += r.air_temp; json += ",";
    json += "\"air_humidity_pct\":";  json += r.air_hum;  json += ",";
  }

  // Remove trailing comma by trimming last char if it's a comma
  if (json.endsWith(",")) json.remove(json.length() - 1);
  json += "}";

  // Send to ESP8266 with DATA: prefix so it knows to forward this, not treat as motor command
  ESP_SERIAL.print(F("DATA:"));
  ESP_SERIAL.print(json);
  ESP_SERIAL.print('\n');

  Serial.print(F("[SEND] Forwarded to ESP8266 (seq ")); Serial.print(r.seq); Serial.println(F(")"));
  r.sent = true;  // optimistically mark sent — ESP will confirm or we retry
}

/*
 * Walk through buffer and retry any readings that weren't sent yet.
 * Called every loop() iteration — won't do anything if all sent.
 */
void retrySend() {
  for (uint8_t i = 0; i < BUFFER_SIZE; i++) {
    if (!readingBuffer[i].sent) {
      Serial.print(F("[RETRY] Resending seq ")); Serial.println(readingBuffer[i].seq);
      sendReading(readingBuffer[i]);
      return;  // one retry per loop tick — don't flood the serial buffer
    }
  }
}

// ============================================================================
// PRINT READING TO SERIAL MONITOR
// ============================================================================

void printReading(const SensorReading& r) {
  Serial.println(F("--- Soil (7-in-1) ---"));
  Serial.print(F("  Moisture  : ")); Serial.println(r.soil_moisture, 1);
  Serial.print(F("  Soil Temp : ")); Serial.println(r.soil_temp, 1);
  Serial.print(F("  EC        : ")); Serial.println(r.ec, 0);
  Serial.print(F("  pH        : ")); Serial.println(r.ph, 1);
  Serial.print(F("  Nitrogen  : ")); Serial.println(r.nitrogen, 0);
  Serial.print(F("  Phosphorus: ")); Serial.println(r.phosphorus, 0);
  Serial.print(F("  Potassium : ")); Serial.println(r.potassium, 0);
  Serial.print(F("  Valid     : ")); Serial.println(r.soil_valid ? F("YES") : F("NO"));

  Serial.println(F("--- Air (DHT22) ---"));
  Serial.print(F("  Air Temp  : ")); Serial.println(r.air_temp, 1);
  Serial.print(F("  Air Hum   : ")); Serial.println(r.air_hum, 1);
  Serial.print(F("  Valid     : ")); Serial.println(r.air_valid ? F("YES") : F("NO"));

  Serial.println(F("--- GPS (NEO-7M) ---"));
  if (r.gps_valid) {
    Serial.print(F("  Lat       : ")); Serial.println(r.lat, 6);
    Serial.print(F("  Lon       : ")); Serial.println(r.lon, 6);
    Serial.print(F("  Accuracy  : ~")); Serial.print(r.gps_accuracy, 1); Serial.println(F(" m"));
  } else {
    Serial.println(F("  Status    : NO FIX — go outdoors"));
  }
}

// ============================================================================
// MOTOR FUNCTIONS  (your original — untouched)
// ============================================================================

void moveForward() {
  motor1.setSpeed(motorSpeed); motor2.setSpeed(motorSpeed);
  motor3.setSpeed(motorSpeed); motor4.setSpeed(motorSpeed);
  motor1.run(FORWARD); motor2.run(FORWARD);
  motor3.run(FORWARD); motor4.run(FORWARD);
}

void moveBackward() {
  motor1.setSpeed(motorSpeed); motor2.setSpeed(motorSpeed);
  motor3.setSpeed(motorSpeed); motor4.setSpeed(motorSpeed);
  motor1.run(BACKWARD); motor2.run(BACKWARD);
  motor3.run(BACKWARD); motor4.run(BACKWARD);
}

void turnLeft() {
  motor1.setSpeed(motorSpeed); motor2.setSpeed(140);
  motor3.setSpeed(140);        motor4.setSpeed(motorSpeed);
  motor1.run(FORWARD);  motor2.run(BACKWARD);
  motor3.run(BACKWARD); motor4.run(FORWARD);
}

void turnRight() {
  motor1.setSpeed(140);        motor2.setSpeed(motorSpeed);
  motor3.setSpeed(motorSpeed); motor4.setSpeed(140);
  motor1.run(BACKWARD); motor2.run(FORWARD);
  motor3.run(FORWARD);  motor4.run(BACKWARD);
}

void moveInCircle() {
  motor1.setSpeed(motorSpeed); motor2.setSpeed(220);
  motor3.setSpeed(220);        motor4.setSpeed(motorSpeed);
  motor1.run(FORWARD);  motor2.run(BACKWARD);
  motor3.run(BACKWARD); motor4.run(FORWARD);
}

void stopMotors() {
  motor1.run(RELEASE); motor2.run(RELEASE);
  motor3.run(RELEASE); motor4.run(RELEASE);
}

void burnoutSpin() {
  motor1.setSpeed(175); motor2.setSpeed(175);
  motor3.setSpeed(motorSpeed); motor4.setSpeed(motorSpeed);
  motor1.run(FORWARD);  motor2.run(FORWARD);
  motor3.run(BACKWARD); motor4.run(BACKWARD);
}

// ============================================================================
// LED FUNCTIONS  (your original — untouched)
// ============================================================================

void ledBreathing() {
  if (millis() - ledTimer >= 10) {
    ledTimer = millis();
    if (increasing) {
      brightness++;
      if (brightness >= 255) increasing = false;
    } else {
      brightness--;
      if (brightness <= 0) {
        increasing    = true;
        breathing     = false;
        alternateBlink = true;
      }
    }
    analogWrite(redLED,   brightness);
    analogWrite(greenLED, brightness);
  }
}

void ledAltBlink() {
  digitalWrite(redLED, HIGH); digitalWrite(greenLED, LOW);  delay(200);
  digitalWrite(redLED, LOW);  digitalWrite(greenLED, HIGH); delay(200);
  digitalWrite(redLED, HIGH); digitalWrite(greenLED, LOW);  delay(1000);
  digitalWrite(redLED, LOW);  digitalWrite(greenLED, HIGH); delay(1000);
}
