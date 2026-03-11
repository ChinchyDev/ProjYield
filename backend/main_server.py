"""
YieldVision Precision Farming Server
FastAPI backend — PostgreSQL only, offline-first architecture

Endpoints:
  POST /readings/upload        — batch upload from rover SD card (idempotent)
  POST /readings/single        — single live reading
  GET  /zones/{zone_id}/state  — current state from zone_current_state view
  GET  /farms/{farm_id}/summary — farm overview
  GET  /farms/{farm_id}/recommendations — pending recommendations
  POST /recommendations/{id}/apply — mark recommendation as applied
  GET  /farms/detect           — GPS farm detection (which farm is rover on?)
  POST /farms/register         — register a new farm
  POST /zones/register         — register zones within a farm
  GET  /crops/varieties        — list crop varieties from DB
  GET  /market/prices/{crop}   — latest market price for a crop
  GET  /rover/schedule/{farm_id} — rover priority queue
  GET  /health                 — server health check
"""

import logging
import os
import json
from contextlib import asynccontextmanager
from datetime import datetime, date
from typing import Dict, List, Optional, Any

import uvicorn
import psycopg2
import psycopg2.extras
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from decision_engine import decision_engine
from precision_models import soil_model, seed_model
from irrigation_engine import irrigation_engine

# =============================================================================
# LOGGING
# =============================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("yieldvision")


# =============================================================================
# DATABASE CONNECTION
# =============================================================================

