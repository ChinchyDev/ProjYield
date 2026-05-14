# YieldVision Precision Farming System

A research-backed precision farming decision engine built for Kenyan smallholder farmers. YieldVision uses a sensor-equipped autonomous rover to map soil health across farm zones and generate actionable, science-grounded recommendations — telling farmers exactly what to apply, how much it costs in KES, and why.

---

## What It Actually Does

Most farming apps tell you your soil is "low in nitrogen." YieldVision tells you:

> *"Zone A2 needs 46 grams of CAN fertilizer (~KES 3). Apply before next rain. Based on your maize variety (H614D) and current soil readings. Confidence: High — based on published KALRO research."*

Every number is traceable to a sensor reading or a published agricultural science source. Nothing is made up.

---

## System Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     LAPTOP SERVER                            │
│                                                              │
│  FastAPI (Port 8000)   ──►  PostgreSQL (Port 5432)          │
│  ML Decision Engine    ──►  PostGIS (Spatial queries)       │
│  Python Desktop GUI    ──►  Market Price Cache (KAMIS)      │
└──────────────────────────────┬───────────────────────────────┘
                               │ WiFi (sync only)
                               │
┌──────────────────────────────▼───────────────────────────────┐
│                    ARDUINO ROVER (ROVER_01)                   │
│                                                              │
│  Arduino Mega 2560                                           │
│  ├── ComWinTop 7-in-1 Soil Sensor (RS485/MAX485)            │
│  │   └── NPK, pH, Moisture, Soil Temp, EC                   │
│  ├── DHT22 (Air Temp + Humidity)                            │
│  ├── NEO-6M GPS Module                                       │
│  ├── SD Card Module (offline data storage)                  │
│  └── Motor Driver (rover movement)                          │
│                                                              │
│  Power: 4× 18650 batteries (14.8V) → motors + sensors      │
│         Powerbank → Arduino Mega + breadboard               │
└──────────────────────────────────────────────────────────────┘
```

### Key Design Principle: Offline-First

The rover **never needs WiFi to collect data.** It collects and saves to SD card regardless of connectivity. WiFi is only used for syncing data to the server and downloading updated farm profiles. If WiFi is unavailable, nothing is lost.

---

## Hardware

| Component | Model | Purpose |
|---|---|---|
| Microcontroller | Arduino Mega 2560 | Main controller |
| Soil Sensor | ComWinTop 7-in-1 (RS485) | NPK, pH, moisture, soil temp, EC |
| Air Sensor | DHT22 | Air temperature + humidity |
| GPS | NEO-6M | Zone identification |
| Communication | MAX485 Module | RS485 to UART for soil sensor |
| Storage | SD Card Module | Offline data buffer |
| Connectivity | ESP8266 / WiFi Shield | Server sync |
| Motor Power | 4× 18650 (14.8V pack) | Drive motors + sensors |
| Logic Power | Powerbank | Arduino Mega + breadboard |

---

## Database Design

PostgreSQL only — InfluxDB removed. All time-series data lives in PostgreSQL with proper indexing.

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

1. **Row Level Security** on every table with `farm_id` — database physically cannot return another farm's data regardless of query
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
| AGRA/IFDC Fertilizer Blends Kenya (2018) | Kenyan fertilizer product catalogue and prices |
| ECOCROP (FAO) | Crop growing condition ranges |
| KALRO Crop Variety Catalogue (2023) | Kenyan variety performance data |
| KAMIS (Kenya Agri. Market Information System) | Live market prices |

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
├── database_setup.sql          # Full PostgreSQL schema (v2.0)
├── main_server.py              # FastAPI backend
├── precision_gui.py            # Desktop GUI (CustomTkinter)
├── precision_models.py         # ML models (YieldSoil, YieldSeed)
├── requirements.txt            # Python dependencies
├── README.md                   # This file
│
├── arduino_rover/
│   └── rover_controller.ino   # Arduino rover firmware
│
├── mock_data/
│   ├── mock_historical_data.sql    # 2 past seasons for demo soil box
│   └── mock_sensor_readings.json   # Synthetic readings for testing
│
└── docs/
    └── PROJECT_REPORT_M2_UPDATE.md
```

Files to be created next:
```
├── zone_generator.py           # Polygon zone creation from GPS boundary drive
├── farm_manager.py             # Farm profile, rover assignment, GPS detection
├── rover_sync.py               # SD card batch upload handler
├── decision_engine.py          # Recommendation generation with full calc trace
```

---

## Setup

### Prerequisites

- Python 3.8+
- PostgreSQL 14+ with PostGIS extension
- Arduino IDE (for rover firmware)
- Windows laptop (development server)

### Database Setup

```bash
# Install PostGIS via Stack Builder (comes with PostgreSQL on Windows)
# Then in psql:
psql -U postgres -f database_setup.sql
```

### Python Server

```bash
pip install -r requirements.txt
python main_server.py
```

### GUI

```bash
python precision_gui.py
```

### Arduino

1. Open `arduino_rover/rover_controller.ino` in Arduino IDE
2. Set WiFi credentials and server IP
3. Upload to Arduino Mega 2560

---

## Development Roadmap

### Phase 1 — Hardware Integration *(current)*
- [ ] Wire ComWinTop sensor via MAX485
- [ ] Confirm NPK, pH, moisture readings on serial monitor
- [ ] DHT22 air readings working
- [ ] NEO-6M GPS fix confirmed
- [ ] SD card read/write working
- [ ] End-to-end: sensor → SD → WiFi → PostgreSQL

### Phase 2 — Real Data Pipeline
- [ ] Farm boundary capture via GPS drive
- [ ] Zone polygon generation (zone_generator.py)
- [ ] SD card batch sync (rover_sync.py)
- [ ] Idempotent upload confirmed (retry test)
- [ ] zone_current_state view returning correct staleness flags

### Phase 3 — Crop Data & Knowledge Base
- [ ] All 9 crop varieties seeded in database
- [ ] Soil type reference table validated against FAO56
- [ ] Fertilizer products table with current KES prices
- [ ] Growth stage auto-calculation from planting date working

### Phase 4 — Decision Engine
- [ ] pH hard gate implemented and tested
- [ ] Irrigation volume calc traced to FAO56
- [ ] Fertilizer translation (ppm → grams → KES)
- [ ] Urgency scoring on all recommendations
- [ ] Plain language confidence labels

### Phase 5 — Onboard Intelligence (Arduino)
- [ ] Point-in-polygon zone detection on Arduino
- [ ] Farm profile stored and read from SD card
- [ ] Offline-first flow confirmed (no WiFi needed for collection)

### Phase 6 — Demo Polish
- [ ] Mock historical data (2 seasons) loaded for demo soil box
- [ ] GUI showing zone map, recommendations, KES costs
- [ ] KAMIS price integration (or hardcoded current prices for demo)
- [ ] Full demo flow: power on rover → collect → sync → recommendation appears in GUI

---

## Current Status

| Component | Status |
|---|---|
| Database schema v2.0 | ✅ Complete |
| Crop varieties seed data | ✅ 9 varieties loaded |
| Fertilizer products (KES) | ✅ 11 products loaded |
| Soil type reference (FAO56) | ✅ 5 soil types loaded |
| Arduino rover firmware | 🔄 In progress |
| Hardware wiring | ⏳ Hardware in transit |
| Decision engine | ⏳ Next |
| Farm boundary capture GUI | ⏳ Next |
| Mock historical data | ⏳ Next |

---

*YieldVision — Research-backed farming decisions for Kenyan smallholders.*-* - 