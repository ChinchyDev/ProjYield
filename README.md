# YieldVision Precision Farming System

A precision farming decision engine built for Kenyan smallholder farmers. YieldVision uses a sensor-equipped rover to map soil health across farm zones and generate plain-language, science-backed recommendations — telling farmers exactly what to apply, how much it costs in KES, and why.

---

## What It Actually Does

Most farming apps tell you your soil is "low in nitrogen." YieldVision tells you:

> *"Zone A2 needs 46 grams of CAN fertilizer (~KES 3). Apply before next rain. Based on your maize variety (H614D) and current soil readings. Confidence: High — based on published KALRO research."*

Every number traces back to either a sensor reading or a published agricultural science source.

---

## System Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     LAPTOP SERVER                            │
│                                                              │
│  FastAPI (Port 8000)   ──►  PostgreSQL (Port 5432)          │
│  ML Decision Engine    ──►  PostGIS (Spatial queries)       │
│  React + Electron App  ──►  Market Price Cache (KAMIS)      │
└──────────────────────────────┬───────────────────────────────┘
                               │ WiFi (sync only, not required)
                               │
┌──────────────────────────────▼───────────────────────────────┐
│                    ARDUINO ROVER (ROVER_01)                   │
│                                                              │
│  Arduino Mega 2560                                           │
│  ├── 7-in-1 RS485 Soil Probe (ComWinTop / similar)          │
│  │   └── NPK, pH, Moisture, Soil Temp, EC (via MAX485)      │
│  ├── DHT22 (Air Temp + Humidity)                            │
│  ├── GY-NEO6MV2 GPS Module                                  │
│  ├── Capacitive Moisture Sensor v2 (backup moisture)        │
│  ├── SD Card Module (offline data storage)                  │
│  ├── ESP8266 (SoftAP, SSID "YieldVision", 192.168.4.1)     │
│  └── AFMotor Shield (rover movement)                        │
│                                                              │
│  Power: 4× 18650 batteries → motors + sensors               │
│         Powerbank → Arduino Mega + breadboard                │
└──────────────────────────────────────────────────────────────┘
```

### Key Design Principle: Offline-First

The rover **never needs WiFi to collect data.** It logs to SD card regardless of connectivity. WiFi (via the ESP8266 SoftAP) is only used to sync data to the laptop server and receive rover control commands. No router required — the rover creates its own network.

---

## Hardware

| Component | Model | Purpose |
|---|---|---|
| Microcontroller | Arduino Mega 2560 | Main controller |
| Soil Sensor | 7-in-1 RS485 probe (ComWinTop-style) | NPK, pH, moisture, soil temp, EC |
| RS485 Interface | MAX485 Module | RS485 to UART conversion |
| Air Sensor | DHT22 | Air temperature + humidity |
| GPS | GY-NEO6MV2 | Zone identification |
| Backup Moisture | Capacitive Moisture Sensor v2 | ~KES 300, moisture redundancy |
| WiFi | ESP8266 (SoftAP mode) | Rover control + data relay, no router needed |
| Storage | SD Card Module | Offline data buffer |
| Motor Control | AFMotor Shield | Drive motors (WASD + GUI control) |
| Motor Power | 4× 18650 (14.8V pack) | Drive + sensors |
| Logic Power | Powerbank | Arduino Mega + breadboard |

> **Sourcing note:** The 7-in-1 probe is available on AliExpress for ~$8–12 (search "7 in 1 soil sensor RS485 NPK pH EC"). If your sensor is a different brand (e.g. Sunicon vs. ComWinTop), the register order or default baud rate may differ by two lines in `sensor_7in1.h` — always cross-check your product manual.

---

## Frontend

The desktop interface is built with **React + Electron**, shipping as both a proper installable desktop app and a PWA from a single codebase. No separate Python GUI.

- Offline-first with local cache (last 2 hours of data available without server)
- GPS-based dynamic zone mapping
- Urgency-coded colour scheme with floating bottom navigation
- Dark/light mode
- Fully wired to FastAPI backend

> Design palette: `#1B2727 #3C5148 #6B8E4E #B2C5B2 #D5DDDF`

---

## Database Design

PostgreSQL only (InfluxDB removed). All time-series data lives in PostgreSQL with proper indexing and PostGIS for spatial queries.

### Core Tables

| Table | Purpose |
|---|---|
| `farms` | Farm profiles with GPS boundary polygons |
| `zones` | Sub-zones within farms, polygon-defined |
| `rovers` | Registered rovers (currently: ROVER_01) |
| `rover_schedule` | Priority queue for shared rover visits |
| `sensor_readings` | All sensor data, idempotent upload keys |
| `zone_crops` | Active and historical plantings (soft delete) |
| `crop_varieties` | Research-backed optimal ranges per variety |
| `soil_type_reference` | FAO56 field capacity, bulk density by soil type |
| `fertilizer_products` | 11 real Kenyan products with KES prices |
| `recommendations` | Generated recommendations with full calc trace |
| `amendments` | What was actually applied |
| `irrigation_events` | Irrigation log with FAO56 calculation trace |
| `market_prices` | Cached KAMIS prices, graceful staleness fallback |
| `alerts` | Urgency-scored, batched to prevent alert fatigue |
| `regional_calibration` | Layer 2: regional adjustments from multi-farm data |
| `yield_history` | Season outcomes for Layer 3 farm-specific learning |
| `staleness_thresholds` | Configurable freshness limits per parameter type |

### Key Views

**`zone_current_state`** — Single source of truth for all staleness checks. Every component queries this view, never raw sensor tables directly. Contains latest reading per zone plus computed `is_stale_*` booleans.

**`pending_recommendations`** — What the farmer should act on today, ordered by urgency score.

**`rover_dispatch_priority`** — Which farm needs the rover most urgently based on staleness scores.

### Architecture Decisions Baked In

1. **Row Level Security** — every table with `farm_id` uses RLS; the database physically cannot return another farm's data
2. **Polygon containment zones** — zone identity is a human label (A1, Z01), GPS used only for spatial math via PostGIS
3. **Idempotent uploads** — rover generates `reading_uuid = rover_id + timestamp_ms + seq` at collection time; server uses `ON CONFLICT DO NOTHING` so retrying uploads never creates duplicates
4. **Single staleness view** — one definition of "stale", enforced once, trusted everywhere
5. **Soft deletes only** — historical data never deleted, only status-changed; ML learns from previous seasons
6. **Rover scheduling queue** — urgency scores tell operator which farm gets rover priority

---

## Rover Startup Sequence

```
Power on
│
├─ GPS fix acquired? ──────────────────────────────────────────┐
│   └── Wait up to 60 seconds                                  │
│       └── Still no fix → alert operator, do not collect     │
│                                                              ▼
├─ Read SD card for farm profile ──────────────────────────────┤
│   └── Run point-in-polygon check → identify zone            │
│       └── No profile on SD? → WiFi required for first setup │
│                                                              ▼
├─ Collect sensor readings ────────────────────────────────────┤
│   └── Generate reading_uuid (ROVER_01_timestamp_seq)        │
│       └── Save to SD card                                   │
│                                                              ▼
└─ WiFi available? ────────────────────────────────────────────┘
    ├── YES → Bulk upload SD → Download fresh farm profile
    └── NO  → Continue collecting, everything safe on SD
```

---

## Recommendation Engine

### Three-Layer Knowledge System

| Layer | Active When | Source | Label Shown to Farmer |
|---|---|---|---|
| 1 — Published Science | Day one | FAO56, KALRO, IFDC, ECOCROP | *"Based on published research"* |
| 2 — Regional | After multiple farms in same area | Regional calibration table | *"Calibrated for your region"* |
| 3 — Farm-Specific | After 1+ full seasons on this farm | Yield history + amendment outcomes | *"Learned from your farm's history"* |

System works on day one. Gets smarter every season.

### Irrigation Calculation (FAO56)

All irrigation math is traceable to FAO Irrigation and Drainage Paper No. 56.

