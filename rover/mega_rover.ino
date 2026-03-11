/*
 * mega_rover.ino
 * YieldVision — Arduino Mega Main Sketch
 *
 * MOTOR CODE: Your original MotorcodeLED.txt kept 100% intact.
 * ADDED on top:
 *   - Sensor reading (7-in-1 OR NPK+PH + capacitive moisture)
 *   - DHT22 air sensor
 *   - GPS zone detection
 *   - SD card logging
 *   - New command 'R' = trigger sensor reading on demand from GUI
 *
 * Architecture:
 *   ESP8266 (WiFi AP) → Serial1 (115200) → THIS sketch on Mega
 *   Commands arrive as single characters on Serial1, same as your original.
 *
 * Serial ports on Mega:
 *   Serial  (USB, pin 0/1)   — debug output to PC Serial Monitor
 *   Serial1 (pin 18/19)      — receives commands from ESP8266
 *   Serial2 (pin 16/17)      — GPS (GY-NEO6MV2)
 *   Serial3 (pin 14/15)      — RS485 soil sensor via MAX485
 *
 * ─────────────────────────────────────────────────────────────────────────
 * SENSOR SELECT — uncomment ONE combo
 * ─────────────────────────────────────────────────────────────────────────
 *
 *  OPTION A: 7-in-1 RS485 sensor (gives NPK + pH + moisture + temp + EC)
 *            Moisture comes from the sensor itself — no extra sensor needed.
 *
 *  OPTION B: NPK+PH RS485 sensor + Capacitive Moisture v2 on A0
 *            Use this if you get the cheaper NPK+PH-only probe.
 *            The capacitive sensor covers moisture separately.
 *
 * ─────────────────────────────────────────────────────────────────────────
 */

// ── PICK YOUR SENSOR COMBO ────────────────────────────────────────────────
#define SENSOR_7IN1
// #define SENSOR_NPKPH_PLUS_CAPACITIVE

// ── Includes ──────────────────────────────────────────────────────────────
#include <AFMotor.h>           // Your original motor library — unchanged
#include "sensor_dht22.h"
#include "sensor_gps.h"
#include "sd_storage.h"

#ifdef SENSOR_7IN1
  #include "sensor_7in1.h"
#endif

#ifdef SENSOR_NPKPH_PLUS_CAPACITIVE
  // #include "sensor_npkph.h"   // Uncomment when sensor arrives
  #include "sensor_capacitive_moisture.h"
#endif

// ─────────────────────────────────────────────────────────────────────────
// YOUR ORIGINAL LED + MOTOR CODE — UNCHANGED FROM MotorcodeLED.txt
// ─────────────────────────────────────────────────────────────────────────

// LEDs
const int redLED   = 41;
const int greenLED = 34;
unsigned long startMillis;
bool steadyOn      = true;
bool breathing     = false;
bool alternateBlink = false;
int  brightness    = 0;
bool increasing    = true;

// Motors — AFMotor shield, 4 motors
AF_DCMotor motor1(1);  // top right
AF_DCMotor motor2(2);  // top left
AF_DCMotor motor3(3);  // bottom left
AF_DCMotor motor4(4);  // bottom right

int motorSpeed  = 220;
int circleSpeed = 100;

// ─────────────────────────────────────────────────────────────────────────
// NEW: SENSOR STATE
// ─────────────────────────────────────────────────────────────────────────
const ZoneProfile* currentZone = nullptr;
uint16_t readingSeq = 0;

// ─────────────────────────────────────────────────────────────────────────
// SETUP
// ─────────────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(9600);       // Debug (USB) — your original baud
  Serial1.begin(115200);    // ESP8266 commands — your original baud

  // ── LEDs — your original init ──────────────────────────────────────────
  pinMode(redLED,   OUTPUT);
  pinMode(greenLED, OUTPUT);
  digitalWrite(redLED,   HIGH);
  digitalWrite(greenLED, HIGH);
  delay(5000);              // 5-second steady state — your original
  steadyOn  = false;
  breathing = true;
  startMillis = millis();

  // ── Sensors init ───────────────────────────────────────────────────────
  Serial.println(F("[BOOT] Sensors..."));

  #ifdef SENSOR_7IN1
    sensor7in1_begin();
    Serial.println(F("  7-in-1 RS485 ready"));
  #endif

  #ifdef SENSOR_NPKPH_PLUS_CAPACITIVE
    moisture_begin();
    Serial.println(F("  Capacitive moisture ready (A0)"));
  #endif

  dht22_begin();
  Serial.println(F("  DHT22 ready"));

  // SD card
  if (sd_begin()) {
    sd_loadFarmProfile();
  }

  // GPS
  gps_begin();
  Serial.println(F("  GPS initialised (waiting for fix in background)"));

  Serial.println(F("[BOOT] Ready. Waiting for commands on Serial1."));
}

