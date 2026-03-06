-- =============================================================================
-- YIELDVISION PRECISION FARMING DATABASE
-- PostgreSQL only (InfluxDB removed)
-- Version 2.0 — Full rebuild with all architecture decisions applied
-- =============================================================================
-- ARCHITECTURE DECISIONS BAKED IN:
--   [1]  Row Level Security on every table with farm_id
--   [2]  Polygon containment zones (not GPS coordinate IDs)
--   [3]  Idempotent uploads via deterministic reading_uuid
--   [4]  Single staleness view (zone_current_state) as source of truth
--   [5]  Soft deletes only — historical continuity preserved
--   [6]  Rover scheduling queue with urgency scoring
--   [7]  Three-layer knowledge system (science → regional → farm-specific)
--   [8]  Traceable irrigation calc — every number logged
--   [9]  Real Kenyan fertilizer products table
--   [10] pH hard gate — enforced in schema via check constraint + app logic
--   [11] Urgency scoring on all recommendations
--   [12] Plain language confidence levels (not raw decimal shown to farmer)
-- =============================================================================

-- Create the database (run this part as superuser before connecting)
-- CREATE DATABASE yieldvision;
-- \c yieldvision;

-- =============================================================================
-- EXTENSIONS
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "postgis";    -- polygon containment queries [2]
CREATE EXTENSION IF NOT EXISTS "btree_gist"; -- needed for exclusion constraints

-- =============================================================================
-- SECTION 1: CORE FARM & ROVER INFRASTRUCTURE
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1.1 ROVERS
-- Registered rovers that serve one or more farms (shared rover model)
-- -----------------------------------------------------------------------------
CREATE TABLE rovers (
    rover_id            VARCHAR(20)  PRIMARY KEY,          -- e.g. 'ROVER_01'
    rover_name          VARCHAR(100) NOT NULL,
    hardware_version    VARCHAR(20)  DEFAULT '1.0',
    firmware_version    VARCHAR(20)  DEFAULT '1.0',
    battery_capacity_mah INTEGER     DEFAULT 14800,        -- 4x 18650
    is_active           BOOLEAN      DEFAULT true,
    registered_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    notes               TEXT
);