```
Water to apply (liters) =
  (Field Capacity % - Current Moisture %)
  × Bulk Density
  × Root Depth
  × Zone Area
  × Drainage Factor
  ÷ 1000

Days until next irrigation =
  Plant Available Water × Root Depth × Depletion Fraction p
  ÷ Daily ETcrop

Daily ETcrop = ET₀ × Kc (crop coefficient for current growth stage)

ET₀ via Hargreaves-Samani (using DHT22 air temp readings):
  ET₀ = 0.0023 × (Tmean + 17.8) × (Tmax - Tmin)^0.5 × Ra
```

Ra (extraterrestrial radiation) is a published lookup by latitude and month — baked into code permanently, no API needed.

### pH Hard Gate

**If soil pH is more than 0.5 units outside the crop's viable range, all NPK fertilizer recommendations are blocked.** The system returns only a pH correction recommendation with a `do_not_fertilize_until` flag.

This prevents the most common money-wasting mistake in Kenyan smallholder farming: spending KES 2,000 on fertilizer for acidic soil where nutrients cannot be absorbed.

### Why EC Can't Be Skipped

Electrical conductivity (EC) is architecturally required — the decision engine uses it to validate the `HIGH_EC_LOW_NPK` flag that catches sensor errors and scores data quality confidence. It can't be substituted cheaply and still pass that check.

### Fertilizer Translation

Recommendations are never in abstract units. Always:

> *"Zone 3 needs 46g of CAN fertilizer (~KES 3 from agro-dealer). Apply as top-dressing after rain."*

Translation chain: `sensor ppm deficit → kg nutrient needed → grams of specific Kenyan product → KES cost`

### Urgency Scoring

```
Urgency score =
  (Deviation from optimal / Optimal range)
  × Growth stage multiplier (2.0× at germination/flowering, 0.5× at maturity)
  × Ignored penalty (0.7× if same recommendation previously ignored)

CRITICAL (>2.0) → Immediate red alert
HIGH     (1.0–2.0) → Today's action list
MEDIUM   (0.5–1.0) → Weekly summary
LOW      (<0.5) → Logged silently
```

Maximum 3 CRITICAL alerts per farm per day. Farmer never gets alert fatigue.

### Confidence Labels

Raw confidence scores are stored in the database for ML use only. Farmers see plain language:

| Score | Label | Explanation |
|---|---|---|
| >0.85 + farm history | High confidence | *"Based on how your farm responded before"* |
| >0.70 | Moderate confidence | *"Based on research for similar farms"* |
| >0.50 | Low confidence | *"Starting point — monitor closely"* |
| <0.50 | Uncertain | *"Collect more readings before acting"* |

---

## Supported Crops

| Crop | Varieties | Season | Market Price (KES/kg) |
|---|---|---|---|
| Maize | H614D, DK8031, DUMA 43 | 95–130 days | 40–55 |
| Beans | Rosecoco GLP2, Mwezi Moja | 65–85 days | 80–130 |
| Potatoes | Shangi, Dutch Robjin | 90–110 days | 25–50 |
| Tomatoes | Rambo F1, Money Maker | 75–145 days | 30–80 |
| Kale | Collard Mfalme F1 | Continuous | 3–15/bunch |

All optimal ranges (pH, NPK, moisture, temperature, EC) sourced from KALRO, FAO56, and ECOCROP.

---

## Research Sources

Every number in the recommendation engine is traceable to one of these:

| Source | Used For |
|---|---|
| FAO Irrigation and Drainage Paper No. 56 (1998) | All irrigation math — ET, Kc values, field capacity, depletion fractions |
| FAO Paper No. 33 — Yield Response to Water | Yield loss estimation under water stress |
| KALRO Soil Acidity and Liming Handbook for Kenya (2023) | Lime application rates for Kenyan soils |
| IFDC Fertilizer Use by Crop in Kenya | NPK requirements, fertilizer product recommendations |
| IFDC Fertilizer Quality Assessment in Markets of Kenya | Actual NPK % in Kenyan market fertilizers |
| ECOCROP (FAO) | Crop growing condition ranges |
| KALRO Crop Variety Catalogue (2023) | Kenyan variety performance data |
| KAMIS (Kenya Agri. Market Information System) | Live market prices |
| NPKGRIDS dataset (Kalleske et al., 2024) | Soil nutrient spatial reference |

