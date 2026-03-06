"""
YieldVision Precision Farming Server
Main FastAPI server with RTX 3070 GPU support
"""

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import torch
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional
import json
import os
from contextlib import asynccontextmanager

# Import backend modules
from decision_engine import decision_engine
from precision_models import soil_model, water_model, seed_model
from irrigation_engine import irrigation_engine
from edge_storage import edge_storage

@asynccontextmanager
async def lifespan(app: FastAPI):
    _load_mock_data_on_startup()
    yield

app = FastAPI(title="YieldVision Precision Farming API", version="1.0.0", lifespan=lifespan)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# GPU Check
GPU_AVAILABLE = torch.cuda.is_available()
if GPU_AVAILABLE:
    print(f"GPU detected: {torch.cuda.get_device_name(0)}")
    print(f"GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
else:
    print("No GPU detected - using CPU")

# In-memory storage for development (will be replaced with databases)
precision_zones = {}
sensor_data = []
decisions = []

# Zone label mapping: short readable labels like AA, AB, AC...
zone_labels = {}  # zone_id -> label (e.g. "AA")

def _generate_zone_labels(zone_ids: list) -> dict:
    """Generate short alphabetic labels AA, AB, AC... BA, BB... for zones"""
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    labels = {}
    for i, zid in enumerate(sorted(zone_ids)):
        first = letters[i // 26] if i // 26 < 26 else "Z"
        second = letters[i % 26]
        labels[zid] = f"{first}{second}"
    return labels

class PrecisionZone:
    """Represents a 2m x 2m precision farming zone"""
    def __init__(self, zone_id: str, center_lat: float, center_lon: float):
        self.zone_id = zone_id
        self.center_lat = center_lat
        self.center_lon = center_lon
        self.area_m2 = 4.0  # 2m x 2m
        self.soil_type = "unknown"
        self.slope_percent = 0.0
        self.aspect_degrees = 0
        self.drainage_rate = "medium"
        self.created_at = datetime.now()

def _load_mock_data_on_startup():
    """Load mock zones and sensor readings into memory for demo mode"""
    mock_dir = os.path.join(os.path.dirname(__file__), "..", "mock_data")
    
    zones_file = os.path.join(mock_dir, "mock_zones.json")
    if os.path.exists(zones_file):
        with open(zones_file, "r") as f:
            zones_list = json.load(f)
        for z in zones_list:
            zone_id = z["zone_id"]
            zone = PrecisionZone(zone_id, z["center_lat"], z["center_lon"])
            zone.soil_type = z.get("soil_type", "loamy")
            zone.slope_percent = z.get("slope_percent", 0.0)
            zone.aspect_degrees = z.get("aspect_degrees", 0)
            zone.drainage_rate = z.get("drainage_rate", "medium")
            precision_zones[zone_id] = zone
            
            # Store in edge storage
            edge_storage.store_zone({
                'zone_id': zone_id,
                'center_lat': z["center_lat"],
                'center_lon': z["center_lon"],
                'area_m2': 4.0,
                'soil_type': zone.soil_type,
                'slope_percent': zone.slope_percent,
                'aspect_degrees': zone.aspect_degrees,
                'drainage_rate': zone.drainage_rate
            })
        
        # Generate short labels for all zones
        zone_labels.update(_generate_zone_labels(list(precision_zones.keys())))
        print(f"Demo: loaded {len(zones_list)} zones from mock_zones.json")
    
    readings_file = os.path.join(mock_dir, "mock_sensor_readings.json")
    if os.path.exists(readings_file):
        with open(readings_file, "r") as f:
            readings_list = json.load(f)
        for r in readings_list:
            sensor_data.append(r)
            
            # Store in edge storage
            edge_storage.store_sensor_reading(r)
        
        print(f"Demo: loaded {len(readings_list)} sensor readings from mock_sensor_readings.json")

class SensorReading:
    """Precision sensor reading for a specific zone"""
    def __init__(self, zone_id: str, gps_lat: float, gps_lon: float):
        self.zone_id = zone_id
        self.gps_lat = gps_lat
        self.gps_lon = gps_lon
        self.soil_moisture_5cm = 0.0
        self.soil_moisture_20cm = 0.0
        self.nitrogen_ppm = 0.0
        self.phosphorus_ppm = 0.0
        self.potassium_ppm = 0.0
        self.ph_level = 7.0
        self.temperature_c = 25.0
        self.organic_matter_percent = 2.0
        self.timestamp = datetime.now()

def calculate_zone_id(lat: float, lon: float) -> str:
    """Generate zone ID from GPS coordinates (2m grid)"""
    # Convert to 2m grid coordinates
    lat_grid = int(lat * 50000) / 50000  # ~2m precision
    lon_grid = int(lon * 50000) / 50000
    return f"Z_{lat_grid:.6f}_{lon_grid:.6f}"

@app.get("/")
async def root():
    return {
        "message": "YieldVision Precision Farming API",
        "gpu_available": GPU_AVAILABLE,
        "zones_count": len(precision_zones),
        "sensor_readings": len(sensor_data)
    }

@app.get("/api/precision/status")
async def get_system_status():
    """Get system status and GPU information"""
    status = {
        "system": "YieldVision Precision Farming",
        "gpu_available": GPU_AVAILABLE,
        "zones_mapped": len(precision_zones),
        "total_sensor_readings": len(sensor_data),
        "decisions_made": len(decisions),
        "server_time": datetime.now().isoformat(),
        "edge_storage_status": edge_storage.get_sync_status()
    }
    
    if GPU_AVAILABLE:
        status.update({
            "gpu_name": torch.cuda.get_device_name(0),
            "gpu_memory_total": f"{torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB",
            "gpu_memory_used": f"{torch.cuda.memory_allocated(0) / 1e9:.1f} GB"
        })
    
    return status

@app.post("/api/precision/sensor-data")
async def receive_sensor_data(data: Dict):
    """Receive precision sensor data from Arduino rover"""
    try:
        # Extract sensor data
        gps_lat = data.get('gps_lat')
        gps_lon = data.get('gps_lon')
        
        if not gps_lat or not gps_lon:
            raise HTTPException(status_code=400, detail="GPS coordinates required")
        
        # Calculate or get zone ID
        zone_id = data.get('zone_id') or calculate_zone_id(gps_lat, gps_lon)
        
        # Create zone if it doesn't exist
        if zone_id not in precision_zones:
            precision_zones[zone_id] = PrecisionZone(zone_id, gps_lat, gps_lon)
        
        # Create sensor reading
        reading = SensorReading(zone_id, gps_lat, gps_lon)
        reading.soil_moisture_5cm = data.get('soil_moisture_5cm', 0.0)
        reading.soil_moisture_20cm = data.get('soil_moisture_20cm', 0.0)
        reading.nitrogen_ppm = data.get('nitrogen_ppm', 0.0)
        reading.phosphorus_ppm = data.get('phosphorus_ppm', 0.0)
        reading.potassium_ppm = data.get('potassium_ppm', 0.0)
        reading.ph_level = data.get('ph_level', 7.0)
        reading.temperature_c = data.get('temperature_c', 25.0)
        reading.organic_matter_percent = data.get('organic_matter_percent', 2.0)
        
        sensor_data.append(reading.__dict__)
        
        # Store in edge storage
        edge_storage.store_sensor_reading(reading.__dict__)
        
        return {
            "status": "success",
            "zone_id": zone_id,
            "reading_count": len(sensor_data),
            "message": f"Sensor data received for zone {zone_id}"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing sensor data: {str(e)}")

@app.get("/api/precision/zones")
async def get_zones():
    """Get all mapped precision zones with short labels"""
    zones_list = []
    for zone_id, zone in precision_zones.items():
        zones_list.append({
            "zone_id": zone.zone_id,
            "zone_label": zone_labels.get(zone_id, zone_id),
            "center_lat": zone.center_lat,
            "center_lon": zone.center_lon,
            "area_m2": zone.area_m2,
            "soil_type": zone.soil_type,
            "slope_percent": zone.slope_percent,
            "aspect_degrees": zone.aspect_degrees,
            "created_at": zone.created_at.isoformat()
        })
    
    return {"zones": zones_list, "total_count": len(zones_list)}

@app.get("/api/precision/zones/summary")
async def get_zones_summary():
    """Get zone summary with latest sensor readings for dashboard display"""
    summary = []
    for zone_id, zone in precision_zones.items():
        zone_readings = [r for r in sensor_data if r.get('zone_id') == zone_id]
        latest = zone_readings[-1] if zone_readings else {}
        moisture = latest.get('soil_moisture_20cm', None)
        nitrogen = latest.get('nitrogen_ppm', None)
        ph = latest.get('ph_level', None)
        
        # Compute soil health status
        if moisture is not None:
            if 30 <= moisture <= 45 and ph and 6.0 <= ph <= 7.0 and nitrogen and nitrogen >= 80:
                status = "good"
            elif moisture < 20 or (ph and (ph < 5.5 or ph > 8.0)) or (nitrogen and nitrogen < 40):
                status = "danger"
            else:
                status = "average"
        else:
            status = "unknown"

        summary.append({
            "zone_id": zone_id,
            "zone_label": zone_labels.get(zone_id, zone_id),
            "soil_type": zone.soil_type,
            "soil_moisture_20cm": round(moisture, 1) if moisture else None,
            "nitrogen_ppm": round(nitrogen, 1) if nitrogen else None,
            "ph_level": round(ph, 2) if ph else None,
            "status": status,
            "has_data": bool(latest),
        })
    return {"zones": summary, "total_count": len(summary)}

@app.get("/api/precision/auto-decisions")
async def get_auto_decisions():
    """Auto-generate 5 best action recommendations per zone using Monte Carlo"""
    ACTION_CANDIDATES = [
        {"type": "irrigate",             "amount": 10, "label": "Irrigate 10L"},
        {"type": "irrigate",             "amount": 20, "label": "Irrigate 20L"},
        {"type": "fertilize_nitrogen",   "amount": 5,  "label": "Add Nitrogen 5kg"},
        {"type": "fertilize_nitrogen",   "amount": 10, "label": "Add Nitrogen 10kg"},
        {"type": "fertilize_phosphorus", "amount": 5,  "label": "Add Phosphorus 5kg"},
        {"type": "fertilize_potassium",  "amount": 5,  "label": "Add Potassium 5kg"},
        {"type": "adjust_ph_up",         "amount": 3,  "label": "Raise pH (lime 3L)"},
        {"type": "adjust_ph_down",       "amount": 3,  "label": "Lower pH (sulfur 3L)"},
    ]

    all_recommendations = []
    for zone_id, zone in list(precision_zones.items()):
        zone_readings = [r for r in sensor_data if r.get('zone_id') == zone_id]
        if not zone_readings:
            continue
        latest = zone_readings[-1]
        zone_data = {
            "zone_id": zone_id,
            "soil_moisture_20cm": latest.get("soil_moisture_20cm", 30),
            "nitrogen_ppm": latest.get("nitrogen_ppm", 50),
            "phosphorus_ppm": latest.get("phosphorus_ppm", 30),
            "potassium_ppm": latest.get("potassium_ppm", 40),
            "ph_level": latest.get("ph_level", 7.0),
            "temperature_c": latest.get("soil_temperature_c", 25.0),
            "organic_matter_percent": latest.get("organic_matter_percent", 2.0),
            "soil_type": zone.soil_type,
        }

        scored = []
        for action in ACTION_CANDIDATES:
            try:
                result = decision_engine.evaluate_action(zone_data, action, time_horizon=14)
                scored.append({
                    "action_label": action["label"],
                    "action": action,
                    "expected_yield_kg": round(result["expected_yield_kg_per_zone"]["mean"], 2),
                    "net_benefit_usd": round(result["expected_net_benefit_usd"]["mean"], 2),
                    "roi": round(result["expected_roi_multiplier"]["mean"], 2),
                    "risk": result["risk_assessment"]["risk_level"],
                    "recommendation": result["recommendation"],
                    "confidence": round(result["confidence_score"], 2),
                })
            except Exception:
                pass

        # Sort by net benefit descending, pick top 5
        top5 = sorted(scored, key=lambda x: x["net_benefit_usd"], reverse=True)[:5]
        all_recommendations.append({
            "zone_id": zone_id,
            "zone_label": zone_labels.get(zone_id, zone_id),
            "top_actions": top5,
        })

    return {"recommendations": all_recommendations}

@app.get("/api/precision/zone/{zone_id}/decisions")
async def get_zone_decisions(zone_id: str):
    """Auto-generate top-5 decisions for a single zone using Monte Carlo"""
    if zone_id not in precision_zones:
        raise HTTPException(status_code=404, detail="Zone not found")

    ACTION_CANDIDATES = [
        {"type": "irrigate",             "amount": 10, "label": "Irrigate 10L"},
        {"type": "irrigate",             "amount": 20, "label": "Irrigate 20L"},
        {"type": "fertilize_nitrogen",   "amount": 5,  "label": "Add Nitrogen 5kg"},
        {"type": "fertilize_nitrogen",   "amount": 10, "label": "Add Nitrogen 10kg"},
        {"type": "fertilize_phosphorus", "amount": 5,  "label": "Add Phosphorus 5kg"},
        {"type": "fertilize_potassium",  "amount": 5,  "label": "Add Potassium 5kg"},
        {"type": "adjust_ph_up",         "amount": 3,  "label": "Raise pH (lime 3L)"},
        {"type": "adjust_ph_down",       "amount": 3,  "label": "Lower pH (sulfur 3L)"},
    ]

    zone = precision_zones[zone_id]
    zone_readings = [r for r in sensor_data if r.get('zone_id') == zone_id]
    if not zone_readings:
        raise HTTPException(status_code=404, detail="No sensor data for zone")
    latest = zone_readings[-1]
    zone_data = {
        "zone_id": zone_id,
        "soil_moisture_20cm": latest.get("soil_moisture_20cm", 30),
        "nitrogen_ppm": latest.get("nitrogen_ppm", 50),
        "phosphorus_ppm": latest.get("phosphorus_ppm", 30),
        "potassium_ppm": latest.get("potassium_ppm", 40),
        "ph_level": latest.get("ph_level", 7.0),
        "temperature_c": latest.get("soil_temperature_c", 25.0),
        "organic_matter_percent": latest.get("organic_matter_percent", 2.0),
        "soil_type": zone.soil_type,
    }

    scored = []
    for action in ACTION_CANDIDATES:
        try:
            result = decision_engine.evaluate_action(zone_data, action, time_horizon=14)
            scored.append({
                "action_label": action["label"],
                "action": action,
                "expected_yield_kg": round(result["expected_yield_kg_per_zone"]["mean"], 2),
                "net_benefit_usd": round(result["expected_net_benefit_usd"]["mean"], 2),
                "roi": round(result["expected_roi_multiplier"]["mean"], 2),
                "risk": result["risk_assessment"]["risk_level"],
                "recommendation": result["recommendation"],
                "confidence": round(result["confidence_score"], 2),
            })
        except Exception:
            pass

    top5 = sorted(scored, key=lambda x: x["net_benefit_usd"], reverse=True)[:5]
    return {
        "zone_id": zone_id,
        "zone_label": zone_labels.get(zone_id, zone_id),
        "top_actions": top5,
    }

# Irrigation Planning Endpoints (using irrigation_engine)
@app.post("/api/irrigation/plan-from-yield-goal")
async def create_irrigation_plan_from_yield_goal(data: Dict):
    """Create irrigation plan based on yield goal"""
    try:
        zone_id = data.get('zone_id')
        crop_type = data.get('crop_type')
        target_yield_kg_per_zone = data.get('target_yield_kg_per_zone')
        
        if not all([zone_id, crop_type, target_yield_kg_per_zone]):
            raise HTTPException(status_code=400, detail="Missing required fields: zone_id, crop_type, target_yield_kg_per_zone")
        
        # Get zone data
        if zone_id not in precision_zones:
            raise HTTPException(status_code=404, detail=f"Zone {zone_id} not found")
        
        zone_data = precision_zones[zone_id].copy()
        zone_data['zone_id'] = zone_id
        
        # Add recent sensor data
        zone_readings = [r for r in sensor_data if r.get('zone_id') == zone_id]
        if zone_readings:
            latest_reading = zone_readings[-1]
            zone_data.update(latest_reading)
        
        # Create irrigation plan using irrigation_engine
        irrigation_plan = irrigation_engine.create_irrigation_schedule(
            zone_data, crop_type, target_yield_kg_per_zone
        )
        
        return {
            "success": True,
            "irrigation_plan": irrigation_plan,
            "created_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating irrigation plan: {str(e)}")

@app.post("/api/irrigation/optimize")
async def optimize_irrigation_schedule(data: Dict):
    """Optimize irrigation schedule for water conservation"""
    try:
        zone_id = data.get('zone_id')
        crop_type = data.get('crop_type')
        target_yield_kg_per_zone = data.get('target_yield_kg_per_zone')
        
        if not all([zone_id, crop_type, target_yield_kg_per_zone]):
            raise HTTPException(status_code=400, detail="Missing required fields")
        
        # Get zone data
        if zone_id not in precision_zones:
            raise HTTPException(status_code=404, detail="Zone {zone_id} not found")
        
        zone_data = precision_zones[zone_id].copy()
        zone_data['zone_id'] = zone_id
        
        # Add recent sensor data
        zone_readings = [r for r in sensor_data if r.get('zone_id') == zone_id]
        if zone_readings:
            latest_reading = zone_readings[-1]
            zone_data.update(latest_reading)
        
        # Create optimization plan using irrigation_engine
        optimization = irrigation_engine.optimize_for_water_conservation(
            zone_data, crop_type, target_yield_kg_per_zone
        )
        
        return {
            "success": True,
            "optimization_plan": optimization,
            "created_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error optimizing irrigation: {str(e)}")

# Edge Storage Endpoints
@app.post("/api/edge/sync")
async def sync_edge_to_cloud():
    """Sync edge data to cloud PostgreSQL"""
    try:
        sync_result = edge_storage.sync_to_cloud()
        return sync_result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync error: {str(e)}")

@app.get("/api/edge/export")
async def export_edge_data():
    """Export edge data to JSON"""
    try:
        export_path = edge_storage.export_to_json()
        return {"export_path": export_path, "status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export error: {str(e)}")

@app.get("/api/edge/status")
async def get_edge_status():
    """Get edge storage status"""
    return edge_storage.get_sync_status()

# Future weather API integration (commented out for future implementation)
"""
@app.get("/api/weather/forecast/{zone_id}")
async def get_weather_forecast(zone_id: str):
    # TODO: Implement weather API integration
    # Plan to integrate with OpenWeatherMap or similar service
    pass

@app.post("/api/irrigation/weather-adjusted")
async def weather_adjusted_irrigation(data: Dict):
    # TODO: Implement weather-based irrigation adjustment
    # Will use forecast data to modify irrigation schedules
    pass
"""

if __name__ == "__main__":
    print("Starting YieldVision Precision Farming Server...")
    print(f"GPU Available: {GPU_AVAILABLE}")
    print("Server will be available at: http://localhost:8000")
    print("API Documentation: http://localhost:8000/docs")
    
    # Start edge storage auto-sync
    edge_storage.start_auto_sync()
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