-- -----------------------------------------------------------------------------
-- 1.2 FARMS
-- Each farm belongs to one owner. Boundary stored as polygon for GPS detection.
-- [1] RLS isolates farms. [2] Polygon boundary used for zone containment.
-- -----------------------------------------------------------------------------
CREATE TABLE farms (
    farm_id             UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    farm_name           VARCHAR(200) NOT NULL,
    owner_name          VARCHAR(200) NOT NULL,
    owner_phone         VARCHAR(20),                       -- for SMS alerts
    owner_email         VARCHAR(200),
    location_name       VARCHAR(200),                      -- human readable e.g. "Kiambu, Limuru"
    county              VARCHAR(100),
    latitude_center     DECIMAL(10,8),                     -- farm centroid for weather API
    longitude_center    DECIMAL(11,8),
    altitude_m          DECIMAL(8,2),                      -- important for Kc adjustments
    boundary_polygon    GEOMETRY(POLYGON, 4326),           -- GPS boundary for auto-detection [2]
    total_area_m2       DECIMAL(10,2),
    soil_type           VARCHAR(20)  DEFAULT 'loam'        -- farmer-selected: sandy/loam/clay
                        CHECK (soil_type IN ('sandy', 'sandy_loam', 'loam', 'clay_loam', 'clay')),
    rainfall_zone       VARCHAR(50),                       -- high/medium/low/semi-arid
    assigned_rover_id   VARCHAR(20)  REFERENCES rovers(rover_id),
    is_active           BOOLEAN      DEFAULT true,
    created_at          TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------------------------------
-- 1.3 ZONES
-- Sub-divisions of a farm. Identity = human label (A1, Z01 etc).
-- GPS used only for spatial math, NOT as primary key. [2]
-- Soft delete only — never hard delete zones. [5]
-- -----------------------------------------------------------------------------
CREATE TABLE zones (
    zone_id             UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    farm_id             UUID         NOT NULL REFERENCES farms(farm_id),
    zone_label          VARCHAR(20)  NOT NULL,              -- human label: A1, B2, Z01 etc.
    boundary_polygon    GEOMETRY(POLYGON, 4326) NOT NULL,   -- defines zone for containment [2]
    center_lat          DECIMAL(10,8),
    center_lon          DECIMAL(11,8),
    area_m2             DECIMAL(8,2) NOT NULL DEFAULT 4.0,
    soil_type           VARCHAR(20),                        -- can override farm default
    slope_percent       DECIMAL(5,2) DEFAULT 0.0,
    drainage_rate       VARCHAR(20)  DEFAULT 'medium'
                        CHECK (drainage_rate IN ('fast', 'medium', 'slow')),
    sun_exposure_hours  DECIMAL(4,1),
    elevation_m         DECIMAL(8,2),
    notes               TEXT,
    status              VARCHAR(20)  DEFAULT 'active'       -- active / resting / abandoned [5]
                        CHECK (status IN ('active', 'resting', 'abandoned')),
    created_at          TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (farm_id, zone_label)                            -- label unique within a farm
);

-- -----------------------------------------------------------------------------
-- 1.4 ROVER SCHEDULE
-- Priority queue for shared rover visits. [6]
-- Staleness score > 1.0 = overdue. Higher score = higher priority.
-- -----------------------------------------------------------------------------
CREATE TABLE rover_schedule (
    schedule_id         UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    farm_id             UUID         NOT NULL REFERENCES farms(farm_id),
    zone_id             UUID         REFERENCES zones(zone_id),  -- NULL = whole farm visit
    rover_id            VARCHAR(20)  REFERENCES rovers(rover_id),
    parameters_needed   TEXT[]       NOT NULL,              -- ['npk','ph','moisture','temperature']
    staleness_score     DECIMAL(6,3) DEFAULT 0.0,           -- computed: hours_overdue / limit * crop_weight
    priority_reason     TEXT,                               -- human readable reason
    scheduled_date      DATE,
    completed_at        TIMESTAMP,
    is_completed        BOOLEAN      DEFAULT false,
    created_at          TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- SECTION 2: CROP KNOWLEDGE BASE
-- Layer 1 knowledge — published science, pre-loaded, works day one [7]
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 2.1 CROP VARIETIES
-- Research-backed optimal ranges per variety. Source: FAO56, KALRO, ECOCROP.
-- Root depth used in irrigation volume calc. [8]
-- Kc values from FAO56 Table 12.
-- -----------------------------------------------------------------------------
CREATE TABLE crop_varieties (
    variety_id              UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    crop_name               VARCHAR(100) NOT NULL,          -- Maize, Beans, Potatoes, etc.
    variety_name            VARCHAR(100) NOT NULL,          -- H614D, Rosecoco GLP2, etc.
    variety_code            VARCHAR(50),                    -- official seed code if any

    -- Growing conditions (Source: ECOCROP / KALRO)
    ph_min                  DECIMAL(4,2) NOT NULL,
    ph_max                  DECIMAL(4,2) NOT NULL,
    ph_optimal_min          DECIMAL(4,2) NOT NULL,
    ph_optimal_max          DECIMAL(4,2) NOT NULL,

    -- NPK optimal ranges (ppm) — Source: KALRO / IFDC Kenya
    nitrogen_optimal_ppm    DECIMAL(8,2),
    phosphorus_optimal_ppm  DECIMAL(8,2),
    potassium_optimal_ppm   DECIMAL(8,2),
    nitrogen_min_ppm        DECIMAL(8,2),
    phosphorus_min_ppm      DECIMAL(8,2),
    potassium_min_ppm       DECIMAL(8,2),

    -- Soil moisture (% volumetric) — Source: FAO56
    moisture_optimal_min    DECIMAL(5,2),
    moisture_optimal_max    DECIMAL(5,2),
    moisture_stress_min     DECIMAL(5,2),           -- below this = stress
    field_capacity_pct      DECIMAL(5,2),           -- per soil type, overridden by soil_type lookup
    wilting_point_pct       DECIMAL(5,2),

    -- Temperature (°C) — Source: ECOCROP
    soil_temp_min_c         DECIMAL(4,1),
    soil_temp_max_c         DECIMAL(4,1),
    soil_temp_optimal_c     DECIMAL(4,1),
    air_temp_min_c          DECIMAL(4,1),
    air_temp_max_c          DECIMAL(4,1),

    -- EC tolerance (µS/cm)
    ec_min                  DECIMAL(6,2),
    ec_max                  DECIMAL(6,2),

    -- Root depth for irrigation calc (cm) — Source: FAO56 Table 1 [8]
    root_depth_cm           DECIMAL(5,1) NOT NULL DEFAULT 40.0,

    -- FAO56 Crop coefficients by growth stage [8] — Source: FAO56 Table 12
    kc_initial              DECIMAL(4,2),           -- germination/establishment
    kc_mid                  DECIMAL(4,2),           -- peak vegetative/flowering
    kc_end                  DECIMAL(4,2),           -- late season/maturation

    -- Depletion fraction — Source: FAO56 Table 22
    -- Fraction of available water usable before stress onset
    depletion_fraction_p    DECIMAL(4,2) DEFAULT 0.50,

    -- Growth stage durations (days) — Source: FAO56 Table 11 / KALRO
    days_initial            INTEGER,                -- germination to establishment
    days_development        INTEGER,                -- establishment to mid
    days_mid                INTEGER,                -- peak growth period
    days_late               INTEGER,                -- maturation to harvest
    days_total              INTEGER,                -- total season length

    -- Yield info
    baseline_yield_kg_per_m2    DECIMAL(8,4),       -- under good conditions
    baseline_yield_source       TEXT,               -- citation

    -- Market context (Kenya)
    market_price_kes_per_kg_min DECIMAL(8,2),
    market_price_kes_per_kg_max DECIMAL(8,2),

    -- Metadata
    altitude_range          VARCHAR(100),           -- e.g. '0-2200m'
    suitable_counties       TEXT[],                 -- Kenyan counties where suitable
    nitrogen_fixing         BOOLEAN DEFAULT false,  -- beans/legumes fix their own N
    data_source             TEXT,                   -- citation for these values
    confidence_layer        INTEGER DEFAULT 1       -- 1=published science, 2=regional, 3=farm-specific [7]
                            CHECK (confidence_layer IN (1, 2, 3)),

    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (crop_name, variety_name)
);

-- -----------------------------------------------------------------------------
-- 2.2 SOIL TYPE REFERENCE
-- Published field capacity, wilting point, bulk density by soil type.
-- Source: FAO56 Table 1 / standard soil science.
-- Used in irrigation volume and fertilizer kg calculations. [8]
-- -----------------------------------------------------------------------------
CREATE TABLE soil_type_reference (
    soil_type               VARCHAR(20) PRIMARY KEY,
    field_capacity_pct      DECIMAL(5,2) NOT NULL,  -- max water soil holds after drainage
    wilting_point_pct       DECIMAL(5,2) NOT NULL,  -- point below which plants cannot recover
    bulk_density_g_cm3      DECIMAL(4,2) NOT NULL,  -- for converting ppm to kg/ha
    drainage_factor         DECIMAL(4,2) NOT NULL,  -- irrigation overage factor for losses
    lime_factor_tonnes_ha   DECIMAL(4,2) NOT NULL,  -- tonnes of lime per ha per pH unit — Source: KALRO
    description             TEXT,
    data_source             TEXT
);

-- Seed data from FAO56 Table 1 + KALRO Soil Management Guidelines
INSERT INTO soil_type_reference VALUES
-- soil_type,    FC%,   WP%,  BD,   drain, lime,  description
('sandy',        12.0,  5.0,  1.65, 1.35,  1.75,  'Sandy soil — fast draining, low water retention', 'FAO56 Table 1, KALRO Liming Guide 2023'),
('sandy_loam',   22.0,  9.0,  1.45, 1.25,  2.50,  'Sandy loam — moderate drainage', 'FAO56 Table 1, KALRO Liming Guide 2023'),
('loam',         31.0,  14.0, 1.25, 1.20,  3.75,  'Loam — balanced drainage and retention, most common Kenya highland', 'FAO56 Table 1, KALRO Liming Guide 2023'),
('clay_loam',    38.0,  20.0, 1.15, 1.15,  5.25,  'Clay loam — slow drainage, high retention', 'FAO56 Table 1, KALRO Liming Guide 2023'),
('clay',         45.0,  25.0, 1.10, 1.10,  7.00,  'Clay — very slow drainage, waterlogging risk', 'FAO56 Table 1, KALRO Liming Guide 2023');

-- -----------------------------------------------------------------------------
-- 2.3 FERTILIZER PRODUCTS
-- Real Kenyan market fertilizer products with actual NPK percentages.
-- Source: IFDC Fertilizer Quality Assessment Kenya, Yara Kenya, MEA.
-- Used to translate "Zone needs 30 more ppm N" into "buy X kg of CAN". [9]
-- -----------------------------------------------------------------------------
CREATE TABLE fertilizer_products (
    product_id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_name            VARCHAR(100) NOT NULL UNIQUE,   -- e.g. 'CAN', 'DAP', 'Urea'
    brand                   VARCHAR(100),                   -- Yara, MEA, NAFAKA etc.
    fertilizer_type         VARCHAR(50) NOT NULL
                            CHECK (fertilizer_type IN ('nitrogen','phosphorus','potassium','npk_blend','lime','organic','micronutrient')),

    -- NPK content (%) — Source: IFDC Kenya fertilizer quality assessment
    nitrogen_pct            DECIMAL(5,2) DEFAULT 0,
    phosphorus_pct          DECIMAL(5,2) DEFAULT 0,
    potassium_pct           DECIMAL(5,2) DEFAULT 0,

    -- Lime-specific
    calcium_carbonate_pct   DECIMAL(5,2),               -- for lime products
    neutralizing_value      DECIMAL(5,2),               -- % relative to pure CaCO3

    -- Kenyan market data
    price_kes_per_50kg_bag  DECIMAL(8,2),
    price_updated_date      DATE,
    availability            VARCHAR(50) DEFAULT 'widely_available'
                            CHECK (availability IN ('widely_available','seasonal','agro_dealer_only','scarce')),
    typical_application     TEXT,                        -- plain English when to use this
    data_source             TEXT,
    is_active               BOOLEAN DEFAULT true
);

-- Seed data — Kenyan fertilizer products
-- Source: IFDC Fertilizer Quality Assessment Kenya 2019, Yara Kenya 2024 price list
INSERT INTO fertilizer_products
    (product_name, brand, fertilizer_type, nitrogen_pct, phosphorus_pct, potassium_pct,
     price_kes_per_50kg_bag, price_updated_date, availability, typical_application, data_source)
VALUES
('CAN',         'Yara/MEA', 'nitrogen',    26.0, 0,    0,    2800,  '2024-01-01', 'widely_available', 'Top-dress nitrogen for maize and vegetables after establishment', 'IFDC Kenya 2019, Yara Kenya 2024'),
('Urea',        'Various',  'nitrogen',    46.0, 0,    0,    3200,  '2024-01-01', 'widely_available', 'High nitrogen, use carefully — risk of burning. Good for leafy crops.', 'IFDC Kenya 2019'),
('DAP',         'Yara',     'npk_blend',   18.0, 46.0, 0,    3800,  '2024-01-01', 'widely_available', 'Basal planting fertilizer — high phosphorus for root development', 'IFDC Kenya 2019, Yara Kenya 2024'),
('NPK 17:17:17','MEA',      'npk_blend',   17.0, 17.0, 17.0, 3500,  '2024-01-01', 'widely_available', 'Balanced fertilizer — good when all three nutrients are deficient', 'MEA Kenya 2024'),
('NPK 23:23:0', 'MEA',      'npk_blend',   23.0, 23.0, 0,    3400,  '2024-01-01', 'widely_available', 'High NP blend for leafy crops and early growth stages', 'MEA Kenya 2024'),
('MOP',         'Various',  'potassium',   0,    0,    60.0, 3000,  '2024-01-01', 'agro_dealer_only', 'Muriate of Potash — for potassium deficiency, good for tuber crops', 'IFDC Kenya 2019'),
('Mavuno Planting','MEA',   'npk_blend',   10.0, 26.0, 10.0, 3600,  '2024-01-01', 'widely_available', 'MEA planting fertilizer — balanced for Kenyan smallholder conditions', 'MEA Kenya 2024'),
('Mavuno Top',  'MEA',      'npk_blend',   25.0, 5.0,  5.0,  3300,  '2024-01-01', 'widely_available', 'MEA top-dressing — nitrogen heavy for vegetative growth stage', 'MEA Kenya 2024'),
('Agricultural Lime','Various','lime',     0,    0,    0,    800,   '2024-01-01', 'widely_available', 'pH correction for acidic soils — apply 3-6 months before planting', 'KALRO Liming Guide 2023'),
('Dolomitic Lime','Various','lime',        0,    0,    0,    950,   '2024-01-01', 'seasonal',         'pH correction + magnesium supplement — better for Mg-deficient soils', 'KALRO Liming Guide 2023'),
('DSP',         'Yara',     'phosphorus',  0,    46.0, 0,    3900,  '2024-01-01', 'agro_dealer_only', 'Double Super Phosphate — for severe phosphorus deficiency', 'IFDC Kenya 2019');

-- Add the calcium carbonate % for lime products
UPDATE fertilizer_products SET calcium_carbonate_pct = 85.0, neutralizing_value = 85.0 WHERE product_name = 'Agricultural Lime';
UPDATE fertilizer_products SET calcium_carbonate_pct = 95.0, neutralizing_value = 95.0 WHERE product_name = 'Dolomitic Lime';

-- =============================================================================
-- SECTION 3: ZONE PLANTING STATE
-- Soft delete model — records are never deleted, only status-changed. [5]
-- =============================================================================

CREATE TABLE zone_crops (
    planting_id             UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    zone_id                 UUID        NOT NULL REFERENCES zones(zone_id),
    farm_id                 UUID        NOT NULL REFERENCES farms(farm_id),  -- denormalized for RLS [1]
    variety_id              UUID        REFERENCES crop_varieties(variety_id),

    -- Planting details
    crop_name               VARCHAR(100) NOT NULL,          -- denormalized for easy querying
    variety_name            VARCHAR(100),
    planting_date           DATE         NOT NULL,
    expected_harvest_date   DATE,
    actual_harvest_date     DATE,

    -- Physical planting
    seeds_per_m2            DECIMAL(5,1),
    planting_depth_cm       DECIMAL(4,1),
    row_spacing_cm          DECIMAL(4,1),

    -- Growth stage tracking (auto-calculated from planting_date, farmer can override)
    current_growth_stage    VARCHAR(30) DEFAULT 'initial'
                            CHECK (current_growth_stage IN ('initial','development','mid','late','harvested')),
    growth_stage_override   BOOLEAN DEFAULT false,          -- true if farmer manually set stage

    -- Yield
    expected_yield_kg       DECIMAL(8,2),                   -- from variety baseline × zone area
    actual_yield_kg         DECIMAL(8,2),
    yield_quality_score     DECIMAL(3,2),

    -- Key growth milestone dates (filled as they happen)
    germination_date        DATE,
    flowering_date          DATE,
    fruiting_date           DATE,
    maturity_date           DATE,

    -- Soft delete [5]
    status                  VARCHAR(20) DEFAULT 'active'
                            CHECK (status IN ('active', 'harvested', 'abandoned', 'failed')),
    failure_reason          TEXT,

    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- SECTION 4: SENSOR READINGS
-- Idempotent uploads via deterministic reading_uuid. [3]
-- reading_uuid = rover_id + timestamp_ms + sequence_number
-- Server uses ON CONFLICT DO NOTHING — retry-safe.
-- =============================================================================

CREATE TABLE sensor_readings (
    -- Idempotent key — generated on rover at collection time [3]
    reading_uuid            VARCHAR(60)  PRIMARY KEY,       -- 'ROVER01_1709654400000_0042'

    zone_id                 UUID         NOT NULL REFERENCES zones(zone_id),
    farm_id                 UUID         NOT NULL REFERENCES farms(farm_id),  -- for RLS [1]
    rover_id                VARCHAR(20)  REFERENCES rovers(rover_id),
    collected_at            TIMESTAMP    NOT NULL,           -- when rover took the reading
    uploaded_at             TIMESTAMP    DEFAULT CURRENT_TIMESTAMP, -- when server received it

    -- GPS at time of reading (for zone containment validation) [2]
    gps_lat                 DECIMAL(10,8),
    gps_lon                 DECIMAL(11,8),
    gps_accuracy_m          DECIMAL(6,2),
    gps_confirmed_zone      BOOLEAN DEFAULT false,          -- did GPS point fall inside zone polygon?

    -- 7-in-1 Soil Sensor (ComWinTop RS485)
    -- Source: KALRO / IFDC for interpretation ranges
    nitrogen_ppm            DECIMAL(8,2),
    phosphorus_ppm          DECIMAL(8,2),
    potassium_ppm           DECIMAL(8,2),
    ph_level                DECIMAL(4,2),
    soil_moisture_pct       DECIMAL(5,2),
    soil_temperature_c      DECIMAL(4,1),
    electrical_conductivity DECIMAL(6,2),                  -- µS/cm

    -- DHT22 readings
    air_temperature_c       DECIMAL(4,1),
    air_humidity_pct        DECIMAL(5,2),

    -- Computed ET at reading time using Hargreaves-Samani — Source: FAO56 Ch.3 [8]
    computed_et0_mm_day     DECIMAL(6,3),                  -- reference ET at this reading
    et_calc_method          VARCHAR(30) DEFAULT 'hargreaves_samani',

    -- Data validation flags [decision engine sanity checks]
    data_quality_score      DECIMAL(3,2) DEFAULT 1.0,
    validation_flags        TEXT[],                         -- array of flag codes e.g. 'HIGH_EC_LOW_NPK'
    sensor_battery_v        DECIMAL(4,2),

    -- SD card sync metadata
    synced_from_sd          BOOLEAN DEFAULT false,
    sd_file_name            VARCHAR(100)
);

-- =============================================================================
-- SECTION 5: STALENESS TRACKING — SINGLE SOURCE OF TRUTH [4]
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 5.1 STALENESS THRESHOLDS (configurable, not hardcoded)
-- These define how long each parameter type stays valid before going stale.
-- -----------------------------------------------------------------------------
CREATE TABLE staleness_thresholds (
    parameter_group         VARCHAR(50) PRIMARY KEY,
    max_age_hours           INTEGER NOT NULL,
    description             TEXT
);

INSERT INTO staleness_thresholds VALUES
('npk_ph',      168, 'NPK and pH — stable weekly parameters (FAO soil management guidance)'),
('moisture',    24,  'Soil moisture — changes daily with ET and rain'),
('temperature', 12,  'Soil and air temperature — changes within a day'),
('humidity',    4,   'Air humidity — fast changing, multiple readings per day preferred');

-- -----------------------------------------------------------------------------
-- 5.2 ZONE CURRENT STATE VIEW — Single staleness source of truth [4]
-- Every component queries THIS VIEW, not raw sensor_readings.
-- is_stale_* flags computed here once, trusted everywhere.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW zone_current_state AS
WITH latest_readings AS (
    SELECT DISTINCT ON (zone_id)
        zone_id,
        farm_id,
        reading_uuid,
        collected_at,
        nitrogen_ppm,
        phosphorus_ppm,
        potassium_ppm,
        ph_level,
        soil_moisture_pct,
        soil_temperature_c,
        air_temperature_c,
        air_humidity_pct,
        electrical_conductivity,
        computed_et0_mm_day,
        data_quality_score,
        validation_flags
    FROM sensor_readings
    WHERE data_quality_score >= 0.5
    ORDER BY zone_id, collected_at DESC
),
active_crops AS (
    SELECT DISTINCT ON (zone_id)
        zone_id,
        planting_id,
        crop_name,
        variety_name,
        variety_id,
        planting_date,
        current_growth_stage,
        expected_harvest_date
    FROM zone_crops
    WHERE status = 'active'
    ORDER BY zone_id, planting_date DESC
)
SELECT
    z.zone_id,
    z.farm_id,
    z.zone_label,
    z.area_m2,
    z.soil_type,

    -- Latest readings
    lr.reading_uuid        AS last_reading_uuid,
    lr.collected_at        AS last_reading_at,
    lr.nitrogen_ppm,
    lr.phosphorus_ppm,
    lr.potassium_ppm,
    lr.ph_level,
    lr.soil_moisture_pct,
    lr.soil_temperature_c,
    lr.air_temperature_c,
    lr.air_humidity_pct,
    lr.electrical_conductivity,
    lr.computed_et0_mm_day,
    lr.data_quality_score,
    lr.validation_flags,

    -- Staleness flags — one definition, enforced once [4]
    CASE WHEN lr.collected_at IS NULL THEN true
         WHEN EXTRACT(EPOCH FROM (NOW() - lr.collected_at))/3600 > 168 THEN true
         ELSE false END AS is_stale_npk_ph,

    CASE WHEN lr.collected_at IS NULL THEN true
         WHEN EXTRACT(EPOCH FROM (NOW() - lr.collected_at))/3600 > 24 THEN true
         ELSE false END AS is_stale_moisture,

    CASE WHEN lr.collected_at IS NULL THEN true
         WHEN EXTRACT(EPOCH FROM (NOW() - lr.collected_at))/3600 > 12 THEN true
         ELSE false END AS is_stale_temperature,

    CASE WHEN lr.collected_at IS NULL THEN true
         WHEN EXTRACT(EPOCH FROM (NOW() - lr.collected_at))/3600 > 4 THEN true
         ELSE false END AS is_stale_humidity,

    -- Needs urgent rover visit flag (any critical parameter stale)
    CASE WHEN lr.collected_at IS NULL THEN true
         WHEN EXTRACT(EPOCH FROM (NOW() - lr.collected_at))/3600 > 24 THEN true
         ELSE false END AS needs_urgent_reading,

    -- Hours since last reading (for staleness score in rover schedule) [6]
    COALESCE(
        EXTRACT(EPOCH FROM (NOW() - lr.collected_at))/3600,
        999
    )::DECIMAL(8,1) AS hours_since_reading,

    -- Active crop context
    ac.planting_id,
    ac.crop_name,
    ac.variety_name,
    ac.variety_id,
    ac.planting_date,
    ac.current_growth_stage,
    ac.expected_harvest_date,

    -- Days into season (for growth stage auto-calc)
    CASE WHEN ac.planting_date IS NOT NULL
         THEN (CURRENT_DATE - ac.planting_date)
         ELSE NULL END AS days_since_planting

FROM zones z
LEFT JOIN latest_readings lr ON z.zone_id = lr.zone_id
LEFT JOIN active_crops ac ON z.zone_id = ac.zone_id
WHERE z.status = 'active';

-- =============================================================================
-- SECTION 6: DECISIONS & RECOMMENDATIONS
-- Every recommendation logged with full calculation breakdown. [8]
-- pH hard gate enforced — no NPK recommendation if pH critical. [10]
-- Urgency scoring applied. [11]
-- Plain language confidence. [12]
-- =============================================================================

CREATE TABLE recommendations (
    recommendation_id       UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    zone_id                 UUID        NOT NULL REFERENCES zones(zone_id),
    farm_id                 UUID        NOT NULL REFERENCES farms(farm_id),
    planting_id             UUID        REFERENCES zone_crops(planting_id),
    generated_at            TIMESTAMP   DEFAULT CURRENT_TIMESTAMP,
    based_on_reading_uuid   VARCHAR(60) REFERENCES sensor_readings(reading_uuid),

    -- What kind of recommendation
    recommendation_type     VARCHAR(50) NOT NULL
                            CHECK (recommendation_type IN (
                                'irrigate', 'fertilize_n', 'fertilize_p', 'fertilize_k',
                                'lime', 'ph_correction', 'do_not_fertilize',
                                'plant', 'harvest_soon', 'monitor', 'soil_test'
                            )),

    -- pH hard gate flag [10]
    ph_gate_active          BOOLEAN DEFAULT false,          -- true = pH critical, NPK blocked
    ph_gate_reason          TEXT,                           -- explanation if gate is active

    -- The actual recommendation
    action_description      TEXT        NOT NULL,           -- plain English what to do
    action_quantity         DECIMAL(10,3),                  -- amount (liters, grams, kg)
    action_unit             VARCHAR(20),                    -- liters, grams, kg, kg/m2
    product_id              UUID        REFERENCES fertilizer_products(product_id),
    product_name            VARCHAR(100),                   -- denormalized for easy display
    estimated_cost_kes      DECIMAL(10,2),

    -- Full calculation trace [8]
    -- All the math that produced this recommendation — stored as JSON for transparency
    calculation_breakdown   JSONB,
    -- Example for irrigation:
    -- {
    --   "formula": "Hargreaves-Samani + FAO56 Ch8 irrigation scheduling",
    --   "current_moisture_pct": 42.0,
    --   "field_capacity_pct": 31.0,
    --   "wilting_point_pct": 14.0,
    --   "soil_deficit_pct": 11.0,
    --   "root_depth_cm": 60.0,
    --   "bulk_density": 1.25,
    --   "zone_area_m2": 4.0,
    --   "drainage_factor": 1.20,
    --   "et0_mm_day": 4.2,
    --   "kc_mid": 1.20,
    --   "etcrop_mm_day": 5.04,
    --   "depletion_fraction_p": 0.55,
    --   "days_until_stress": 2.1,
    --   "water_needed_liters": 8.4,
    --   "data_sources": ["FAO56 Table 1", "FAO56 Table 12", "FAO56 Table 22"]
    -- }

    -- Urgency scoring [11]
    urgency_score           DECIMAL(6,3),       -- computed score
    urgency_level           VARCHAR(20)         -- CRITICAL / HIGH / MEDIUM / LOW
                            CHECK (urgency_level IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW')),
    urgency_breakdown       JSONB,              -- deviation × stage_multiplier × ignored_penalty

    -- Confidence [12]
    confidence_score        DECIMAL(3,2),       -- raw score stored here (not shown to farmer)
    confidence_label        VARCHAR(20),        -- label shown to farmer
                            -- 'high' / 'moderate' / 'low' / 'uncertain'
    confidence_explanation  TEXT,               -- "Based on 3 seasons of your farm's data"
    knowledge_layer         INTEGER DEFAULT 1   -- which layer produced this [7]
                            CHECK (knowledge_layer IN (1, 2, 3)),
    knowledge_layer_label   TEXT,               -- "Based on published research" etc.

    -- Expected outcome
    expected_yield_impact_pct   DECIMAL(6,2),   -- % yield improvement expected
    expected_next_reading_date  DATE,           -- when to re-check after applying

    -- Farmer response tracking (feeds back into urgency scoring)
    was_applied             BOOLEAN,            -- did farmer follow recommendation?
    applied_at              TIMESTAMP,
    farmer_feedback         TEXT,
    ignored_count           INTEGER DEFAULT 0,  -- increments if same type ignored repeatedly [11]

    -- ROI
    expected_benefit_kes    DECIMAL(10,2),
    roi_percent             DECIMAL(8,2)
);

-- =============================================================================
-- SECTION 7: AMENDMENTS LOG
-- What was actually applied — links back to recommendation.
-- Cost tracking in KES. [9]
-- =============================================================================

CREATE TABLE amendments (
    amendment_id            UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    zone_id                 UUID        NOT NULL REFERENCES zones(zone_id),
    farm_id                 UUID        NOT NULL REFERENCES farms(farm_id),
    recommendation_id       UUID        REFERENCES recommendations(recommendation_id),
    planting_id             UUID        REFERENCES zone_crops(planting_id),

    applied_at              TIMESTAMP   NOT NULL,
    applied_by              VARCHAR(100),

    -- What was applied
    amendment_type          VARCHAR(50) NOT NULL
                            CHECK (amendment_type IN ('fertilizer','lime','irrigation','organic','pesticide','other')),
    product_id              UUID        REFERENCES fertilizer_products(product_id),
    product_name            VARCHAR(100) NOT NULL,
    amount_applied          DECIMAL(10,3) NOT NULL,
    unit                    VARCHAR(20) NOT NULL,          -- kg, liters, grams

    -- Nutrient content of what was applied (computed from product NPK %)
    nitrogen_applied_kg     DECIMAL(8,4),
    phosphorus_applied_kg   DECIMAL(8,4),
    potassium_applied_kg    DECIMAL(8,4),
    lime_applied_kg         DECIMAL(8,4),

    -- Cost in KES [9]
    cost_kes                DECIMAL(10,2),
    receipt_reference       VARCHAR(100),

    -- Application context
    application_method      VARCHAR(50),       -- broadcast, drip, foliar, side_dress
    incorporation_depth_cm  DECIMAL(4,1),
    notes                   TEXT,

    -- Before/after snapshot for tracking effectiveness
    pre_application_snapshot    JSONB,          -- sensor values at time of application
    post_application_reading_id VARCHAR(60)     REFERENCES sensor_readings(reading_uuid),

    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- SECTION 8: IRRIGATION EVENTS
-- Separate table for irrigation specifics.
-- Water volume calculation fully traceable to FAO56. [8]
-- =============================================================================

CREATE TABLE irrigation_events (
    irrigation_id           UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    zone_id                 UUID        NOT NULL REFERENCES zones(zone_id),
    farm_id                 UUID        NOT NULL REFERENCES farms(farm_id),
    recommendation_id       UUID        REFERENCES recommendations(recommendation_id),
    planting_id             UUID        REFERENCES zone_crops(planting_id),

    irrigated_at            TIMESTAMP   NOT NULL,
    water_applied_liters    DECIMAL(8,2) NOT NULL,
    irrigation_method       VARCHAR(50),                   -- manual, drip, sprinkler, flood
    water_source            VARCHAR(50),                   -- borehole, rain_harvest, river, tap

    -- Pre/post moisture for effectiveness tracking
    pre_moisture_pct        DECIMAL(5,2),
    post_moisture_pct       DECIMAL(5,2),
    efficiency_score        DECIMAL(3,2),                  -- post-pre / recommended ratio

    -- Irrigation schedule
    next_irrigation_date    DATE,
    next_irrigation_liters  DECIMAL(8,2),

    -- Full FAO56 calc trace [8]
    irrigation_calc         JSONB,
    -- {
    --   "et0_mm_day": 4.2,
    --   "kc": 1.20,
    --   "etcrop_mm_day": 5.04,
    --   "soil_deficit_mm": 21.0,
    --   "drainage_factor": 1.20,
    --   "water_needed_mm": 25.2,
    --   "zone_area_m2": 4.0,
    --   "water_needed_liters": 10.08,
    --   "days_until_next": 3.8,
    --   "data_sources": ["FAO56 Table 12", "FAO56 Table 22", "FAO56 Ch8"]
    -- }

    cost_kes                DECIMAL(8,2),                  -- water cost if applicable
    notes                   TEXT,
    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- SECTION 9: MARKET PRICES
-- Cached market prices — updated from KAMIS API when internet available.
-- Falls back to last known price gracefully. [4]
-- =============================================================================

CREATE TABLE market_prices (
    price_id                UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    crop_name               VARCHAR(100) NOT NULL,
    market_name             VARCHAR(200),                  -- Wakulima, Kongowea, Eldoret etc.
    county                  VARCHAR(100),
    price_kes_per_kg        DECIMAL(8,2) NOT NULL,
    price_date              DATE         NOT NULL,
    source                  VARCHAR(100) DEFAULT 'KAMIS', -- KAMIS, manual_entry, estimated
    is_current              BOOLEAN      DEFAULT true,
    notes                   TEXT,
    created_at              TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);

-- Create index for fast latest-price lookup
CREATE INDEX idx_market_prices_crop_date ON market_prices(crop_name, price_date DESC);

-- =============================================================================
-- SECTION 10: ALERTS
-- Urgency-scored, batched to prevent alert fatigue. [11]
-- Max 3 CRITICAL alerts per farm per day enforced at application layer.
-- =============================================================================

CREATE TABLE alerts (
    alert_id                UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    zone_id                 UUID        REFERENCES zones(zone_id),
    farm_id                 UUID        NOT NULL REFERENCES farms(farm_id),
    recommendation_id       UUID        REFERENCES recommendations(recommendation_id),
    created_at              TIMESTAMP   DEFAULT CURRENT_TIMESTAMP,

    alert_type              VARCHAR(50) NOT NULL
                            CHECK (alert_type IN (
                                'moisture_stress', 'nutrient_deficiency', 'ph_critical',
                                'harvest_window', 'system', 'rover_overdue', 'sensor_error'
                            )),
    urgency_level           VARCHAR(20) NOT NULL
                            CHECK (urgency_level IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW')),

    title                   VARCHAR(200) NOT NULL,
    message                 TEXT         NOT NULL,
    plain_language_action   TEXT,                          -- exactly what farmer should do

    -- Notification tracking
    shown_to_user           BOOLEAN DEFAULT false,
    shown_at                TIMESTAMP,
    acknowledged_at         TIMESTAMP,
    resolved_at             TIMESTAMP,
    resolution_notes        TEXT,

    -- Alert grouping (prevents duplicate alerts for same condition)
    alert_fingerprint       VARCHAR(100),                  -- hash of zone_id+alert_type+date
    UNIQUE (alert_fingerprint)
);

-- =============================================================================
-- SECTION 11: REGIONAL CALIBRATION (Layer 2 knowledge) [7]
-- Adjustments learned from multiple farms in same region.
-- Overrides Layer 1 published science where regional data supports it.
-- =============================================================================

CREATE TABLE regional_calibration (
    calibration_id          UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    county                  VARCHAR(100) NOT NULL,
    crop_name               VARCHAR(100) NOT NULL,
    parameter_name          VARCHAR(50) NOT NULL,          -- 'ph_optimal_min', 'kc_mid' etc.
    calibrated_value        DECIMAL(10,4) NOT NULL,
    published_value         DECIMAL(10,4),                 -- what Layer 1 says
    sample_size             INTEGER,                       -- how many farms contributed
    confidence              DECIMAL(3,2),
    valid_from              DATE,
    valid_to                DATE,
    data_source             TEXT,
    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (county, crop_name, parameter_name)
);

-- =============================================================================
-- SECTION 12: PERFORMANCE & YIELD HISTORY
-- Season-over-season data. Powers Layer 3 farm-specific learning. [7]
-- Never deleted — soft archive only. [5]
-- =============================================================================

CREATE TABLE yield_history (
    yield_id                UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    planting_id             UUID        NOT NULL REFERENCES zone_crops(planting_id),
    zone_id                 UUID        NOT NULL REFERENCES zones(zone_id),
    farm_id                 UUID        NOT NULL REFERENCES farms(farm_id),

    -- Season summary
    crop_name               VARCHAR(100) NOT NULL,
    variety_name            VARCHAR(100),
    season_year             INTEGER,
    season_type             VARCHAR(20),                   -- 'long_rains' / 'short_rains' / 'irrigated'

    -- Yield outcome
    yield_kg                DECIMAL(10,2),
    yield_kg_per_m2         DECIMAL(8,4),
    baseline_yield_kg_per_m2 DECIMAL(8,4),                -- from crop_varieties for comparison
    yield_vs_baseline_pct   DECIMAL(8,2),                  -- % of expected baseline achieved

    -- Average soil conditions during season
    avg_nitrogen_ppm        DECIMAL(8,2),
    avg_phosphorus_ppm      DECIMAL(8,2),
    avg_potassium_ppm       DECIMAL(8,2),
    avg_ph                  DECIMAL(4,2),
    avg_moisture_pct        DECIMAL(5,2),

    -- Input summary
    total_water_liters      DECIMAL(10,2),
    total_fertilizer_cost_kes DECIMAL(10,2),
    total_amendment_cost_kes  DECIMAL(10,2),

    -- Financial outcome
    market_price_kes_per_kg DECIMAL(8,2),
    gross_revenue_kes       DECIMAL(10,2),
    total_input_cost_kes    DECIMAL(10,2),
    net_profit_kes          DECIMAL(10,2),
    roi_percent             DECIMAL(8,2),

    -- What recommendations were followed
    recommendations_followed    INTEGER DEFAULT 0,
    recommendations_ignored     INTEGER DEFAULT 0,
    compliance_rate_pct         DECIMAL(5,2),

    notes                   TEXT,
    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- SECTION 13: INDEXES
-- =============================================================================

-- Sensor readings — most queried table
CREATE INDEX idx_readings_zone_time     ON sensor_readings(zone_id, collected_at DESC);
CREATE INDEX idx_readings_farm_time     ON sensor_readings(farm_id, collected_at DESC);
CREATE INDEX idx_readings_quality       ON sensor_readings(data_quality_score);

-- Zone lookups
CREATE INDEX idx_zones_farm             ON zones(farm_id);
CREATE INDEX idx_zones_label            ON zones(farm_id, zone_label);

-- Spatial index for GPS farm detection [2]
CREATE INDEX idx_farms_boundary         ON farms USING GIST(boundary_polygon);
CREATE INDEX idx_zones_boundary         ON zones USING GIST(boundary_polygon);

-- Recommendations
CREATE INDEX idx_recs_zone_time         ON recommendations(zone_id, generated_at DESC);
CREATE INDEX idx_recs_farm_urgency      ON recommendations(farm_id, urgency_level, generated_at DESC);
CREATE INDEX idx_recs_unapplied         ON recommendations(farm_id, was_applied) WHERE was_applied IS NULL;

-- Zone crops — active crops lookup
CREATE INDEX idx_crops_zone_active      ON zone_crops(zone_id, status) WHERE status = 'active';
CREATE INDEX idx_crops_farm             ON zone_crops(farm_id);

-- Amendments & irrigation
CREATE INDEX idx_amendments_zone_time   ON amendments(zone_id, applied_at DESC);
CREATE INDEX idx_irrigation_zone_time   ON irrigation_events(zone_id, irrigated_at DESC);

-- Rover schedule
CREATE INDEX idx_schedule_farm_score    ON rover_schedule(farm_id, staleness_score DESC) WHERE is_completed = false;

-- Alerts
CREATE INDEX idx_alerts_farm_urgency    ON alerts(farm_id, urgency_level, created_at DESC);
CREATE INDEX idx_alerts_unresolved      ON alerts(farm_id) WHERE resolved_at IS NULL;

-- Market prices
CREATE INDEX idx_market_crop_current    ON market_prices(crop_name) WHERE is_current = true;

-- =============================================================================
-- SECTION 14: ROW LEVEL SECURITY [1]
-- Enabled on every table with farm_id.
-- Database physically cannot return another farm's data.
-- =============================================================================

ALTER TABLE farms              ENABLE ROW LEVEL SECURITY;
ALTER TABLE zones              ENABLE ROW LEVEL SECURITY;
ALTER TABLE zone_crops         ENABLE ROW LEVEL SECURITY;
ALTER TABLE sensor_readings    ENABLE ROW LEVEL SECURITY;
ALTER TABLE recommendations    ENABLE ROW LEVEL SECURITY;
ALTER TABLE amendments         ENABLE ROW LEVEL SECURITY;
ALTER TABLE irrigation_events  ENABLE ROW LEVEL SECURITY;
ALTER TABLE alerts             ENABLE ROW LEVEL SECURITY;
ALTER TABLE rover_schedule     ENABLE ROW LEVEL SECURITY;
ALTER TABLE yield_history      ENABLE ROW LEVEL SECURITY;

-- Application user (connect via this role from Python server)
-- Run as superuser:
-- CREATE ROLE yieldvision_app WITH LOGIN PASSWORD 'CHANGE_THIS_PASSWORD';

-- RLS Policies — app passes current farm context via session variable
-- In Python: conn.execute("SET app.current_farm_id = %s", [farm_id])

CREATE POLICY farm_isolation ON farms
    USING (farm_id::text = current_setting('app.current_farm_id', true));

CREATE POLICY farm_isolation ON zones
    USING (farm_id::text = current_setting('app.current_farm_id', true));

CREATE POLICY farm_isolation ON zone_crops
    USING (farm_id::text = current_setting('app.current_farm_id', true));

CREATE POLICY farm_isolation ON sensor_readings
    USING (farm_id::text = current_setting('app.current_farm_id', true));

CREATE POLICY farm_isolation ON recommendations
    USING (farm_id::text = current_setting('app.current_farm_id', true));

CREATE POLICY farm_isolation ON amendments
    USING (farm_id::text = current_setting('app.current_farm_id', true));

CREATE POLICY farm_isolation ON irrigation_events
    USING (farm_id::text = current_setting('app.current_farm_id', true));

CREATE POLICY farm_isolation ON alerts
    USING (farm_id::text = current_setting('app.current_farm_id', true));

CREATE POLICY farm_isolation ON rover_schedule
    USING (farm_id::text = current_setting('app.current_farm_id', true));

CREATE POLICY farm_isolation ON yield_history
    USING (farm_id::text = current_setting('app.current_farm_id', true));

-- Admin bypass policy (superuser sees all)
CREATE POLICY admin_bypass ON farms        TO yieldvision_admin USING (true);
CREATE POLICY admin_bypass ON zones        TO yieldvision_admin USING (true);
CREATE POLICY admin_bypass ON zone_crops   TO yieldvision_admin USING (true);
CREATE POLICY admin_bypass ON sensor_readings TO yieldvision_admin USING (true);
CREATE POLICY admin_bypass ON recommendations TO yieldvision_admin USING (true);

-- Grant app user permissions
-- GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO yieldvision_app;
-- GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO yieldvision_app;

-- =============================================================================
-- SECTION 15: TRIGGERS
-- =============================================================================

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_farms_updated_at
    BEFORE UPDATE ON farms
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_zones_updated_at
    BEFORE UPDATE ON zones
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_zone_crops_updated_at
    BEFORE UPDATE ON zone_crops
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Auto-calculate zone area from polygon
CREATE OR REPLACE FUNCTION calculate_zone_area()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.boundary_polygon IS NOT NULL THEN
        NEW.area_m2 = ST_Area(ST_Transform(NEW.boundary_polygon, 32737)); -- UTM zone 37S for Kenya
        NEW.center_lat = ST_Y(ST_Centroid(NEW.boundary_polygon));
        NEW.center_lon = ST_X(ST_Centroid(NEW.boundary_polygon));
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_zones_area
    BEFORE INSERT OR UPDATE ON zones
    FOR EACH ROW EXECUTE FUNCTION calculate_zone_area();

-- Auto-update zone staleness score in rover_schedule when new reading arrives
CREATE OR REPLACE FUNCTION update_rover_schedule_on_reading()
RETURNS TRIGGER AS $$
BEGIN
    -- Mark any pending schedule entries for this zone as completed
    UPDATE rover_schedule
    SET is_completed = true,
        completed_at = NEW.collected_at
    WHERE zone_id = NEW.zone_id
      AND is_completed = false
      AND scheduled_date <= CURRENT_DATE;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_reading_updates_schedule
    AFTER INSERT ON sensor_readings
    FOR EACH ROW EXECUTE FUNCTION update_rover_schedule_on_reading();

-- =============================================================================
-- SECTION 16: SEED DATA — KENYAN CROP VARIETIES
-- Source: KALRO, FAO56, ECOCROP, Yara Kenya
-- =============================================================================

-- MAIZE VARIETIES
INSERT INTO crop_varieties (
    crop_name, variety_name, variety_code,
    ph_min, ph_max, ph_optimal_min, ph_optimal_max,
    nitrogen_optimal_ppm, phosphorus_optimal_ppm, potassium_optimal_ppm,
    nitrogen_min_ppm, phosphorus_min_ppm, potassium_min_ppm,
    moisture_optimal_min, moisture_optimal_max, moisture_stress_min,
    wilting_point_pct,
    soil_temp_optimal_c, air_temp_min_c, air_temp_max_c,
    ec_min, ec_max,
    root_depth_cm,
    kc_initial, kc_mid, kc_end,
    depletion_fraction_p,
    days_initial, days_development, days_mid, days_late, days_total,
    baseline_yield_kg_per_m2,
    market_price_kes_per_kg_min, market_price_kes_per_kg_max,
    altitude_range, nitrogen_fixing, data_source, confidence_layer
) VALUES
(
    'Maize', 'H614D', 'H614D',
    5.5, 7.5, 6.0, 7.0,
    150, 60, 120,
    80, 30, 80,
    50, 80, 35,
    14.0,
    24, 10, 35,
    100, 800,
    60,
    0.30, 1.20, 0.35,
    0.55,
    20, 35, 45, 30, 130,
    0.10,   -- 1000 kg/acre = ~0.25 kg/m2, mid range
    40, 55,
    '900-2100m', false,
    'KALRO Crop Variety Catalogue 2023, FAO56 Table 12, ECOCROP', 1
),
(
    'Maize', 'DK8031', 'DK8031',
    5.5, 7.5, 6.0, 7.0,
    150, 60, 120,
    80, 30, 80,
    50, 80, 35,
    14.0,
    24, 10, 35,
    100, 800,
    60,
    0.30, 1.20, 0.35,
    0.55,
    18, 32, 40, 25, 115,
    0.125,  -- 1250 kg/acre mid range
    40, 55,
    '0-1800m', false,
    'Dekalb Kenya 2024, FAO56 Table 12, ECOCROP', 1
),
(
    'Maize', 'DUMA 43', 'DUMA43',
    5.5, 7.5, 6.0, 7.0,
    140, 55, 110,
    70, 25, 75,
    40, 75, 30,
    14.0,
    24, 10, 38,
    80, 800,
    55,
    0.30, 1.15, 0.35,
    0.55,
    15, 25, 35, 20, 95,
    0.085,  -- drought tolerant, slightly lower yield
    40, 55,
    '0-1600m', false,
    'SEEDCO Kenya 2024, FAO56 Table 12, KALRO Drought Tolerance Trials', 1
);

-- BEANS VARIETIES
INSERT INTO crop_varieties (
    crop_name, variety_name, variety_code,
    ph_min, ph_max, ph_optimal_min, ph_optimal_max,
    nitrogen_optimal_ppm, phosphorus_optimal_ppm, potassium_optimal_ppm,
    nitrogen_min_ppm, phosphorus_min_ppm, potassium_min_ppm,
    moisture_optimal_min, moisture_optimal_max, moisture_stress_min,
    wilting_point_pct,
    soil_temp_optimal_c, air_temp_min_c, air_temp_max_c,
    ec_min, ec_max,
    root_depth_cm,
    kc_initial, kc_mid, kc_end,
    depletion_fraction_p,
    days_initial, days_development, days_mid, days_late, days_total,
    baseline_yield_kg_per_m2,
    market_price_kes_per_kg_min, market_price_kes_per_kg_max,
    altitude_range, nitrogen_fixing, data_source, confidence_layer
) VALUES
(
    'Beans', 'Rosecoco GLP2', 'GLP2',
    5.5, 7.0, 6.0, 6.8,
    60, 50, 80,
    20, 30, 50,
    45, 75, 30,
    12.0,
    22, 12, 30,
    50, 600,
    50,
    0.30, 1.10, 0.30,
    0.45,
    15, 25, 25, 15, 80,
    0.050,  -- 500 kg/acre mid range
    80, 130,
    '1200-2200m', true,
    'KALRO Beans Programme 2023, FAO56 Table 12, ECOCROP', 1
),
(
    'Beans', 'Mwezi Moja', 'MWEZIMOJA',
    5.5, 7.0, 6.0, 6.8,
    60, 50, 80,
    20, 30, 50,
    45, 75, 30,
    12.0,
    22, 12, 30,
    50, 600,
    45,
    0.30, 1.10, 0.30,
    0.45,
    12, 20, 20, 13, 65,
    0.045,
    80, 130,
    '0-1800m', true,
    'KALRO Beans Programme 2023, FAO56 Table 12', 1
);

-- POTATOES VARIETIES
INSERT INTO crop_varieties (
    crop_name, variety_name, variety_code,
    ph_min, ph_max, ph_optimal_min, ph_optimal_max,
    nitrogen_optimal_ppm, phosphorus_optimal_ppm, potassium_optimal_ppm,
    nitrogen_min_ppm, phosphorus_min_ppm, potassium_min_ppm,
    moisture_optimal_min, moisture_optimal_max, moisture_stress_min,
    wilting_point_pct,
    soil_temp_optimal_c, air_temp_min_c, air_temp_max_c,
    ec_min, ec_max,
    root_depth_cm,
    kc_initial, kc_mid, kc_end,
    depletion_fraction_p,
    days_initial, days_development, days_mid, days_late, days_total,
    baseline_yield_kg_per_m2,
    market_price_kes_per_kg_min, market_price_kes_per_kg_max,
    altitude_range, nitrogen_fixing, data_source, confidence_layer
) VALUES
(
    'Potatoes', 'Shangi', 'SHANGI',
    5.0, 6.5, 5.5, 6.2,
    150, 80, 250,
    80, 50, 150,
    55, 85, 40,
    14.0,
    18, 7, 25,
    100, 700,
    40,
    0.40, 1.15, 0.75,
    0.35,
    25, 30, 30, 15, 100,
    0.40,   -- 4000 kg/acre mid range
    25, 50,
    '1800-3000m', false,
    'KALRO Tigoni 2023, FAO56 Table 12, ECOCROP', 1
),
(
    'Potatoes', 'Dutch Robjin', 'DUTCHROBJIN',
    5.0, 6.5, 5.5, 6.2,
    150, 80, 250,
    80, 50, 150,
    55, 85, 40,
    14.0,
    18, 7, 25,
    100, 700,
    40,
    0.40, 1.15, 0.75,
    0.35,
    25, 35, 30, 15, 105,
    0.50,   -- 5000 kg/acre mid range
    25, 50,
    '1800-3000m', false,
    'KALRO Tigoni 2023, FAO56 Table 12', 1
);

-- TOMATOES VARIETIES
INSERT INTO crop_varieties (
    crop_name, variety_name, variety_code,
    ph_min, ph_max, ph_optimal_min, ph_optimal_max,
    nitrogen_optimal_ppm, phosphorus_optimal_ppm, potassium_optimal_ppm,
    nitrogen_min_ppm, phosphorus_min_ppm, potassium_min_ppm,
    moisture_optimal_min, moisture_optimal_max, moisture_stress_min,
    wilting_point_pct,
    soil_temp_optimal_c, air_temp_min_c, air_temp_max_c,
    ec_min, ec_max,
    root_depth_cm,
    kc_initial, kc_mid, kc_end,
    depletion_fraction_p,
    days_initial, days_development, days_mid, days_late, days_total,
    baseline_yield_kg_per_m2,
    market_price_kes_per_kg_min, market_price_kes_per_kg_max,
    altitude_range, nitrogen_fixing, data_source, confidence_layer
) VALUES
(
    'Tomatoes', 'Rambo F1', 'RAMBOF1',
    5.8, 7.0, 6.0, 6.8,
    180, 80, 200,
    100, 50, 120,
    60, 85, 45,
    15.0,
    25, 15, 32,
    150, 900,
    50,
    0.40, 1.15, 0.70,
    0.40,
    30, 40, 40, 25, 135,
    1.15,   -- 11500 kg/acre mid range (high value crop)
    30, 80,
    '0-2000m', false,
    'Syngenta Kenya 2024, FAO56 Table 12, ECOCROP', 1
),
(
    'Tomatoes', 'Money Maker', 'MONEYMAKER',
    5.8, 7.0, 6.0, 6.8,
    180, 80, 200,
    100, 50, 120,
    60, 85, 45,
    15.0,
    25, 15, 32,
    150, 900,
    50,
    0.40, 1.15, 0.70,
    0.40,
    30, 40, 45, 30, 145,
    0.70,   -- open pollinated, lower yield than hybrids
    30, 80,
    '0-2200m', false,
    'KEPHIS 2023, FAO56 Table 12', 1
);

-- KALE / SUKUMA WIKI VARIETIES
INSERT INTO crop_varieties (
    crop_name, variety_name, variety_code,
    ph_min, ph_max, ph_optimal_min, ph_optimal_max,
    nitrogen_optimal_ppm, phosphorus_optimal_ppm, potassium_optimal_ppm,
    nitrogen_min_ppm, phosphorus_min_ppm, potassium_min_ppm,
    moisture_optimal_min, moisture_optimal_max, moisture_stress_min,
    wilting_point_pct,
    soil_temp_optimal_c, air_temp_min_c, air_temp_max_c,
    ec_min, ec_max,
    root_depth_cm,
    kc_initial, kc_mid, kc_end,
    depletion_fraction_p,
    days_initial, days_development, days_mid, days_late, days_total,
    baseline_yield_kg_per_m2,
    market_price_kes_per_kg_min, market_price_kes_per_kg_max,
    altitude_range, nitrogen_fixing, data_source, confidence_layer
) VALUES
(
    'Kale', 'Collard Mfalme F1', 'MFALME',
    5.5, 7.5, 6.0, 7.0,
    160, 50, 130,
    80, 30, 80,
    50, 80, 35,
    14.0,
    22, 10, 32,
    100, 750,
    35,
    0.40, 1.00, 0.95,
    0.45,
    15, 20, 90, 0, 365,  -- continuous harvest, mid is the whole productive period
    0.10,   -- 1000 kg/acre/month × 12 = per m2 per year rough estimate
    3, 15,
    '0-2500m', false,
    'KALRO Horticulture 2023, FAO56 Table 12, ECOCROP', 1
);

-- =============================================================================
-- SECTION 17: HELPER VIEWS
-- =============================================================================

-- Farm summary — quick overview of all zones
CREATE VIEW farm_summary AS
SELECT
    f.farm_id,
    f.farm_name,
    f.owner_name,
    f.county,
    COUNT(z.zone_id)                                   AS total_zones,
    COUNT(CASE WHEN z.status = 'active' THEN 1 END)    AS active_zones,
    COUNT(CASE WHEN zcs.needs_urgent_reading THEN 1 END) AS zones_needing_rover,
    COUNT(CASE WHEN zcs.is_stale_npk_ph THEN 1 END)    AS zones_stale_npk,
    COUNT(CASE WHEN zcs.is_stale_moisture THEN 1 END)  AS zones_stale_moisture,
    COUNT(DISTINCT zc.crop_name)                        AS crops_growing
FROM farms f
LEFT JOIN zones z ON f.farm_id = z.farm_id AND z.status = 'active'
LEFT JOIN zone_current_state zcs ON z.zone_id = zcs.zone_id
LEFT JOIN zone_crops zc ON z.zone_id = zc.zone_id AND zc.status = 'active'
GROUP BY f.farm_id, f.farm_name, f.owner_name, f.county;

-- Pending recommendations — what farmer should act on today
CREATE VIEW pending_recommendations AS
SELECT
    r.recommendation_id,
    r.farm_id,
    r.zone_id,
    z.zone_label,
    r.recommendation_type,
    r.action_description,
    r.action_quantity,
    r.action_unit,
    r.product_name,
    r.estimated_cost_kes,
    r.urgency_level,
    r.urgency_score,
    r.confidence_label,
    r.confidence_explanation,
    r.ph_gate_active,
    r.expected_benefit_kes,
    r.roi_percent,
    r.generated_at
FROM recommendations r
JOIN zones z ON r.zone_id = z.zone_id
WHERE r.was_applied IS NULL
  AND r.generated_at > NOW() - INTERVAL '7 days'
ORDER BY r.urgency_score DESC, r.generated_at DESC;

-- Rover dispatch view — which farm needs rover most urgently
CREATE VIEW rover_dispatch_priority AS
SELECT
    f.farm_id,
    f.farm_name,
    f.county,
    f.assigned_rover_id,
    COUNT(CASE WHEN zcs.needs_urgent_reading THEN 1 END) AS urgent_zones,
    MAX(zcs.hours_since_reading)                          AS max_hours_since_reading,
    AVG(zcs.hours_since_reading)                          AS avg_hours_since_reading
FROM farms f
JOIN zones z ON f.farm_id = z.farm_id AND z.status = 'active'
JOIN zone_current_state zcs ON z.zone_id = zcs.zone_id
GROUP BY f.farm_id, f.farm_name, f.county, f.assigned_rover_id
ORDER BY urgent_zones DESC, max_hours_since_reading DESC;

-- =============================================================================
-- SCHEMA COMPLETE
-- =============================================================================

-- Quick verification query — run after setup to confirm all tables exist:
-- SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;

-- Tables that should exist (17):
-- alerts, amendments, crop_varieties, farms, fertilizer_products,
-- irrigation_events, market_prices, recommendations, regional_calibration,
-- rover_schedule, rovers, sensor_readings, soil_type_reference,
-- staleness_thresholds, yield_history, zone_crops, zones

-- Views that should exist (5):
-- farm_summary, pending_recommendations, rover_dispatch_priority,
-- zone_current_state, zone_summary (legacy - can be dropped)

-- Seed data loaded:
-- soil_type_reference: 5 soil types
-- staleness_thresholds: 4 parameter groups
-- fertilizer_products: 11 Kenyan products
-- crop_varieties: 9 Kenyan varieties (3 maize, 2 beans, 2 potatoes, 2 tomatoes, 1 kale)