---

## Market Data

Market prices cached from **KAMIS** (Kenya Agricultural Market Information System) — the official government agricultural price database.

- Updates daily when internet is available
- Falls back to last known price if offline
- Prices older than 30 days are flagged as stale
- ROI calculations always use current price, never locked-in historical price

**KAMIS API:** https://kamis.kilimo.go.ke

---

## Project Structure

```
ProjYield/
├── backend/
│   ├── main_server.py          # FastAPI backend (all API endpoints)
│   ├── decision_engine.py      # Recommendation orchestrator
│   ├── precision_models.py     # YieldSoil + YieldSeed models
│   ├── irrigation_engine.py    # FAO56 irrigation math
│   ├── edge_storage.py         # SQLite edge storage + PostgreSQL sync
│   └── database_setup.sql      # Full PostgreSQL schema (v2.0)
│
├── rover/
│   ├── mega_rover.ino          # Arduino Mega main sketch (motors + sensors)
│   └── esp8266_wifi.ino        # ESP8266 SoftAP + command bridge
│
├── frontend/
│   └── PWA/src/
│       ├── App.js              # Main app shell + navigation
│       ├── api.js              # FastAPI client with offline cache
│       └── components/
│           ├── Dashboard.js
│           ├── Farm.js
│           ├── Tasks.js
│           ├── Reports.js
│           ├── Alerts.js
│           └── RecommendationModal.js
│
├── requirements.txt
└── README.md
```

---

## Setup

### Prerequisites

- Python 3.8+
- PostgreSQL 14+ with PostGIS extension
- Node.js 18+ (for React/Electron frontend)
- Arduino IDE (for rover firmware)

### Database Setup

```bash
# Install PostGIS via Stack Builder (comes with PostgreSQL on Windows)
# Then in psql:
psql -U postgres -f backend/database_setup.sql
```

### Python Server

```bash
pip install -r requirements.txt
python backend/main_server.py
```

### Frontend (React + Electron)

```bash
cd frontend
npm install
npm start          # development (PWA in browser)
npm run electron   # desktop app
```

### Arduino

1. Open `rover/mega_rover.ino` in Arduino IDE
2. Open `rover/esp8266_wifi.ino` for the ESP8266 (separate upload)
3. Upload Mega sketch to Arduino Mega 2560
4. Upload ESP8266 sketch to ESP8266 module
5. Laptop connects to WiFi SSID "YieldVision", password "rover1234"
6. React app available at `http://localhost:3000`, API at `http://localhost:8000`

---

## Current Status

| Component | Status |
|---|---|
| Database schema v2.0 | ✅ Complete |
| Crop varieties seed data (9 varieties) | ✅ Complete |
| Fertilizer products table (11 Kenyan products, KES prices) | ✅ Complete |
| Soil type reference (FAO56) | ✅ Complete |
| FastAPI backend (all endpoints) | ✅ Complete |
| Decision engine + recommendation logic | ✅ Complete |
| Irrigation engine (FAO56-traced) | ✅ Complete |
| Arduino rover firmware (motors + sensors) | ✅ Complete |
| ESP8266 SoftAP + command bridge | ✅ Complete |
| React + Electron frontend (26 files) | ✅ Complete |
| Hardware components | ⏳ Ordered (AliExpress, delivery pending) |
| Physical sensor validation | ⏳ Awaiting hardware |
| GitHub README (was outdated) | ✅ Now updated |

### Pending Academic Documentation

- [ ] Data Flow Diagrams (DFDs)
- [ ] ER Diagrams
- [ ] Field testing results
- [ ] ML model evaluation
- [ ] Sensor justification write-up
- [ ] UI screenshots

---

*YieldVision — Research-backed farming decisions for Kenyan smallholders.*