// ─────────────────────────────────────────────────────────────────────────
// LOOP
// ─────────────────────────────────────────────────────────────────────────
void loop() {

  // ── Command handler — your original logic, plus new 'R' command ────────
  if (Serial1.available()) {
    char command = Serial1.read();

    if      (command == 'W' || command == 'w') { moveForward();    }
    else if (command == 'S' || command == 's') { moveBackward();   }
    else if (command == 'A' || command == 'a') { turnLeft();       }
    else if (command == 'D' || command == 'd') { turnRight();      }
    else if (command == 'B' || command == 'b') { burnoutSpin();    Serial.println(F("Burnout Spin")); }
    else if (command == 'C' || command == 'c') { moveInCircle();   }
    else if (command == ' ')                   { stopMotors();     }
    // NEW: 'R' = take a sensor reading right now
    else if (command == 'R' || command == 'r') { takeReading();    }
  }

  // ── LED effects — your original code, unchanged ────────────────────────
  if (breathing) {
    ledBreathingEffect();
  } else if (alternateBlink) {
    ledAlternatingBlink();
  }

  // ── GPS background feed ────────────────────────────────────────────────
  gps_feed();
}

// ─────────────────────────────────────────────────────────────────────────
// SENSOR READING — called on 'R' command from GUI
// ─────────────────────────────────────────────────────────────────────────
void takeReading() {
  stopMotors();     // Pause motors while reading for cleaner sensor data
  readingSeq++;
  Serial.print(F("\n[READ] #")); Serial.println(readingSeq);

  float n_ppm = -1, p_ppm = -1, k_ppm = -1;
  float ph = -1, moisture = -1, soil_temp = -999, ec = -1;
  bool soilValid = false;

  #ifdef SENSOR_7IN1
    SoilReading7in1 soil = sensor7in1_readAll();
    soilValid = soil.valid;
    n_ppm     = soil.nitrogen_ppm;
    p_ppm     = soil.phosphorus_ppm;
    k_ppm     = soil.potassium_ppm;
    ph        = soil.ph;
    moisture  = soil.humidity_pct;
    soil_temp = soil.temperature_c;
    ec        = soil.conductivity_us_cm;
    sensor7in1_print(soil);
  #endif

  #ifdef SENSOR_NPKPH_PLUS_CAPACITIVE
    // NPK+PH RS485 (add when sensor arrives):
    // SoilReadingNpkPh soil = sensorNpkPh_readAll();
    // n_ppm = soil.nitrogen_ppm; ...

    // Capacitive moisture on A0:
    MoistureReading moist = moisture_read();
    if (moist.valid) moisture = moist.moisture_pct;
    moisture_print(moist);
  #endif

  AirReading air = dht22_read();
  dht22_print(air);

  GpsReading gps = gps_read();
  if (gps.valid && _farm.loaded) {
    const ZoneProfile* z = sd_detectZone(gps.lat, gps.lon);
    if (z) currentZone = z;
  }

  float quality = 0.0;
  if (soilValid)  quality += 0.6;
  if (air.valid)  quality += 0.3;
  if (gps.valid)  quality += 0.1;

  const char* zid  = currentZone ? currentZone->zone_id    : "UNKNOWN";
  const char* zlbl = currentZone ? currentZone->zone_label : "??";

  char timestamp[24], datestr[12];
  unsigned long s = millis() / 1000;
  snprintf(timestamp, sizeof(timestamp), "2026-01-01T%02lu:%02lu:%02lu",
           (s/3600)%24, (s/60)%60, s%60);
  snprintf(datestr, sizeof(datestr), "20260101");  // TODO: replace with RTC

  bool logged = sd_logReading(
    timestamp, datestr, zid, zlbl,
    n_ppm, p_ppm, k_ppm, ph,
    moisture, soil_temp, ec,
    air.valid ? air.temperature_c : -999,
    air.valid ? air.humidity_pct  : -1,
    gps.valid ? gps.lat : 0,
    gps.valid ? gps.lon : 0,
    gps.valid ? gps.accuracy_m : 999,
    quality, readingSeq
  );

  Serial.print(F("[LOG] ")); Serial.println(logged ? F("Saved to SD") : F("SD write failed"));
}

// ─────────────────────────────────────────────────────────────────────────
// MOTOR FUNCTIONS — your original, untouched
// ─────────────────────────────────────────────────────────────────────────

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

// ─────────────────────────────────────────────────────────────────────────
// LED FUNCTIONS — your original, untouched
// ─────────────────────────────────────────────────────────────────────────

void ledBreathingEffect() {
  unsigned long currentMillis = millis();
  if (currentMillis - startMillis >= 10) {
    startMillis = currentMillis;
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

void ledAlternatingBlink() {
  digitalWrite(redLED, HIGH); digitalWrite(greenLED, LOW);  delay(200);
  digitalWrite(redLED, LOW);  digitalWrite(greenLED, HIGH); delay(200);
  digitalWrite(redLED, HIGH); digitalWrite(greenLED, LOW);  delay(1000);
  digitalWrite(redLED, LOW);  digitalWrite(greenLED, HIGH); delay(1000);
}