DB_CONFIG = {
    "host":     os.getenv("DB_HOST",     "localhost"),
    "port":     int(os.getenv("DB_PORT", "5432")),
    "database": os.getenv("DB_NAME",     "yieldvision"),
    "user":     os.getenv("DB_USER",     "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
}

def get_db():
    """Get a PostgreSQL connection. Caller must close it."""
    conn = psycopg2.connect(**DB_CONFIG)
    conn.cursor_factory = psycopg2.extras.RealDictCursor
    return conn

def set_farm_context(conn, farm_id: str):
    """
    Set Row Level Security session variable so DB only returns this farm's rows.
    Architecture decision [1] — RLS enforced at DB level.
    """
    with conn.cursor() as cur:
        cur.execute("SET app.current_farm_id = %s", (str(farm_id),))


# =============================================================================
# PYDANTIC MODELS (request/response shapes)
# =============================================================================

class SensorReading(BaseModel):
    """Single sensor reading from ComWinTop 7-in-1 + DHT22"""
    zone_id:                str
    farm_id:                str
    rover_id:               str = "ROVER_01"
    collected_at:           Optional[str] = None

    # GPS
    gps_lat:                Optional[float] = None
    gps_lon:                Optional[float] = None
    gps_accuracy_m:         Optional[float] = None

    # ComWinTop RS485 sensor — register addresses per manual
    # 0x0004=Nitrogen, 0x0005=Phosphorus, 0x0006=Potassium (mg/kg)
    # 0x0003=pH (×0.1), 0x0000=Humidity(%×0.1), 0x0001=Temp(°C×0.1)
    # 0x0002=EC(µS/cm), 0x0007=Salinity, 0x0008=TDS
    nitrogen_ppm:           Optional[float] = None
    phosphorus_ppm:         Optional[float] = None
    potassium_ppm:          Optional[float] = None
    ph_level:               Optional[float] = None
    soil_moisture_pct:      Optional[float] = None
    soil_temperature_c:     Optional[float] = None
    electrical_conductivity:Optional[float] = None

    # DHT22
    air_temperature_c:      Optional[float] = None
    air_humidity_pct:       Optional[float] = None

    # SD card sync metadata
    sequence_number:        int = 0
    synced_from_sd:         bool = True
    sd_file_name:           Optional[str] = None
    sensor_battery_v:       Optional[float] = None


class BatchUpload(BaseModel):
    """Batch upload from rover SD card — idempotent [3]"""
    rover_id:   str = "ROVER_01"
    readings:   List[SensorReading]


class RecommendationApply(BaseModel):
    was_applied:     bool
    applied_at:      Optional[str] = None
    farmer_feedback: Optional[str] = None


class FarmRegistration(BaseModel):
    farm_name:       str
    owner_name:      str
    owner_phone:     Optional[str] = None
    county:          str
    soil_type:       str = "loam"
    rainfall_zone:   str = "medium"
    altitude_m:      Optional[float] = None
    latitude_center: Optional[float] = None
    longitude_center:Optional[float] = None


class ZoneRegistration(BaseModel):
    farm_id:     str
    zone_label:  str
    area_m2:     float = 4.0
    center_lat:  float
    center_lon:  float
    soil_type:   Optional[str] = None
    notes:       Optional[str] = None


# =============================================================================
# APP LIFECYCLE
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("YieldVision server starting...")
    try:
        conn = get_db()
        conn.close()
        logger.info("Database connection OK")
    except Exception as e:
        logger.warning(f"Database not available: {e}. Running in limited mode.")
    yield
    logger.info("YieldVision server shutting down.")


app = FastAPI(
    title="YieldVision Precision Farming API",
    version="2.0.0",
    description="Research-backed precision farming decisions for Kenyan smallholders",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# HEALTH CHECK
# =============================================================================

@app.get("/health")
def health_check():
    """Server health + DB connectivity check"""
    db_ok = False
    try:
        conn = get_db()
        conn.close()
        db_ok = True
    except Exception as e:
        pass

    return {
        "status": "ok",
        "database": "connected" if db_ok else "unavailable",
        "version": "2.0.0",
        "timestamp": datetime.now().isoformat()
    }


# =============================================================================
# SENSOR READING UPLOAD
# =============================================================================

@app.post("/readings/upload")
def batch_upload_readings(batch: BatchUpload):
    """
    Bulk upload readings from rover SD card.
    Idempotent — safe to retry, duplicates silently ignored. [3]
    Returns count of new readings inserted vs duplicates skipped.
    """
    inserted = 0
    skipped = 0
    errors = []

    try:
        conn = get_db()
        cur = conn.cursor()

        for reading in batch.readings:
            try:
                # Build full reading dict for storage
                raw = reading.dict()
                collected_dt = datetime.fromisoformat(reading.collected_at) \
                    if reading.collected_at else datetime.now()

                prepared = decision_engine.prepare_reading_for_storage(
                    raw_sensor_data=raw,
                    rover_id=batch.rover_id,
                    sequence_number=reading.sequence_number,
                    collected_at=collected_dt
                )

                # Set farm RLS context
                set_farm_context(conn, reading.farm_id)

                # INSERT ON CONFLICT DO NOTHING — idempotent [3]
                cur.execute("""
                    INSERT INTO sensor_readings (
                        reading_uuid, zone_id, farm_id, rover_id, collected_at,
                        gps_lat, gps_lon, gps_accuracy_m,
                        nitrogen_ppm, phosphorus_ppm, potassium_ppm,
                        ph_level, soil_moisture_pct, soil_temperature_c,
                        electrical_conductivity, air_temperature_c, air_humidity_pct,
                        computed_et0_mm_day, et_calc_method,
                        data_quality_score, validation_flags,
                        sensor_battery_v, synced_from_sd, sd_file_name
                    ) VALUES (
                        %(reading_uuid)s, %(zone_id)s, %(farm_id)s, %(rover_id)s,
                        %(collected_at)s, %(gps_lat)s, %(gps_lon)s, %(gps_accuracy_m)s,
                        %(nitrogen_ppm)s, %(phosphorus_ppm)s, %(potassium_ppm)s,
                        %(ph_level)s, %(soil_moisture_pct)s, %(soil_temperature_c)s,
                        %(electrical_conductivity)s, %(air_temperature_c)s,
                        %(air_humidity_pct)s, %(computed_et0_mm_day)s,
                        %(et_calc_method)s, %(data_quality_score)s,
                        %(validation_flags)s, %(sensor_battery_v)s,
                        %(synced_from_sd)s, %(sd_file_name)s
                    )
                    ON CONFLICT (reading_uuid) DO NOTHING
                """, prepared)

                if cur.rowcount > 0:
                    inserted += 1
                else:
                    skipped += 1

            except Exception as e:
                errors.append({"reading": reading.dict().get("sequence_number"), "error": str(e)})
                logger.error(f"Error inserting reading: {e}")

        conn.commit()
        cur.close()
        conn.close()

    except Exception as e:
        logger.error(f"Batch upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "status": "ok",
        "inserted": inserted,
        "skipped_duplicates": skipped,
        "errors": errors,
        "total_received": len(batch.readings)
    }


@app.post("/readings/single")
def upload_single_reading(reading: SensorReading):
    """Upload a single sensor reading (for live reads when WiFi available)."""
    batch = BatchUpload(rover_id=reading.rover_id, readings=[reading])
    return batch_upload_readings(batch)


# =============================================================================
# ZONE STATE & RECOMMENDATIONS
# =============================================================================

@app.get("/zones/{zone_id}/state")
def get_zone_state(zone_id: str, farm_id: str = Query(...)):
    """
    Get current zone state from zone_current_state view.
    Includes staleness flags, active crop, and latest sensor values. [4]
    """
    try:
        conn = get_db()
        set_farm_context(conn, farm_id)
        cur = conn.cursor()

        cur.execute("""
            SELECT * FROM zone_current_state
            WHERE zone_id = %s AND farm_id = %s::uuid
        """, (zone_id, farm_id))

        row = cur.fetchone()
        cur.close()
        conn.close()

        if not row:
            raise HTTPException(status_code=404, detail=f"Zone {zone_id} not found")

        return dict(row)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Zone state error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/zones/{zone_id}/recommend")
def generate_recommendations(zone_id: str, farm_id: str = Query(...)):
    """
    Generate fresh recommendations for a zone based on latest sensor readings.
    Stores results in recommendations table.
    Returns recommendations with urgency, cost in KES, and calculation trace.
    """
    try:
        conn = get_db()
        set_farm_context(conn, farm_id)
        cur = conn.cursor()

        # Get zone state from view
        cur.execute("""
            SELECT zcs.*, z.soil_type, z.area_m2,
                   cv.kc_mid, cv.root_depth_cm, cv.depletion_fraction_p,
                   f.altitude_m, f.rainfall_zone, f.county
            FROM zone_current_state zcs
            JOIN zones z ON zcs.zone_id = z.zone_id
            JOIN farms f ON z.farm_id = f.farm_id
            LEFT JOIN crop_varieties cv ON zcs.variety_id = cv.variety_id
            WHERE zcs.zone_id = %s::uuid AND zcs.farm_id = %s::uuid
        """, (zone_id, farm_id))

        state = cur.fetchone()
        if not state:
            raise HTTPException(status_code=404, detail="Zone not found")

        state = dict(state)

        # How many times has farmer previously ignored each type?
        cur.execute("""
            SELECT recommendation_type, SUM(ignored_count) as total_ignored
            FROM recommendations
            WHERE zone_id = %s::uuid AND farm_id = %s::uuid
            GROUP BY recommendation_type
        """, (zone_id, farm_id))
        ignored_rows = cur.fetchall()
        ignored_counts = {r["recommendation_type"]: (r["total_ignored"] or 0) for r in ignored_rows}

        # Build inputs for decision engine
        zone_data = {
            "zone_id":                zone_id,
            "farm_id":                farm_id,
            "ph_level":               state.get("ph_level"),
            "nitrogen_ppm":           state.get("nitrogen_ppm"),
            "phosphorus_ppm":         state.get("phosphorus_ppm"),
            "potassium_ppm":          state.get("potassium_ppm"),
            "soil_moisture_pct":      state.get("soil_moisture_pct"),
            "soil_temperature_c":     state.get("soil_temperature_c"),
            "air_temperature_c":      state.get("air_temperature_c"),
            "air_humidity_pct":       state.get("air_humidity_pct"),
            "electrical_conductivity":state.get("electrical_conductivity"),
            "data_quality_score":     state.get("data_quality_score", 1.0),
            "validation_flags":       state.get("validation_flags") or [],
        }

        farm_context = {
            "crop_name":       state.get("crop_name", "maize"),
            "variety_name":    state.get("variety_name"),
            "soil_type":       state.get("soil_type", "loam"),
            "zone_area_m2":    state.get("area_m2", 4.0),
            "planting_date":   state.get("planting_date"),
            "altitude_m":      state.get("altitude_m", 1500.0),
            "rainfall_zone":   state.get("rainfall_zone", "medium"),
            "planting_id":     str(state.get("planting_id")) if state.get("planting_id") else None,
            "reading_uuid":    state.get("last_reading_uuid"),
            "root_depth_cm":   state.get("root_depth_cm", 40.0),
        }

        # Generate recommendations
        result = decision_engine.generate_zone_recommendations(
            zone_data=zone_data,
            farm_context=farm_context,
            ignored_counts=ignored_counts
        )

        # Store each recommendation in DB
        for rec in result.get("recommendations", []):
            if rec.get("recommendation_type") == "monitor":
                continue  # Don't store low-value monitor recommendations

            cur.execute("""
                INSERT INTO recommendations (
                    zone_id, farm_id, planting_id, based_on_reading_uuid,
                    recommendation_type, action_description,
                    action_quantity, action_unit, product_name,
                    estimated_cost_kes, urgency_score, urgency_level,
                    urgency_breakdown, confidence_score, confidence_label,
                    confidence_explanation, knowledge_layer, knowledge_layer_label,
                    ph_gate_active, ph_gate_reason,
                    calculation_breakdown, generated_at
                ) VALUES (
                    %s::uuid, %s::uuid, %s::uuid, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, NOW()
                )
            """, (
                zone_id, farm_id,
                rec.get("planting_id"),
                rec.get("reading_uuid"),
                rec.get("recommendation_type"),
                rec.get("action_description"),
                rec.get("action_quantity"),
                rec.get("action_unit"),
                rec.get("product_name"),
                rec.get("estimated_cost_kes"),
                rec.get("urgency_score"),
                rec.get("urgency_level"),
                json.dumps({"growth_stage": rec.get("growth_stage")}),
                rec.get("confidence_score"),
                rec.get("confidence_label"),
                rec.get("confidence_explanation"),
                rec.get("knowledge_layer", 1),
                rec.get("knowledge_layer_label"),
                rec.get("ph_gate_active", False),
                rec.get("ph_gate_reason"),
                json.dumps(rec.get("calculation_breakdown") or {}),
            ))

        conn.commit()
        cur.close()
        conn.close()

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Recommendation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/farms/{farm_id}/recommendations")
def get_pending_recommendations(farm_id: str):
    """Get all pending (unapplied) recommendations for a farm, ordered by urgency."""
    try:
        conn = get_db()
        set_farm_context(conn, farm_id)
        cur = conn.cursor()

        cur.execute("""
            SELECT * FROM pending_recommendations
            WHERE farm_id = %s::uuid
            ORDER BY urgency_score DESC
        """, (farm_id,))

        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        conn.close()

        return {
            "farm_id": farm_id,
            "total": len(rows),
            "critical": sum(1 for r in rows if r.get("urgency_level") == "CRITICAL"),
            "high":     sum(1 for r in rows if r.get("urgency_level") == "HIGH"),
            "recommendations": rows
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/recommendations/{recommendation_id}/apply")
def mark_recommendation_applied(recommendation_id: str, body: RecommendationApply,
                                  farm_id: str = Query(...)):
    """Record whether a recommendation was applied by the farmer."""
    try:
        conn = get_db()
        set_farm_context(conn, farm_id)
        cur = conn.cursor()

        applied_at = datetime.fromisoformat(body.applied_at) \
            if body.applied_at else datetime.now()

        cur.execute("""
            UPDATE recommendations
            SET was_applied = %s,
                applied_at = %s,
                farmer_feedback = %s
            WHERE recommendation_id = %s::uuid AND farm_id = %s::uuid
        """, (body.was_applied, applied_at, body.farmer_feedback,
              recommendation_id, farm_id))

        conn.commit()
        cur.close()
        conn.close()

        return {"status": "updated", "recommendation_id": recommendation_id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# FARM MANAGEMENT
# =============================================================================

@app.get("/farms/{farm_id}/summary")
def get_farm_summary(farm_id: str):
    """Get farm overview from farm_summary view."""
    try:
        conn = get_db()
        set_farm_context(conn, farm_id)
        cur = conn.cursor()

        cur.execute("""
            SELECT * FROM farm_summary WHERE farm_id = %s::uuid
        """, (farm_id,))

        row = cur.fetchone()
        cur.close()
        conn.close()

        if not row:
            raise HTTPException(status_code=404, detail="Farm not found")

        return dict(row)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/farms/register")
def register_farm(farm: FarmRegistration):
    """Register a new farm. Returns farm_id for subsequent operations."""
    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO farms (
                farm_name, owner_name, owner_phone, county,
                soil_type, rainfall_zone, altitude_m,
                latitude_center, longitude_center,
                assigned_rover_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'ROVER_01')
            RETURNING farm_id
        """, (
            farm.farm_name, farm.owner_name, farm.owner_phone,
            farm.county, farm.soil_type, farm.rainfall_zone,
            farm.altitude_m, farm.latitude_center, farm.longitude_center
        ))

        row = cur.fetchone()
        farm_id = str(row["farm_id"])
        conn.commit()
        cur.close()
        conn.close()

        logger.info(f"Registered farm: {farm.farm_name} ({farm_id})")
        return {"status": "registered", "farm_id": farm_id, "farm_name": farm.farm_name}

    except Exception as e:
        logger.error(f"Farm registration error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/zones/register")
def register_zone(zone: ZoneRegistration):
    """Register a zone within a farm."""
    try:
        conn = get_db()
        set_farm_context(conn, zone.farm_id)
        cur = conn.cursor()

        # Build a minimal polygon around center point (2m × 2m approximation)
        # Proper boundary capture happens via GPS drive in the field
        lat, lon = zone.center_lat, zone.center_lon
        delta = 0.00001  # ~1m at equator
        polygon_wkt = (
            f"POLYGON(("
            f"{lon-delta} {lat-delta}, "
            f"{lon+delta} {lat-delta}, "
            f"{lon+delta} {lat+delta}, "
            f"{lon-delta} {lat+delta}, "
            f"{lon-delta} {lat-delta}"
            f"))"
        )

        cur.execute("""
            INSERT INTO zones (
                farm_id, zone_label, center_lat, center_lon,
                area_m2, soil_type, notes,
                boundary_polygon
            ) VALUES (
                %s::uuid, %s, %s, %s, %s, %s, %s,
                ST_GeomFromText(%s, 4326)
            )
            ON CONFLICT (farm_id, zone_label) DO NOTHING
            RETURNING zone_id
        """, (
            zone.farm_id, zone.zone_label,
            zone.center_lat, zone.center_lon,
            zone.area_m2,
            zone.soil_type,
            zone.notes,
            polygon_wkt
        ))

        row = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()

        if not row:
            return {"status": "exists", "message": f"Zone {zone.zone_label} already registered"}

        return {
            "status": "registered",
            "zone_id": str(row["zone_id"]),
            "zone_label": zone.zone_label,
            "farm_id": zone.farm_id
        }

    except Exception as e:
        logger.error(f"Zone registration error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# GPS FARM DETECTION [2]
# =============================================================================

@app.get("/farms/detect")
def detect_farm_from_gps(lat: float = Query(...), lon: float = Query(...)):
    """
    Given a GPS coordinate, find which farm the rover is currently on.
    Uses PostGIS point-in-polygon containment. [2]
    Called by rover on startup to identify farm automatically.
    """
    try:
        conn = get_db()
        cur = conn.cursor()

        # No RLS needed here — we're searching across all farms
        cur.execute("""
            SELECT farm_id, farm_name, owner_name, county,
                   soil_type, rainfall_zone, altitude_m,
                   assigned_rover_id
            FROM farms
            WHERE is_active = true
              AND ST_Contains(
                    boundary_polygon,
                    ST_SetSRID(ST_Point(%s, %s), 4326)
                  )
            LIMIT 1
        """, (lon, lat))

        row = cur.fetchone()

        if not row:
            # Also check if we're close to a farm center (fallback for farms without polygon)
            cur.execute("""
                SELECT farm_id, farm_name, owner_name, county,
                       soil_type, rainfall_zone, altitude_m,
                       latitude_center, longitude_center,
                       ST_Distance(
                           ST_SetSRID(ST_Point(longitude_center, latitude_center), 4326)::geography,
                           ST_SetSRID(ST_Point(%s, %s), 4326)::geography
                       ) AS distance_m
                FROM farms
                WHERE is_active = true
                  AND latitude_center IS NOT NULL
                ORDER BY distance_m
                LIMIT 1
            """, (lon, lat))
            row = cur.fetchone()

            if row and row.get("distance_m", 9999) > 500:
                cur.close()
                conn.close()
                return {
                    "farm_detected": False,
                    "message": "GPS coordinates do not match any registered farm",
                    "nearest_farm": dict(row) if row else None
                }

        cur.close()
        conn.close()

        if not row:
            return {"farm_detected": False, "message": "No farms registered yet"}

        result = dict(row)
        result["farm_detected"] = True

        logger.info(f"GPS detection: lat={lat}, lon={lon} → farm {result.get('farm_name')}")
        return result

    except Exception as e:
        logger.error(f"GPS detection error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# CROP & MARKET DATA
# =============================================================================

@app.get("/crops/varieties")
def get_crop_varieties(crop_name: Optional[str] = None):
    """List crop varieties from database."""
    try:
        conn = get_db()
        cur = conn.cursor()

        if crop_name:
            cur.execute("""
                SELECT variety_id, crop_name, variety_name, variety_code,
                       ph_optimal_min, ph_optimal_max,
                       nitrogen_optimal_ppm, phosphorus_optimal_ppm, potassium_optimal_ppm,
                       moisture_optimal_min, moisture_optimal_max,
                       kc_initial, kc_mid, kc_end, depletion_fraction_p,
                       days_total, baseline_yield_kg_per_m2,
                       market_price_kes_per_kg_min, market_price_kes_per_kg_max,
                       altitude_range, nitrogen_fixing
                FROM crop_varieties
                WHERE LOWER(crop_name) = LOWER(%s)
                ORDER BY variety_name
            """, (crop_name,))
        else:
            cur.execute("""
                SELECT crop_name, COUNT(*) as variety_count,
                       STRING_AGG(variety_name, ', ') as varieties
                FROM crop_varieties
                GROUP BY crop_name
                ORDER BY crop_name
            """)

        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        conn.close()
        return {"crops": rows, "count": len(rows)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/market/prices/{crop_name}")
def get_market_price(crop_name: str):
    """
    Get latest market price for a crop from cached KAMIS data.
    Falls back gracefully if data is stale. [4]
    """
    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT crop_name, price_kes_per_kg, price_date, source, market_name
            FROM market_prices
            WHERE LOWER(crop_name) = LOWER(%s)
              AND is_current = true
            ORDER BY price_date DESC
            LIMIT 1
        """, (crop_name,))

        row = cur.fetchone()
        cur.close()
        conn.close()

        if not row:
            # Fallback to hardcoded recent prices
            fallback = {
                "maize": 47, "beans": 105, "potatoes": 38,
                "tomatoes": 55, "kale": 8
            }
            price = fallback.get(crop_name.lower(), 50)
            return {
                "crop_name": crop_name,
                "price_kes_per_kg": price,
                "source": "hardcoded_fallback",
                "is_stale": True,
                "note": "No KAMIS data available. Using approximate price."
            }

        result = dict(row)
        # Check if price is older than 30 days
        age_days = (date.today() - result["price_date"]).days if result.get("price_date") else 999
        result["is_stale"] = age_days > 30
        result["age_days"] = age_days

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# ROVER SCHEDULING
# =============================================================================

@app.get("/rover/schedule/{farm_id}")
def get_rover_schedule(farm_id: str):
    """
    Get priority queue for rover visits to this farm.
    Zones with stale readings and high staleness score appear first. [6]
    """
    try:
        conn = get_db()
        set_farm_context(conn, farm_id)
        cur = conn.cursor()

        # Get zones ordered by staleness
        cur.execute("""
            SELECT
                zcs.zone_id,
                zcs.zone_label,
                zcs.crop_name,
                zcs.growth_stage,
                zcs.hours_since_reading,
                zcs.is_stale_npk_ph,
                zcs.is_stale_moisture,
                zcs.is_stale_temperature,
                zcs.needs_urgent_reading,
                zcs.last_reading_at,
                -- Staleness score: higher = more urgent
                CASE
                    WHEN zcs.is_stale_npk_ph THEN zcs.hours_since_reading / 168.0
                    WHEN zcs.is_stale_moisture THEN zcs.hours_since_reading / 24.0
                    ELSE 0
                END AS staleness_score
            FROM zone_current_state zcs
            WHERE zcs.farm_id = %s::uuid
            ORDER BY staleness_score DESC, zcs.zone_label
        """, (farm_id,))

        zones = [dict(r) for r in cur.fetchall()]
        cur.close()
        conn.close()

        urgent = [z for z in zones if z.get("needs_urgent_reading")]
        return {
            "farm_id": farm_id,
            "total_zones": len(zones),
            "urgent_zones": len(urgent),
            "schedule": zones
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# ROVER COMMAND RELAY
# =============================================================================
# The ESP8266 on the rover creates its own WiFi AP ("YieldVision", 192.168.4.1).
# The laptop connects to that hotspot. The React UI can talk directly to the
# ESP8266, but this relay endpoint lets the server act as a proxy — useful
# for debugging or if CORS/network issues arise in production.

import requests as _requests  # stdlib alias to avoid shadowing FastAPI's Request

class RoverCommandRelay(BaseModel):
    direction: str      # W/S/A/D/B/C or space for stop
    rover_ip:  str = "192.168.4.1"

@app.post("/rover/command")
def relay_rover_command(body: RoverCommandRelay):
    """
    Relay a movement command to the rover's ESP8266 WiFi module.
    The ESP8266 forwards the character to the Arduino Mega via Serial1.
    Commands: W=forward S=backward A=left D=right B=burnout C=circle SPACE=stop R=scan
    """
    allowed = set("WSADwsadbcBCrR ")
    if not body.direction or body.direction[0] not in allowed:
        raise HTTPException(status_code=400, detail=f"Invalid command: '{body.direction}'")

    cmd = body.direction[0]
    url = f"http://{body.rover_ip}/cmd?dir={cmd}"
    try:
        resp = _requests.get(url, timeout=2.0)
        return {
            "status":   "sent",
            "command":  cmd,
            "rover_ip": body.rover_ip,
            "rover_ack": resp.text.strip()
        }
    except _requests.exceptions.Timeout:
        raise HTTPException(status_code=503, detail=f"Rover at {body.rover_ip} did not respond (timeout)")
    except _requests.exceptions.ConnectionError:
        raise HTTPException(status_code=503, detail=f"Cannot reach rover at {body.rover_ip} — check WiFi connection")


@app.get("/rover/ping")
def ping_rover(ip: str = "192.168.4.1"):
    """
    Check if the ESP8266 rover module is reachable and return its status JSON.
    React UI polls this to show the connection indicator.
    """
    try:
        resp = _requests.get(f"http://{ip}/status", timeout=2.0)
        data = resp.json()
        return {"reachable": True, "rover_ip": ip, **data}
    except Exception:
        return {"reachable": False, "rover_ip": ip}


# =============================================================================
# IRRIGATION ENDPOINT (direct calc without storing)
# =============================================================================

@app.post("/calculate/irrigation")
def calculate_irrigation(
    zone_id: str,
    farm_id: str = Query(...),
    crop_name: str = Query("maize"),
    days_since_planting: int = Query(30)
):
    """
    Quick irrigation calculation for a zone based on latest readings.
    Does not store result — use /zones/{id}/recommend for full workflow.
    """
    try:
        conn = get_db()
        set_farm_context(conn, farm_id)
        cur = conn.cursor()

        cur.execute("""
            SELECT zcs.soil_moisture_pct, zcs.air_temperature_c,
                   zcs.air_humidity_pct, z.soil_type, z.area_m2
            FROM zone_current_state zcs
            JOIN zones z ON zcs.zone_id = z.zone_id
            WHERE zcs.zone_id = %s::uuid AND zcs.farm_id = %s::uuid
        """, (zone_id, farm_id))

        row = cur.fetchone()
        cur.close()
        conn.close()

        if not row:
            raise HTTPException(status_code=404, detail="Zone not found")

        zone_data = dict(row)
        soil_type = zone_data.get("soil_type", "loam")
        area = zone_data.get("area_m2", 4.0)

        result = irrigation_engine.generate_irrigation_schedule(
            zone_data=zone_data,
            crop_name=crop_name,
            days_since_planting=days_since_planting,
            soil_type=soil_type,
            zone_area_m2=area
        )
        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    uvicorn.run(
        "main_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )