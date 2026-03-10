"""
YieldVision Irrigation Engine
All math traceable to FAO Irrigation and Drainage Paper No. 56 (FAO56)
Allen, R.G., Pereira, L.S., Raes, D., & Smith, M. (1998)

Key formulas used:
  ET0  — Hargreaves-Samani (FAO56 Ch.3, Eq. 52)
  ETc  — ET0 × Kc  (FAO56 Ch.6)
  Kc   — by crop and growth stage (FAO56 Table 12)
  TAW  — (FC% - WP%) × Bd × root_depth (FAO56 Eq. 82)
  RAW  — p × TAW  (FAO56 Eq. 83), p from FAO56 Table 22
  Net irrigation depth — (FC - θ) × Bd × Zr (FAO56 Eq. 99)
  Days until stress — RAW / ETc  (FAO56 Ch.8)
"""

import math
from datetime import datetime, date
from typing import Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS FROM FAO56
# =============================================================================

# Soil type properties — FAO56 Table 1
# field_capacity_pct, wilting_point_pct, bulk_density_g_cm3, drainage_factor
SOIL_TYPE_PARAMS: Dict[str, Dict] = {
    "sandy": {
        "field_capacity_pct": 12.0,
        "wilting_point_pct":   5.0,
        "bulk_density":        1.65,
        "drainage_factor":     1.35,
        "source": "FAO56 Table 1"
    },
    "sandy_loam": {
        "field_capacity_pct": 22.0,
        "wilting_point_pct":   9.0,
        "bulk_density":        1.45,
        "drainage_factor":     1.25,
        "source": "FAO56 Table 1"
    },
    "loam": {
        "field_capacity_pct": 31.0,
        "wilting_point_pct":  14.0,
        "bulk_density":        1.25,
        "drainage_factor":     1.20,
        "source": "FAO56 Table 1"
    },
    "clay_loam": {
        "field_capacity_pct": 38.0,
        "wilting_point_pct":  20.0,
        "bulk_density":        1.15,
        "drainage_factor":     1.15,
        "source": "FAO56 Table 1"
    },
    "clay": {
        "field_capacity_pct": 45.0,
        "wilting_point_pct":  25.0,
        "bulk_density":        1.10,
        "drainage_factor":     1.10,
        "source": "FAO56 Table 1"
    },
}

# Crop coefficients by growth stage — FAO56 Table 12
# depletion_fraction_p — FAO56 Table 22
# root_depth_cm — FAO56 Table 1 (typical values)
CROP_FAO_PARAMS: Dict[str, Dict] = {
    "maize": {
        "kc_initial":   0.30,
        "kc_mid":       1.20,
        "kc_end":       0.35,
        "depletion_p":  0.55,
        "root_depth_cm": 60.0,
        "days_initial":  20,
        "days_dev":      35,
        "days_mid":      45,
        "days_late":     30,
        "source": "FAO56 Table 12, Table 22"
    },
    "beans": {
        "kc_initial":   0.30,
        "kc_mid":       1.10,
        "kc_end":       0.30,
        "depletion_p":  0.45,
        "root_depth_cm": 50.0,
        "days_initial":  15,
        "days_dev":      25,
        "days_mid":      25,
        "days_late":     15,
        "source": "FAO56 Table 12, Table 22"
    },
    "potatoes": {
        "kc_initial":   0.40,
        "kc_mid":       1.15,
        "kc_end":       0.75,
        "depletion_p":  0.35,
        "root_depth_cm": 40.0,
        "days_initial":  25,
        "days_dev":      30,
        "days_mid":      30,
        "days_late":     15,
        "source": "FAO56 Table 12, Table 22"
    },
    "tomatoes": {
        "kc_initial":   0.40,
        "kc_mid":       1.15,
        "kc_end":       0.70,
        "depletion_p":  0.40,
        "root_depth_cm": 50.0,
        "days_initial":  30,
        "days_dev":      40,
        "days_mid":      40,
        "days_late":     25,
        "source": "FAO56 Table 12, Table 22"
    },
    "kale": {
        "kc_initial":   0.40,
        "kc_mid":       1.00,
        "kc_end":       0.95,
        "depletion_p":  0.45,
        "root_depth_cm": 35.0,
        "days_initial":  15,
        "days_dev":      20,
        "days_mid":      90,
        "days_late":     0,   # continuous harvest, no late stage
        "source": "FAO56 Table 12, Table 22"
    },
}

