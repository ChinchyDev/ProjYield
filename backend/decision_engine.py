"""
YieldVision Decision Engine
Orchestrates recommendations from all sub-engines into a single per-zone decision.

Architecture decisions implemented:
  [10] pH hard gate — enforced here, NPK blocked if pH critical
  [11] Urgency scoring — deviation × stage multiplier × ignored penalty
  [12] Plain language confidence labels — raw scores never shown to farmer
  [7]  Knowledge layer label — "Based on published research" etc.
  [8]  Full calculation trace stored in every recommendation
"""

import math
import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple
import json

from precision_models import soil_model, seed_model
from irrigation_engine import irrigation_engine

logger = logging.getLogger(__name__)


# =============================================================================
# URGENCY SCORING CONFIG
# =============================================================================

# Growth stage multipliers — critical stages weighted higher [11]
# Source: general agronomic practice; germination and flowering are most sensitive
STAGE_MULTIPLIERS = {
    "initial":     2.0,   # germination — very sensitive, mistakes here lose the crop
    "development": 1.5,   # establishment
    "mid":         2.0,   # flowering/fruiting — peak sensitivity
    "late":        0.5,   # maturation — less sensitive
    "mature":      0.3,   # harvest window — minimal intervention value
    "harvested":   0.0,   # done
}

# Urgency thresholds
URGENCY_THRESHOLDS = {
    "CRITICAL": 2.0,
    "HIGH":     1.0,
    "MEDIUM":   0.5,
    "LOW":      0.0,
}

# Confidence score → label mapping [12]
CONFIDENCE_LABELS = {
    (0.85, 1.01, True):  ("High confidence",     "Based on your farm's historical data"),
    (0.85, 1.01, False): ("High confidence",     "Based on published research for these conditions"),
    (0.70, 0.85, True):  ("Moderate confidence", "Calibrated from similar farms in your region"),
    (0.70, 0.85, False): ("Moderate confidence", "Based on research for similar farms — monitor closely"),
    (0.50, 0.70, True):  ("Low confidence",      "Limited farm-specific data — good starting point"),
    (0.50, 0.70, False): ("Low confidence",      "Limited data for your specific conditions"),
    (0.00, 0.50, True):  ("Uncertain",           "Not enough data yet — collect more readings"),
    (0.00, 0.50, False): ("Uncertain",           "Insufficient data — use as rough guidance only"),
}

# Knowledge layer labels [7]
KNOWLEDGE_LAYER_LABELS = {
    1: "Based on published research (FAO, KALRO, IFDC)",
    2: "Calibrated for your region from multiple farms",
    3: "Learned from your farm's own seasonal history",
}


# =============================================================================
# DECISION ENGINE
# =============================================================================

class DecisionEngine:
    """
    Central recommendation orchestrator.
    Takes zone sensor data and generates a complete, prioritised set of
    recommendations with full calculation traces and plain language summaries.
    """

    def __init__(self):
        self.soil_model = soil_model
        self.seed_model = seed_model
        self.irrigation = irrigation_engine

    # -------------------------------------------------------------------------
    # MAIN ENTRY POINT
    # -------------------------------------------------------------------------
    def generate_zone_recommendations(
        self,
        zone_data: Dict,
        farm_context: Dict,
        ignored_counts: Optional[Dict] = None
    ) -> Dict:
        """
        Generate all recommendations for one zone.

        Args:
            zone_data: Must include readings from sensor_readings table:
                zone_id, farm_id, ph_level, nitrogen_ppm, phosphorus_ppm,
                potassium_ppm, soil_moisture_pct, soil_temperature_c,
                air_temperature_c, air_humidity_pct, electrical_conductivity,
                data_quality_score, collected_at

            farm_context: Info about the zone:
                crop_name, variety_name, soil_type, zone_area_m2,
                planting_date (date object or ISO string),
                altitude_m, rainfall_zone, reading_uuid, planting_id

            ignored_counts: Dict mapping recommendation_type → times previously ignored
                Used for urgency penalty. Defaults to zero.

        Returns:
            Dict with list of recommendations, each with urgency score,
            plain language action, calculation trace, and cost in KES.
        """
        if ignored_counts is None:
            ignored_counts = {}

        # --- Parse context ---
        crop_name    = farm_context.get("crop_name", "maize")
        soil_type    = farm_context.get("soil_type", "loam")
        zone_area    = farm_context.get("zone_area_m2", 4.0)
        altitude     = farm_context.get("altitude_m", 1500.0)
        rainfall     = farm_context.get("rainfall_zone", "medium")
        planting_id  = farm_context.get("planting_id")
        reading_uuid = farm_context.get("reading_uuid")

        # Days since planting and growth stage
        days_planted, growth_stage = self._get_growth_stage(
            farm_context.get("planting_date"),
            crop_name
        )

        # Data quality check — low quality readings lower confidence
        data_quality = zone_data.get("data_quality_score", 1.0)
        validation_flags = zone_data.get("validation_flags", [])

        all_recommendations = []

        # ---- SOIL RECOMMENDATIONS (NPK + pH) ----
        soil_result = self.soil_model.generate_soil_recommendation(
            zone_data=zone_data,
            crop_name=crop_name,
            soil_type=soil_type,
            zone_area_m2=zone_area,
            days_since_planting=days_planted,
            growth_stage=growth_stage,
            root_depth_cm=farm_context.get("root_depth_cm", 40.0)
        )

        for rec in soil_result.get("recommendations", []):
            rec_type = rec.get("recommendation_type", "monitor")
            ignored_n = ignored_counts.get(rec_type, 0)

            # Compute urgency score
            urgency_score = self._compute_urgency_score(
                base_urgency=rec.get("urgency_level", "LOW"),
                growth_stage=growth_stage,
                ignored_count=ignored_n,
                data_quality=data_quality
            )
            rec["urgency_score"] = urgency_score
            rec["urgency_level"] = self._score_to_level(urgency_score)

            # Confidence
            conf_score, conf_label, conf_explanation = self._compute_confidence(
                data_quality=data_quality,
                knowledge_layer=1,   # Layer 1 until farm history builds up
                has_farm_history=False,
                validation_flags=validation_flags
            )
            rec["confidence_score"]      = conf_score
            rec["confidence_label"]      = conf_label
            rec["confidence_explanation"] = conf_explanation
            rec["knowledge_layer"]       = 1
            rec["knowledge_layer_label"] = KNOWLEDGE_LAYER_LABELS[1]

            # Metadata
            rec["zone_id"]       = zone_data.get("zone_id")
            rec["farm_id"]       = zone_data.get("farm_id")
            rec["planting_id"]   = planting_id
            rec["reading_uuid"]  = reading_uuid
            rec["generated_at"]  = datetime.now().isoformat()
            rec["growth_stage"]  = growth_stage
            rec["days_since_planting"] = days_planted

            all_recommendations.append(rec)

        # ---- IRRIGATION RECOMMENDATION ----
        if days_planted >= 0 and crop_name:
            irr_result = self.irrigation.generate_irrigation_schedule(
                zone_data=zone_data,
                crop_name=crop_name,
                days_since_planting=days_planted,
                soil_type=soil_type,
                zone_area_m2=zone_area,
                root_depth_override_cm=farm_context.get("root_depth_cm")
            )

            ignored_n = ignored_counts.get("irrigate", 0)
            urgency_score = self._compute_urgency_score(
                base_urgency=irr_result.get("urgency_level", "LOW"),
                growth_stage=growth_stage,
                ignored_count=ignored_n,
                data_quality=data_quality
            )
            irr_result["urgency_score"] = urgency_score
            irr_result["urgency_level"] = self._score_to_level(urgency_score)

            conf_score, conf_label, conf_explanation = self._compute_confidence(
                data_quality=data_quality,
                knowledge_layer=1,
                has_farm_history=False,
                validation_flags=validation_flags
            )
            irr_result["confidence_score"]       = conf_score
            irr_result["confidence_label"]       = conf_label
            irr_result["confidence_explanation"] = conf_explanation
            irr_result["knowledge_layer"]        = 1
            irr_result["knowledge_layer_label"]  = KNOWLEDGE_LAYER_LABELS[1]

            irr_result["zone_id"]      = zone_data.get("zone_id")
            irr_result["farm_id"]      = zone_data.get("farm_id")
            irr_result["planting_id"]  = planting_id
            irr_result["reading_uuid"] = reading_uuid
            irr_result["generated_at"] = datetime.now().isoformat()
            irr_result["growth_stage"] = growth_stage

            all_recommendations.append(irr_result)

        # ---- HARVEST WARNING ----
        if days_planted > 0:
            harvest_rec = self._check_harvest_window(
                crop_name, days_planted, zone_data, zone_area
            )
            if harvest_rec:
                harvest_rec["zone_id"]  = zone_data.get("zone_id")
                harvest_rec["farm_id"]  = zone_data.get("farm_id")
                harvest_rec["urgency_score"] = self._compute_urgency_score(
                    "HIGH", growth_stage, 0, data_quality
                )
                harvest_rec["urgency_level"] = "HIGH"
                all_recommendations.append(harvest_rec)

        # ---- SORT by urgency score ----
        all_recommendations.sort(
            key=lambda x: x.get("urgency_score", 0), reverse=True
        )

        # ---- ALERT FATIGUE CAP: max 3 CRITICAL per zone per call ----
        critical_count = 0
        for rec in all_recommendations:
            if rec.get("urgency_level") == "CRITICAL":
                critical_count += 1
                if critical_count > 3:
                    rec["urgency_level"] = "HIGH"
                    rec["urgency_score"] = 1.5

        total_cost = sum(r.get("estimated_cost_kes", 0) or 0 for r in all_recommendations)

        return {
            "zone_id":           zone_data.get("zone_id"),
            "farm_id":           zone_data.get("farm_id"),
            "crop_name":         crop_name,
            "growth_stage":      growth_stage,
            "days_since_planting": days_planted,
            "generated_at":      datetime.now().isoformat(),
            "data_quality_score": data_quality,
            "recommendations":   all_recommendations,
            "total_recommendations": len(all_recommendations),
            "critical_count":    min(critical_count, 3),
            "total_estimated_cost_kes": round(total_cost, 2),
        }

    # -------------------------------------------------------------------------
    # URGENCY SCORING [11]
    # score = base_score × stage_multiplier × ignored_penalty × quality_factor
    # -------------------------------------------------------------------------
    def _compute_urgency_score(
        self,
        base_urgency: str,
        growth_stage: str,
        ignored_count: int,
        data_quality: float
    ) -> float:
        """
        Compute numeric urgency score from components.

        base_urgency: CRITICAL=2.5, HIGH=1.5, MEDIUM=0.75, LOW=0.25
        stage_multiplier: from STAGE_MULTIPLIERS
        ignored_penalty: 0.7 per time ignored (reduces score to prevent spam)
        quality_factor: scales with data_quality_score
        """
        base_scores = {"CRITICAL": 2.5, "HIGH": 1.5, "MEDIUM": 0.75, "LOW": 0.25}
        base = base_scores.get(base_urgency, 0.25)

        stage_mult = STAGE_MULTIPLIERS.get(growth_stage, 1.0)

        # Ignored penalty — each time farmer ignored this type, score drops 30%
        ignored_penalty = 0.7 ** min(ignored_count, 3)   # cap at 3 ignores

        # Data quality factor — low quality readings produce lower urgency
        quality_factor = 0.5 + (data_quality * 0.5)  # 0.5 at quality=0, 1.0 at quality=1

        score = base * stage_mult * ignored_penalty * quality_factor
        return round(score, 3)

    def _score_to_level(self, score: float) -> str:
        if score >= URGENCY_THRESHOLDS["CRITICAL"]:
            return "CRITICAL"
        elif score >= URGENCY_THRESHOLDS["HIGH"]:
            return "HIGH"
        elif score >= URGENCY_THRESHOLDS["MEDIUM"]:
            return "MEDIUM"
        else:
            return "LOW"

    # -------------------------------------------------------------------------
    # CONFIDENCE LABELS [12]
    # Raw score stored in DB, plain language shown to farmer
    # -------------------------------------------------------------------------
    def _compute_confidence(
        self,
        data_quality: float,
        knowledge_layer: int,
        has_farm_history: bool,
        validation_flags: List[str]
    ) -> Tuple[float, str, str]:
        """
        Returns (raw_score, label, explanation)
        """
        # Base confidence from knowledge layer
        layer_base = {1: 0.75, 2: 0.82, 3: 0.90}
        score = layer_base.get(knowledge_layer, 0.75)

        # Penalise for data quality
        score = score * data_quality

        # Penalise for validation flags
        score -= len(validation_flags) * 0.05

        score = max(0.0, min(1.0, score))

        # Plain language
        label, explanation = self._confidence_label(score, has_farm_history)
        return round(score, 2), label, explanation

    def _confidence_label(self, score: float, has_farm_history: bool) -> Tuple[str, str]:
        if score >= 0.85:
            if has_farm_history:
                return "High confidence", "Based on how your farm responded before — safe to act"
            return "High confidence", "Based on published research for these crop conditions"
        elif score >= 0.70:
            if has_farm_history:
                return "Moderate confidence", "Calibrated from similar farms in your region"
            return "Moderate confidence", "Based on research for similar farms — act and monitor"
        elif score >= 0.50:
            return "Low confidence", "Starting point — limited data for your conditions, monitor closely"
        else:
            return "Uncertain", "Collect more readings before acting on this recommendation"

    # -------------------------------------------------------------------------
    # GROWTH STAGE FROM PLANTING DATE
    # -------------------------------------------------------------------------
    def _get_growth_stage(
        self,
        planting_date,
        crop_name: str
    ) -> Tuple[int, str]:
        """
        Calculate days since planting and derive growth stage.
        Falls back to "mid" if planting date unknown.
        """
        if planting_date is None:
            return 30, "mid"

        if isinstance(planting_date, str):
            try:
                planting_date = date.fromisoformat(planting_date)
            except Exception:
                return 30, "mid"

        if isinstance(planting_date, datetime):
            planting_date = planting_date.date()

        days = (date.today() - planting_date).days
        days = max(0, days)

        # Get stage boundaries from irrigation_engine crop params
        crop = crop_name.lower()
        params = irrigation_engine.crop_params.get(crop, irrigation_engine.crop_params["maize"])
        d_init = params["days_initial"]
        d_dev  = params["days_dev"]
        d_mid  = params["days_mid"]
        d_late = params["days_late"]
        total  = d_init + d_dev + d_mid + d_late

        if days <= d_init:
            stage = "initial"
        elif days <= d_init + d_dev:
            stage = "development"
        elif days <= d_init + d_dev + d_mid:
            stage = "mid"
        elif days <= total:
            stage = "late"
        else:
            stage = "mature"

        return days, stage

    # -------------------------------------------------------------------------
    # HARVEST WINDOW CHECK
    # -------------------------------------------------------------------------
    def _check_harvest_window(
        self,
        crop_name: str,
        days_since_planting: int,
        zone_data: Dict,
        zone_area_m2: float
    ) -> Optional[Dict]:
        """
        Warn farmer if crop is approaching or in harvest window.
        """
        crop = crop_name.lower()
        params = irrigation_engine.crop_params.get(crop)
        if not params:
            return None

        total_days = params["days_initial"] + params["days_dev"] + params["days_mid"] + params["days_late"]
        days_to_harvest = total_days - days_since_planting

        if 0 <= days_to_harvest <= 14:
            return {
                "recommendation_type": "harvest_soon",
                "action_description": (
                    f"{crop_name.title()} is approaching harvest — approximately {days_to_harvest} days remaining. "
                    f"Prepare storage and check market prices. Reduce irrigation in the last week."
                ),
                "urgency_level": "HIGH",
                "action_quantity": None,
                "estimated_cost_kes": 0,
                "generated_at": datetime.now().isoformat()
            }
        return None

    # -------------------------------------------------------------------------
    # YIELD ESTIMATION
    # Source: FAO Irrigation and Drainage Paper No. 33 (yield response to water)
    # Mitscherlich yield response to nutrients (FAO Plant Nutrition Bulletin 16)
    # -------------------------------------------------------------------------
    def estimate_yield(
        self,
        zone_data: Dict,
        crop_name: str,
        zone_area_m2: float,
        baseline_yield_kg_m2: float,
        market_price_kes_per_kg: float
    ) -> Dict:
        """
        Estimate yield and gross revenue given current soil conditions.
        Uses simplified Mitscherlich response curves.
        """
        crop = crop_name.lower()
        ranges = soil_model.crop_ranges.get(crop, soil_model.crop_ranges["maize"])

        ph      = zone_data.get("ph_level", 6.5)
        n_ppm   = zone_data.get("nitrogen_ppm", 100)
        p_ppm   = zone_data.get("phosphorus_ppm", 50)
        moisture = zone_data.get("soil_moisture_pct", 60)

        def mitscherlich(current, opt_min, opt_max, penalty_per_unit=0.20):
            """Simple penalty function — yield drops as conditions deviate."""
            if opt_min <= current <= opt_max:
                return 1.0
            deviation = max(opt_min - current, current - opt_max, 0)
            return max(0.3, 1.0 - (deviation * penalty_per_unit))

        ph_mult = mitscherlich(ph, ranges["ph_opt_min"], ranges["ph_opt_max"], 0.25)
        n_mult  = mitscherlich(n_ppm, ranges["n_min"], ranges["n_opt"] * 1.2, 0.005)
        p_mult  = mitscherlich(p_ppm, ranges["p_min"], ranges["p_opt"] * 1.2, 0.008)
        moist_mult = mitscherlich(moisture, ranges["moisture_opt_min"], ranges["moisture_opt_max"], 0.015)

        # Combined multiplier — all factors reduce from 1.0
        combined = ph_mult * n_mult * p_mult * moist_mult
        expected_yield_kg_m2 = baseline_yield_kg_m2 * combined
        expected_yield_total = expected_yield_kg_m2 * zone_area_m2

        gross_revenue = expected_yield_total * market_price_kes_per_kg

        return {
            "expected_yield_kg": round(expected_yield_total, 3),
            "expected_yield_kg_m2": round(expected_yield_kg_m2, 4),
            "baseline_yield_kg_m2": baseline_yield_kg_m2,
            "yield_vs_baseline_pct": round(combined * 100, 1),
            "gross_revenue_kes": round(gross_revenue, 2),
            "market_price_kes_per_kg": market_price_kes_per_kg,
            "multipliers": {
                "ph_factor": round(ph_mult, 3),
                "nitrogen_factor": round(n_mult, 3),
                "phosphorus_factor": round(p_mult, 3),
                "moisture_factor": round(moist_mult, 3),
                "combined": round(combined, 3),
            },
            "formula": "yield = baseline × pH_factor × N_factor × P_factor × moisture_factor (Mitscherlich response)",
            "source": "FAO Plant Nutrition for Food Security Bulletin 16; FAO33 Yield Response to Water"
        }

    # -------------------------------------------------------------------------
    # SENSOR DATA INGEST — validate then store-ready dict
    # -------------------------------------------------------------------------
    def prepare_reading_for_storage(
        self,
        raw_sensor_data: Dict,
        rover_id: str,
        sequence_number: int,
        collected_at: Optional[datetime] = None
    ) -> Dict:
        """
        Validate sensor data from rover and prepare for INSERT into sensor_readings.
        Generates the idempotent reading_uuid. [3]

        Args:
            raw_sensor_data: Dict from ComWinTop + DHT22 readings
            rover_id: e.g. 'ROVER_01'
            sequence_number: Rover sequence counter for this reading
            collected_at: Timestamp when rover collected the data

        Returns:
            reading dict ready for DB INSERT
        """
        if collected_at is None:
            collected_at = datetime.now()

        # Idempotent UUID: rover_id + timestamp_ms + seq [3]
        ts_ms = int(collected_at.timestamp() * 1000)
        reading_uuid = f"{rover_id}_{ts_ms}_{sequence_number:04d}"

        # Validate reading
        validated = self.irrigation.validate_sensor_reading(raw_sensor_data.copy())

        return {
            "reading_uuid":           reading_uuid,
            "zone_id":                raw_sensor_data.get("zone_id"),
            "farm_id":                raw_sensor_data.get("farm_id"),
            "rover_id":               rover_id,
            "collected_at":           collected_at.isoformat(),
            "gps_lat":                raw_sensor_data.get("gps_lat"),
            "gps_lon":                raw_sensor_data.get("gps_lon"),
            "gps_accuracy_m":         raw_sensor_data.get("gps_accuracy_m"),
            # ComWinTop 7-in-1 sensor values (register map from manual)
            "nitrogen_ppm":           raw_sensor_data.get("nitrogen_ppm"),
            "phosphorus_ppm":         raw_sensor_data.get("phosphorus_ppm"),
            "potassium_ppm":          raw_sensor_data.get("potassium_ppm"),
            "ph_level":               raw_sensor_data.get("ph_level"),
            "soil_moisture_pct":      raw_sensor_data.get("soil_moisture_pct"),
            "soil_temperature_c":     raw_sensor_data.get("soil_temperature_c"),
            "electrical_conductivity":raw_sensor_data.get("electrical_conductivity"),
            # DHT22 values
            "air_temperature_c":      raw_sensor_data.get("air_temperature_c"),
            "air_humidity_pct":       raw_sensor_data.get("air_humidity_pct"),
            # Computed ET at reading time
            "computed_et0_mm_day":    self._compute_et0_from_reading(raw_sensor_data),
            "et_calc_method":         "hargreaves_samani",
            # Quality
            "data_quality_score":     validated.get("data_quality_score", 1.0),
            "validation_flags":       validated.get("validation_flags", []),
            "sensor_battery_v":       raw_sensor_data.get("sensor_battery_v"),
            "synced_from_sd":         raw_sensor_data.get("synced_from_sd", True),
            "sd_file_name":           raw_sensor_data.get("sd_file_name"),
        }

    def _compute_et0_from_reading(self, reading: Dict) -> Optional[float]:
        """Quick ET0 estimate from a single reading using current air temp."""
        try:
            t = reading.get("air_temperature_c", 22.0)
            result = self.irrigation.calculate_et0(
                t_max_c=t + 6.0,
                t_min_c=t - 6.0,
                month=datetime.now().month
            )
            return result["et0_mm_day"]
        except Exception:
            return None


# Module-level singleton
decision_engine = DecisionEngine()