# Extraterrestrial radiation Ra (MJ/m2/day) for Kenya (latitude 0°–4°S)
# Source: FAO56 Table 2.6 / Annex 2, monthly values for equatorial Africa
# Using 1°S as representative for Kenyan highlands
RA_BY_MONTH: Dict[int, float] = {
    1: 36.8,   # January
    2: 37.9,   # February
    3: 37.4,   # March
    4: 35.3,   # April
    5: 32.6,   # May
    6: 31.4,   # June
    7: 31.8,   # July
    8: 33.6,   # August
    9: 36.0,   # September
    10: 37.2,  # October
    11: 36.6,  # November
    12: 36.0,  # December
}


# =============================================================================
# CORE IRRIGATION ENGINE
# =============================================================================

class IrrigationEngine:
    """
    FAO56-grounded irrigation scheduling engine.
    Every calculation stores a full trace of inputs, formula, and source.
    """

    def __init__(self):
        self.soil_params = SOIL_TYPE_PARAMS
        self.crop_params = CROP_FAO_PARAMS

    # -------------------------------------------------------------------------
    # 1. ET0 CALCULATION — Hargreaves-Samani
    #    FAO56 Chapter 3, Equation 52
    # -------------------------------------------------------------------------
    def calculate_et0(
        self,
        t_max_c: float,
        t_min_c: float,
        t_mean_c: Optional[float] = None,
        month: Optional[int] = None
    ) -> Dict:
        """
        Calculate reference evapotranspiration (ET0) using Hargreaves-Samani.

        Formula: ET0 = 0.0023 × (Tmean + 17.8) × (Tmax - Tmin)^0.5 × Ra
        Source: FAO56 Chapter 3, Equation 52

        Args:
            t_max_c: Daily max air temperature (°C) from DHT22
            t_min_c: Daily min air temperature (°C) from DHT22
            t_mean_c: Mean temperature (if None, computed as average)
            month: Calendar month (1-12) for Ra lookup; defaults to current month

        Returns:
            Dict with et0_mm_day and full calculation trace
        """
        if t_mean_c is None:
            t_mean_c = (t_max_c + t_min_c) / 2.0

        if month is None:
            month = datetime.now().month

        ra = RA_BY_MONTH.get(month, 35.0)

        # Hargreaves-Samani formula — FAO56 Eq. 52
        temp_range = max(t_max_c - t_min_c, 0.0)
        et0 = 0.0023 * (t_mean_c + 17.8) * math.sqrt(temp_range) * ra
        et0 = max(et0, 0.1)  # floor at 0.1 mm/day — physically unreasonable below this

        return {
            "et0_mm_day": round(et0, 3),
            "formula": "ET0 = 0.0023 × (Tmean + 17.8) × (Tmax - Tmin)^0.5 × Ra",
            "inputs": {
                "t_max_c": t_max_c,
                "t_min_c": t_min_c,
                "t_mean_c": round(t_mean_c, 2),
                "ra_mj_m2_day": ra,
                "month": month,
            },
            "source": "FAO56 Chapter 3, Equation 52 (Hargreaves-Samani)"
        }

    # -------------------------------------------------------------------------
    # 2. CROP COEFFICIENT — Kc by growth stage
    #    FAO56 Table 12
    # -------------------------------------------------------------------------
    def get_kc(self, crop_name: str, days_since_planting: int) -> Dict:
        """
        Get crop coefficient (Kc) for current growth stage.
        Source: FAO56 Table 12

        Args:
            crop_name: 'maize', 'beans', 'potatoes', 'tomatoes', 'kale'
            days_since_planting: Integer days elapsed since planting

        Returns:
            Dict with kc value, stage name, and source
        """
        crop = crop_name.lower()
        params = self.crop_params.get(crop, self.crop_params["maize"])

        d_init = params["days_initial"]
        d_dev  = params["days_dev"]
        d_mid  = params["days_mid"]
        d_late = params["days_late"]

        kc_init = params["kc_initial"]
        kc_mid  = params["kc_mid"]
        kc_end  = params["kc_end"]

        # Determine stage and interpolate Kc — FAO56 Ch.6 procedure
        if days_since_planting <= d_init:
            stage = "initial"
            kc = kc_init

        elif days_since_planting <= d_init + d_dev:
            stage = "development"
            # Linear interpolation between kc_init and kc_mid
            progress = (days_since_planting - d_init) / d_dev
            kc = kc_init + progress * (kc_mid - kc_init)

        elif days_since_planting <= d_init + d_dev + d_mid:
            stage = "mid"
            kc = kc_mid

        elif days_since_planting <= d_init + d_dev + d_mid + d_late:
            stage = "late"
            progress = (days_since_planting - d_init - d_dev - d_mid) / max(d_late, 1)
            kc = kc_mid + progress * (kc_end - kc_mid)

        else:
            stage = "mature"
            kc = kc_end

        return {
            "kc": round(kc, 3),
            "growth_stage": stage,
            "days_since_planting": days_since_planting,
            "source": f"FAO56 Table 12 ({crop})"
        }

    # -------------------------------------------------------------------------
    # 3. CROP ET — ETc = ET0 × Kc
    #    FAO56 Chapter 6
    # -------------------------------------------------------------------------
    def calculate_etc(self, et0_mm_day: float, kc: float) -> Dict:
        """
        Calculate crop evapotranspiration.
        Formula: ETc = ET0 × Kc
        Source: FAO56 Chapter 6, Equation 58
        """
        etc = et0_mm_day * kc
        return {
            "etc_mm_day": round(etc, 3),
            "et0_mm_day": et0_mm_day,
            "kc": kc,
            "formula": "ETc = ET0 × Kc",
            "source": "FAO56 Chapter 6, Equation 58"
        }

    # -------------------------------------------------------------------------
    # 4. IRRIGATION VOLUME CALCULATION
    #    FAO56 Chapter 8, Equation 99
    # -------------------------------------------------------------------------
    def calculate_irrigation_volume(
        self,
        current_moisture_pct: float,
        soil_type: str,
        zone_area_m2: float,
        root_depth_cm: float,
        drainage_factor: Optional[float] = None
    ) -> Dict:
        """
        Calculate how many liters to apply to bring soil to field capacity.

        Formula: Net irrigation depth (mm) = (FC% - θ%) × Bd × Zr (cm) × 10
        Then convert mm to liters: liters = depth_mm × area_m2
        Apply drainage_factor for losses.

        Source: FAO56 Chapter 8, Equation 99

        Args:
            current_moisture_pct: Current soil moisture % (from ComWinTop sensor)
            soil_type: 'sandy'/'loam'/'clay' etc.
            zone_area_m2: Zone area in square meters
            root_depth_cm: Effective root depth in cm (from crop_varieties table)
            drainage_factor: Override drainage loss factor (default from soil table)

        Returns:
            Dict with water_needed_liters and full calculation trace
        """
        soil = self.soil_params.get(soil_type, self.soil_params["loam"])
        fc = soil["field_capacity_pct"]
        wp = soil["wilting_point_pct"]
        bd = soil["bulk_density"]
        df = drainage_factor if drainage_factor else soil["drainage_factor"]

        # Soil moisture deficit
        deficit_pct = max(fc - current_moisture_pct, 0.0)

        if deficit_pct <= 0:
            return {
                "water_needed_liters": 0.0,
                "already_at_capacity": True,
                "current_moisture_pct": current_moisture_pct,
                "field_capacity_pct": fc,
                "message": "Soil already at or above field capacity"
            }

        # Net irrigation depth (mm) — FAO56 Eq. 99
        # depth_mm = deficit% × bulk_density × root_depth_cm × 10
        # (×10 converts g/cm3 × cm × % to mm)
        depth_mm = (deficit_pct / 100.0) * bd * root_depth_cm * 10.0

        # Convert mm depth over zone area to liters
        # 1 mm over 1 m2 = 1 liter
        net_liters = depth_mm * zone_area_m2

        # Apply drainage factor (accounts for percolation losses)
        gross_liters = net_liters * df

        return {
            "water_needed_liters": round(gross_liters, 2),
            "net_liters_no_losses": round(net_liters, 2),
            "depth_mm": round(depth_mm, 2),
            "deficit_pct": round(deficit_pct, 2),
            "formula": "depth_mm = (FC% - θ%) × Bd × Zr × 10; liters = depth_mm × area_m2 × drainage_factor",
            "inputs": {
                "current_moisture_pct": current_moisture_pct,
                "field_capacity_pct": fc,
                "wilting_point_pct": wp,
                "bulk_density_g_cm3": bd,
                "root_depth_cm": root_depth_cm,
                "zone_area_m2": zone_area_m2,
                "drainage_factor": df,
                "soil_type": soil_type,
            },
            "source": "FAO56 Chapter 8, Equation 99"
        }

    # -------------------------------------------------------------------------
    # 5. DAYS UNTIL STRESS
    #    FAO56 Chapter 8
    # -------------------------------------------------------------------------
    def days_until_stress(
        self,
        current_moisture_pct: float,
        soil_type: str,
        root_depth_cm: float,
        etc_mm_day: float,
        depletion_p: float
    ) -> Dict:
        """
        How many days before soil moisture drops to stress threshold.

        Formula:
          TAW = (FC% - WP%) × Bd × Zr × 10  [mm]  — FAO56 Eq. 82
          RAW = p × TAW                              — FAO56 Eq. 83
          Current depletion = (FC% - θ%) × Bd × Zr × 10
          Days until stress = (RAW - current_depletion) / ETc

        Args:
            current_moisture_pct: Current soil moisture %
            soil_type: Soil type string
            root_depth_cm: Root depth in cm
            etc_mm_day: Crop ET in mm/day
            depletion_p: Depletion fraction p (from FAO56 Table 22)

        Returns:
            Dict with days_until_stress and trace
        """
        soil = self.soil_params.get(soil_type, self.soil_params["loam"])
        fc = soil["field_capacity_pct"]
        wp = soil["wilting_point_pct"]
        bd = soil["bulk_density"]

        # Total available water (mm) — FAO56 Eq. 82
        taw = ((fc - wp) / 100.0) * bd * root_depth_cm * 10.0

        # Readily available water (mm) — FAO56 Eq. 83
        raw = depletion_p * taw

        # Current soil water depletion (mm)
        current_depletion = max(((fc - current_moisture_pct) / 100.0) * bd * root_depth_cm * 10.0, 0.0)

        # Water remaining before stress threshold
        buffer_mm = max(raw - current_depletion, 0.0)

        if etc_mm_day <= 0:
            days = 999.0
        else:
            days = buffer_mm / etc_mm_day

        # Stress status
        if current_moisture_pct <= wp:
            stress_status = "WILTING — irrigate immediately"
        elif current_depletion >= raw:
            stress_status = "STRESS — irrigate today"
        elif days <= 1:
            stress_status = "URGENT — irrigate within 24 hours"
        elif days <= 3:
            stress_status = "SOON — irrigate within 3 days"
        else:
            stress_status = f"OK — next irrigation in ~{days:.1f} days"

        return {
            "days_until_stress": round(days, 1),
            "stress_status": stress_status,
            "taw_mm": round(taw, 2),
            "raw_mm": round(raw, 2),
            "current_depletion_mm": round(current_depletion, 2),
            "buffer_remaining_mm": round(buffer_mm, 2),
            "formula": "TAW = (FC-WP)×Bd×Zr×10; RAW = p×TAW; days = (RAW - depletion) / ETc",
            "inputs": {
                "current_moisture_pct": current_moisture_pct,
                "field_capacity_pct": fc,
                "wilting_point_pct": wp,
                "bulk_density": bd,
                "root_depth_cm": root_depth_cm,
                "etc_mm_day": etc_mm_day,
                "depletion_p": depletion_p,
            },
            "source": "FAO56 Chapter 8, Equations 82, 83"
        }

    # -------------------------------------------------------------------------
    # 6. FULL IRRIGATION SCHEDULE — combines all above
    # -------------------------------------------------------------------------
    def generate_irrigation_schedule(
        self,
        zone_data: Dict,
        crop_name: str,
        days_since_planting: int,
        soil_type: str,
        zone_area_m2: float = 4.0,
        root_depth_override_cm: Optional[float] = None
    ) -> Dict:
        """
        Generate a complete irrigation recommendation for one zone.

        Args:
            zone_data: Dict from sensor_readings — must include:
                soil_moisture_pct, air_temperature_c, air_humidity_pct
                (Tmax and Tmin estimated from air_temperature_c ± typical diurnal range
                 when only a single reading is available)
            crop_name: Crop in this zone
            days_since_planting: Days elapsed since planting
            soil_type: Soil classification
            zone_area_m2: Zone area
            root_depth_override_cm: Override if crop_varieties table has a better value

        Returns:
            Full recommendation dict with calculation trace
        """
        crop_lower = crop_name.lower()
        crop_fao = self.crop_params.get(crop_lower, self.crop_params["maize"])

        # --- Temperature inputs ---
        # DHT22 gives current air temp. Estimate daily range for Hargreaves-Samani.
        # Kenya highlands diurnal range is typically 8-14°C.
        t_current = zone_data.get("air_temperature_c", 22.0)
        t_max = zone_data.get("air_temp_max_c", t_current + 6.0)   # +6 estimate
        t_min = zone_data.get("air_temp_min_c", t_current - 6.0)   # -6 estimate

        # --- ET0 ---
        et0_result = self.calculate_et0(
            t_max_c=t_max,
            t_min_c=t_min,
            month=datetime.now().month
        )

        # --- Kc and growth stage ---
        kc_result = self.get_kc(crop_lower, days_since_planting)

        # --- ETc ---
        etc_result = self.calculate_etc(et0_result["et0_mm_day"], kc_result["kc"])

        # --- Root depth ---
        root_depth = root_depth_override_cm or crop_fao["root_depth_cm"]

        # --- Irrigation volume ---
        moisture = zone_data.get("soil_moisture_pct", 20.0)
        vol_result = self.calculate_irrigation_volume(
            current_moisture_pct=moisture,
            soil_type=soil_type,
            zone_area_m2=zone_area_m2,
            root_depth_cm=root_depth
        )

        # --- Days until stress ---
        stress_result = self.days_until_stress(
            current_moisture_pct=moisture,
            soil_type=soil_type,
            root_depth_cm=root_depth,
            etc_mm_day=etc_result["etc_mm_day"],
            depletion_p=crop_fao["depletion_p"]
        )

        # --- Urgency ---
        days = stress_result["days_until_stress"]
        if days <= 0 or moisture <= self.soil_params.get(soil_type, {}).get("wilting_point_pct", 14):
            urgency = "CRITICAL"
        elif days <= 1:
            urgency = "HIGH"
        elif days <= 3:
            urgency = "MEDIUM"
        else:
            urgency = "LOW"

        # --- Plain language action ---
        water_l = vol_result["water_needed_liters"]
        if water_l <= 0:
            action = "No irrigation needed — soil is at field capacity."
        else:
            action = (
                f"Apply {water_l:.1f} litres to zone. "
                f"Next irrigation needed in ~{days:.1f} days."
            )

        return {
            "recommendation_type": "irrigate",
            "action_description": action,
            "action_quantity": water_l,
            "action_unit": "liters",
            "urgency_level": urgency,
            "next_irrigation_days": round(days, 1),

            # Full calculation trace stored in DB
            "calculation_breakdown": {
                "crop": crop_lower,
                "growth_stage": kc_result["growth_stage"],
                "days_since_planting": days_since_planting,
                "et0": et0_result,
                "kc": kc_result,
                "etc": etc_result,
                "volume": vol_result,
                "stress": stress_result,
                "data_sources": [
                    "FAO56 Ch.3 Eq.52 (Hargreaves-Samani ET0)",
                    "FAO56 Table 12 (Kc by growth stage)",
                    "FAO56 Table 22 (depletion fraction p)",
                    "FAO56 Ch.8 Eq.99 (irrigation depth)",
                    "FAO56 Ch.8 Eq.82-83 (TAW, RAW)",
                    "FAO56 Table 1 (soil field capacity)",
                ]
            }
        }

    # -------------------------------------------------------------------------
    # 7. VALIDATE SENSOR READING (sanity checks before using in calc)
    # -------------------------------------------------------------------------
    def validate_sensor_reading(self, reading: Dict) -> Dict:
        """
        Check sensor reading for physically impossible or suspicious values.
        Returns the reading with data_quality_score and validation_flags added.
        """
        flags = []
        score = 1.0

        moisture = reading.get("soil_moisture_pct")
        ec       = reading.get("electrical_conductivity")
        ph       = reading.get("ph_level")
        nitrogen = reading.get("nitrogen_ppm")
        temp_soil = reading.get("soil_temperature_c")
        temp_air  = reading.get("air_temperature_c")

        # Physical range checks
        if moisture is not None:
            if not (0 <= moisture <= 100):
                flags.append("MOISTURE_OUT_OF_RANGE")
                score -= 0.3

        if ph is not None:
            if not (3.0 <= ph <= 9.0):
                flags.append("PH_OUT_OF_SENSOR_RANGE")
                score -= 0.4
            elif ph < 4.0:
                flags.append("PH_EXTREMELY_ACIDIC — verify probe calibration")
                score -= 0.1

        if ec is not None and nitrogen is not None:
            if ec > 800 and nitrogen < 30:
                flags.append("HIGH_EC_LOW_NPK — possible sensor error or recent irrigation")
                score -= 0.15

        if temp_soil is not None and moisture is not None:
            if moisture > 80 and temp_soil > 30:
                flags.append("HIGH_MOISTURE_HIGH_TEMP — unusual, verify probe contact")
                score -= 0.1

        if temp_air is not None and temp_soil is not None:
            if abs(temp_air - temp_soil) > 20:
                flags.append("LARGE_AIR_SOIL_TEMP_DIFFERENCE — verify DHT22 placement")
                score -= 0.1

        reading["data_quality_score"] = max(round(score, 2), 0.0)
        reading["validation_flags"] = flags
        return reading


# Module-level singleton
irrigation_engine = IrrigationEngine()