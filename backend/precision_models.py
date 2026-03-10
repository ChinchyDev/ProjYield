"""
YieldVision Precision Models
YieldSoil — soil amendment recommendations (NPK + pH correction)
YieldSeed — crop variety suitability scoring

Research sources:
  NPK deficiency math:   IFDC Fertilizer Use by Crop in Kenya (2019)
  pH correction:         KALRO Soil Acidity and Liming Handbook for Kenya (2023)
  Fertilizer products:   IFDC Fertilizer Quality Assessment Kenya (2019)
  Yield response:        FAO Plant Nutrition for Food Security, Bulletin 16
  Crop suitability:      ECOCROP (FAO), KALRO Crop Variety Catalogue 2023
"""

import math
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


# =============================================================================
# FERTILIZER PRODUCTS — real Kenyan market products
# Source: IFDC Kenya 2019, Yara Kenya 2024, MEA Kenya 2024
# =============================================================================
FERTILIZER_PRODUCTS = {
    "CAN": {
        "n_pct": 26.0, "p_pct": 0.0, "k_pct": 0.0,
        "price_kes_per_50kg": 2800,
        "type": "nitrogen",
        "use": "Top-dress nitrogen. Apply at vegetative stage.",
        "source": "IFDC Kenya 2019, Yara Kenya 2024"
    },
    "Urea": {
        "n_pct": 46.0, "p_pct": 0.0, "k_pct": 0.0,
        "price_kes_per_50kg": 3200,
        "type": "nitrogen",
        "use": "High-N correction. Apply carefully — burning risk.",
        "source": "IFDC Kenya 2019"
    },
    "DAP": {
        "n_pct": 18.0, "p_pct": 46.0, "k_pct": 0.0,
        "price_kes_per_50kg": 3800,
        "type": "npk_blend",
        "use": "Basal application at planting. High P for root development.",
        "source": "IFDC Kenya 2019, Yara Kenya 2024"
    },
    "NPK 17:17:17": {
        "n_pct": 17.0, "p_pct": 17.0, "k_pct": 17.0,
        "price_kes_per_50kg": 3500,
        "type": "npk_blend",
        "use": "Balanced application when all three nutrients are deficient.",
        "source": "MEA Kenya 2024"
    },
    "MOP": {
        "n_pct": 0.0, "p_pct": 0.0, "k_pct": 60.0,
        "price_kes_per_50kg": 3000,
        "type": "potassium",
        "use": "Potassium correction. Good for tuber crops (potatoes).",
        "source": "IFDC Kenya 2019"
    },
    "Mavuno Planting": {
        "n_pct": 10.0, "p_pct": 26.0, "k_pct": 10.0,
        "price_kes_per_50kg": 3600,
        "type": "npk_blend",
        "use": "MEA planting fertilizer. Well-suited for Kenyan soils.",
        "source": "MEA Kenya 2024"
    },
    "Mavuno Top": {
        "n_pct": 25.0, "p_pct": 5.0, "k_pct": 5.0,
        "price_kes_per_50kg": 3300,
        "type": "npk_blend",
        "use": "Top-dress at vegetative stage. Nitrogen-heavy for leaf growth.",
        "source": "MEA Kenya 2024"
    },
    "Agricultural Lime": {
        "n_pct": 0.0, "p_pct": 0.0, "k_pct": 0.0,
        "caco3_pct": 85.0,
        "price_kes_per_50kg": 800,
        "type": "lime",
        "use": "pH correction for acidic soils. Apply 3-6 months before planting.",
        "source": "KALRO Liming Guide 2023"
    },
}

# =============================================================================
# SOIL TYPE LIME FACTORS
# Source: KALRO Soil Acidity and Liming Handbook for Kenya (2023)
# Tonnes of agricultural lime per hectare per pH unit to correct
# =============================================================================
LIME_FACTORS_TONNES_HA_PER_PH_UNIT = {
    "sandy":      1.75,
    "sandy_loam": 2.50,
    "loam":       3.75,
    "clay_loam":  5.25,
    "clay":       7.00,
}

# Bulk density for unit conversions (g/cm3) — matches irrigation_engine
BULK_DENSITY = {
    "sandy": 1.65, "sandy_loam": 1.45, "loam": 1.25, "clay_loam": 1.15, "clay": 1.10
}

# =============================================================================
# CROP VARIETY OPTIMAL RANGES
# Loaded from DB at runtime; these are fallback Layer 1 values
# Source: KALRO, IFDC, ECOCROP
# =============================================================================
CROP_OPTIMAL_RANGES = {
    "maize": {
        "ph_min": 5.5, "ph_max": 7.5, "ph_opt_min": 6.0, "ph_opt_max": 7.0,
        "n_opt": 150, "p_opt": 60, "k_opt": 120,
        "n_min": 80, "p_min": 30, "k_min": 80,
        "moisture_opt_min": 50, "moisture_opt_max": 80,
        "nitrogen_fixing": False,
        "source": "KALRO, IFDC Kenya 2019"
    },
    "beans": {
        "ph_min": 5.5, "ph_max": 7.0, "ph_opt_min": 6.0, "ph_opt_max": 6.8,
        "n_opt": 60, "p_opt": 50, "k_opt": 80,
        "n_min": 20, "p_min": 30, "k_min": 50,
        "moisture_opt_min": 45, "moisture_opt_max": 75,
        "nitrogen_fixing": True,   # rhizobia fix N — don't over-apply N fertilizer
        "source": "KALRO Beans Programme 2023"
    },
    "potatoes": {
        "ph_min": 5.0, "ph_max": 6.5, "ph_opt_min": 5.5, "ph_opt_max": 6.2,
        "n_opt": 150, "p_opt": 80, "k_opt": 250,
        "n_min": 80, "p_min": 50, "k_min": 150,
        "moisture_opt_min": 55, "moisture_opt_max": 85,
        "nitrogen_fixing": False,
        "source": "KALRO Tigoni 2023, IFDC Kenya 2019"
    },
    "tomatoes": {
        "ph_min": 5.8, "ph_max": 7.0, "ph_opt_min": 6.0, "ph_opt_max": 6.8,
        "n_opt": 180, "p_opt": 80, "k_opt": 200,
        "n_min": 100, "p_min": 50, "k_min": 120,
        "moisture_opt_min": 60, "moisture_opt_max": 85,
        "nitrogen_fixing": False,
        "source": "Syngenta Kenya 2024, IFDC Kenya 2019"
    },
    "kale": {
        "ph_min": 5.5, "ph_max": 7.5, "ph_opt_min": 6.0, "ph_opt_max": 7.0,
        "n_opt": 160, "p_opt": 50, "k_opt": 130,
        "n_min": 80, "p_min": 30, "k_min": 80,
        "moisture_opt_min": 50, "moisture_opt_max": 80,
        "nitrogen_fixing": False,
        "source": "KALRO Horticulture 2023"
    },
}


# =============================================================================
# YIELD SOIL MODEL
# =============================================================================

class YieldSoilModel:
    """
    Soil amendment recommendation engine.
    Translates sensor readings into specific product recommendations in KES.

    No ML training required — Layer 1 knowledge uses published science directly.
    ML layer added later once farm-specific data accumulates.
    """

    def __init__(self):
        self.fertilizers = FERTILIZER_PRODUCTS
        self.lime_factors = LIME_FACTORS_TONNES_HA_PER_PH_UNIT
        self.bulk_density = BULK_DENSITY
        self.crop_ranges = CROP_OPTIMAL_RANGES

    # -------------------------------------------------------------------------
    # pH HARD GATE — checks before any NPK recommendation
    # If pH is critically wrong, NPK is blocked. Farmer wastes money otherwise.
    # Source: KALRO Liming Guide 2023
    # -------------------------------------------------------------------------
    def check_ph_gate(self, ph: float, crop_name: str) -> Dict:
        """
        pH hard gate — must pass before any NPK recommendation is generated.
        If pH outside crop range by > 0.5 units, gate is ACTIVE and NPK blocked.

        Returns:
            Dict with gate_active bool, reason, and lime recommendation if active
        """
        crop = crop_name.lower()
        ranges = self.crop_ranges.get(crop, self.crop_ranges["maize"])
        ph_min = ranges["ph_min"]
        ph_max = ranges["ph_max"]

        too_low  = ph < (ph_min - 0.5)
        too_high = ph > (ph_max + 0.5)

        if not too_low and not too_high:
            return {
                "gate_active": False,
                "ph_status": "acceptable",
                "current_ph": ph,
                "crop_ph_range": [ph_min, ph_max]
            }

        if too_low:
            direction = "too acidic"
            correction = "Add agricultural lime to raise pH"
        else:
            direction = "too alkaline"
            correction = "Acidify with sulfur or organic matter"

        return {
            "gate_active": True,
            "ph_status": direction,
            "do_not_fertilize_until": True,
            "reason": (
                f"Soil pH {ph:.1f} is {direction} for {crop_name} "
                f"(needs {ph_min}–{ph_max}). At this pH, applied fertilizer "
                f"cannot be absorbed. Correct pH first."
            ),
            "correction": correction,
            "current_ph": ph,
            "crop_ph_range": [ph_min, ph_max],
            "source": "KALRO Liming Guide 2023"
        }

    # -------------------------------------------------------------------------
    # LIME REQUIREMENT CALCULATION
    # Source: KALRO Soil Acidity and Liming Handbook for Kenya (2023)
    # -------------------------------------------------------------------------
    def calculate_lime_needed(
        self,
        current_ph: float,
        target_ph: float,
        soil_type: str,
        zone_area_m2: float
    ) -> Dict:
        """
        Calculate lime needed to raise pH to target.

        Formula: lime_t_ha = (target_pH - current_pH) × lime_factor
        Convert to kg for zone: kg = (t_ha × 1000) / 10000 × area_m2

        Source: KALRO Soil Acidity and Liming Handbook for Kenya (2023)
        """
        ph_deficit = max(target_ph - current_ph, 0.0)
        if ph_deficit <= 0:
            return {"lime_needed_kg": 0.0, "already_at_target": True}

        factor = self.lime_factors.get(soil_type, self.lime_factors["loam"])
        tonnes_per_ha = ph_deficit * factor
        kg_per_m2 = (tonnes_per_ha * 1000) / 10000
        kg_for_zone = kg_per_m2 * zone_area_m2

        # Cost
        lime = self.fertilizers["Agricultural Lime"]
        cost_kes = (kg_for_zone / 50) * lime["price_kes_per_50kg"]

        return {
            "lime_needed_kg": round(kg_for_zone, 3),
            "product": "Agricultural Lime",
            "cost_kes": round(cost_kes, 2),
            "formula": "lime_t/ha = (target_pH - current_pH) × lime_factor; kg = (t/ha × 1000 / 10000) × area_m2",
            "inputs": {
                "current_ph": current_ph,
                "target_ph": target_ph,
                "ph_deficit": round(ph_deficit, 2),
                "soil_type": soil_type,
                "lime_factor_t_ha_per_unit": factor,
                "tonnes_per_ha": round(tonnes_per_ha, 3),
                "zone_area_m2": zone_area_m2,
            },
            "source": "KALRO Soil Acidity and Liming Handbook for Kenya (2023)"
        }

    # -------------------------------------------------------------------------
    # NPK DEFICIT CALCULATION
    # Source: IFDC Fertilizer Use by Crop in Kenya (2019)
    # CABI Soil Fertility in Africa
    # -------------------------------------------------------------------------
    def calculate_npk_deficit(
        self,
        current_n: float,
        current_p: float,
        current_k: float,
        crop_name: str,
        soil_type: str,
        zone_area_m2: float,
        root_depth_cm: float = 40.0
    ) -> Dict:
        """
        Convert ppm deficit to kg of nutrient needed for this zone.

        Formula: nutrient_kg = (optimal_ppm - current_ppm) × Bd × Zr_cm × area_m2 × 0.0001
        Unit derivation: ppm × g/cm3 × cm × m2 → kg (×0.0001 is the unit conversion)
        Source: CABI Soil Fertility in Africa, IFDC Kenya 2019

        Args:
            root_depth_cm: Effective root depth from crop_varieties table

        Returns:
            Dict with N, P, K deficits in kg and ppm
        """
        crop = crop_name.lower()
        ranges = self.crop_ranges.get(crop, self.crop_ranges["maize"])
        bd = self.bulk_density.get(soil_type, 1.25)

        # Unit conversion: ppm × g/cm3 × cm depth × m2 area × 0.0001 = kg
        # 0.0001 = (1/100) for % of ppm being fraction × (1/1000) g→kg × (1/10) cm→dm
        def ppm_to_kg(ppm_deficit):
            return ppm_deficit * bd * root_depth_cm * zone_area_m2 * 0.0001

        n_deficit_ppm = max(ranges["n_opt"] - current_n, 0.0)
        p_deficit_ppm = max(ranges["p_opt"] - current_p, 0.0)
        k_deficit_ppm = max(ranges["k_opt"] - current_k, 0.0)

        # Beans fix their own N — don't recommend N fertilizer unless severely deficient
        if ranges.get("nitrogen_fixing") and n_deficit_ppm < 40:
            n_deficit_ppm = 0.0

        return {
            "nitrogen_deficit_ppm":   round(n_deficit_ppm, 1),
            "phosphorus_deficit_ppm": round(p_deficit_ppm, 1),
            "potassium_deficit_ppm":  round(k_deficit_ppm, 1),
            "nitrogen_deficit_kg":    round(ppm_to_kg(n_deficit_ppm), 4),
            "phosphorus_deficit_kg":  round(ppm_to_kg(p_deficit_ppm), 4),
            "potassium_deficit_kg":   round(ppm_to_kg(k_deficit_ppm), 4),
            "nitrogen_fixing_crop":   ranges.get("nitrogen_fixing", False),
            "formula": "nutrient_kg = deficit_ppm × Bd × root_depth_cm × area_m2 × 0.0001",
            "inputs": {
                "current_n_ppm": current_n, "optimal_n_ppm": ranges["n_opt"],
                "current_p_ppm": current_p, "optimal_p_ppm": ranges["p_opt"],
                "current_k_ppm": current_k, "optimal_k_ppm": ranges["k_opt"],
                "bulk_density": bd,
                "root_depth_cm": root_depth_cm,
                "zone_area_m2": zone_area_m2,
            },
            "source": "CABI Soil Fertility in Africa; IFDC Fertilizer Use by Crop in Kenya 2019"
        }

    # -------------------------------------------------------------------------
    # FERTILIZER PRODUCT RECOMMENDATION
    # Translates kg of nutrient needed into a specific product + KES cost
    # -------------------------------------------------------------------------
    def recommend_fertilizer(
        self,
        nutrient: str,
        kg_needed: float,
        crop_name: str,
        growth_stage: str = "mid"
    ) -> Optional[Dict]:
        """
        Recommend the best matching Kenyan fertilizer product for a nutrient deficit.

        Args:
            nutrient: 'nitrogen', 'phosphorus', or 'potassium'
            kg_needed: kg of the nutrient needed for this zone
            crop_name: To match appropriate product
            growth_stage: 'initial', 'development', 'mid', 'late'

        Returns:
            Dict with product_name, grams_to_apply, cost_kes, and action description
        """
        if kg_needed <= 0:
            return None

        # Select best product per nutrient and growth stage
        # Priority logic based on KALRO/Yara recommendations for Kenya
        if nutrient == "nitrogen":
            if growth_stage in ("initial", "development"):
                product_name = "DAP"         # DAP at planting for N+P
            else:
                product_name = "CAN"         # CAN for top-dressing

        elif nutrient == "phosphorus":
            product_name = "DAP"             # DAP is primary P source in Kenya

        elif nutrient == "potassium":
            crop = crop_name.lower()
            if crop in ("potatoes", "tomatoes"):
                product_name = "MOP"         # High K for tuber/fruit crops
            else:
                product_name = "NPK 17:17:17"

        else:
            return None

        product = self.fertilizers.get(product_name)
        if not product:
            return None

        # kg fertilizer needed = kg nutrient / (nutrient% / 100)
        nutrient_pct_key = f"{nutrient[0]}_pct"  # n_pct, p_pct, k_pct
        nutrient_pct = product.get(f"{nutrient[0]}_pct", 0)
        if nutrient_pct <= 0:
            return None

        kg_product = kg_needed / (nutrient_pct / 100.0)
        grams_product = kg_product * 1000

        # Cost: price is per 50kg bag
        cost_kes = (kg_product / 50.0) * product["price_kes_per_50kg"]

        return {
            "product_name": product_name,
            "nutrient_targeted": nutrient,
            "kg_product_needed": round(kg_product, 4),
            "grams_to_apply": round(grams_product, 1),
            "cost_kes": round(cost_kes, 2),
            "product_n_pct": product.get("n_pct", 0),
            "product_p_pct": product.get("p_pct", 0),
            "product_k_pct": product.get("k_pct", 0),
            "application_guide": product["use"],
            "formula": "kg_product = kg_nutrient / (nutrient_pct / 100)",
            "source": product["source"]
        }

    # -------------------------------------------------------------------------
    # FULL SOIL RECOMMENDATION — combines gate + lime + NPK
    # -------------------------------------------------------------------------
    def generate_soil_recommendation(
        self,
        zone_data: Dict,
        crop_name: str,
        soil_type: str,
        zone_area_m2: float = 4.0,
        days_since_planting: int = 30,
        growth_stage: str = "mid",
        root_depth_cm: float = 40.0
    ) -> Dict:
        """
        Generate complete soil amendment recommendations for one zone.

        Flow:
          1. Check pH gate — if critical, return only lime recommendation
          2. Calculate lime needed (if pH suboptimal but not critical)
          3. Calculate NPK deficits
          4. Translate deficits to specific fertilizer products
          5. Calculate total cost in KES
          6. Assign urgency score

        Args:
            zone_data: Must include ph_level, nitrogen_ppm, phosphorus_ppm,
                       potassium_ppm, electrical_conductivity, soil_moisture_pct
        """
        ph      = zone_data.get("ph_level", 6.5)
        n_ppm   = zone_data.get("nitrogen_ppm", 100)
        p_ppm   = zone_data.get("phosphorus_ppm", 50)
        k_ppm   = zone_data.get("potassium_ppm", 100)
        ec      = zone_data.get("electrical_conductivity", 300)

        crop = crop_name.lower()
        ranges = self.crop_ranges.get(crop, self.crop_ranges["maize"])

        recommendations = []
        total_cost_kes = 0.0

        # --- Step 1: pH Gate ---
        ph_gate = self.check_ph_gate(ph, crop_name)

        if ph_gate["gate_active"]:
            # pH is critical — only lime, no NPK
            target_ph = ranges["ph_opt_min"]
            lime = self.calculate_lime_needed(ph, target_ph, soil_type, zone_area_m2)
            lime_rec = {
                "recommendation_type": "lime",
                "action_description": (
                    f"pH is {ph:.1f} — too acidic for {crop_name}. "
                    f"Apply {lime['lime_needed_kg']:.0f}g of Agricultural Lime. "
                    f"Cost: ~KES {lime['cost_kes']:.0f}. "
                    f"Wait 4–6 weeks before applying fertilizer."
                ),
                "action_quantity": lime["lime_needed_kg"],
                "action_unit": "kg",
                "product_name": "Agricultural Lime",
                "estimated_cost_kes": lime["cost_kes"],
                "urgency_level": "CRITICAL",
                "ph_gate_active": True,
                "ph_gate_reason": ph_gate["reason"],
                "do_not_fertilize_until": True,
                "calculation_breakdown": {
                    "ph_gate": ph_gate,
                    "lime_calc": lime,
                    "data_sources": ["KALRO Soil Acidity and Liming Handbook Kenya 2023"]
                }
            }
            return {
                "ph_gate_active": True,
                "recommendations": [lime_rec],
                "total_cost_kes": lime["cost_kes"],
                "summary": f"pH correction required before any fertilizer application."
            }

        # --- Step 2: Lime if pH is suboptimal (but not critical) ---
        ph_opt_min = ranges["ph_opt_min"]
        lime_recs = []
        if ph < ph_opt_min:
            target_ph = ph_opt_min
            lime = self.calculate_lime_needed(ph, target_ph, soil_type, zone_area_m2)
            if lime["lime_needed_kg"] > 0.001:
                lime_recs.append({
                    "recommendation_type": "lime",
                    "action_description": (
                        f"pH {ph:.1f} is below optimal ({ph_opt_min}). "
                        f"Apply {lime['lime_needed_kg']*1000:.0f}g Agricultural Lime (~KES {lime['cost_kes']:.0f}). "
                        f"Can apply alongside fertilizer but ideally 2 weeks apart."
                    ),
                    "action_quantity": lime["lime_needed_kg"],
                    "action_unit": "kg",
                    "product_name": "Agricultural Lime",
                    "estimated_cost_kes": lime["cost_kes"],
                    "urgency_level": "MEDIUM",
                    "calculation_breakdown": {
                        "lime_calc": lime,
                        "data_sources": ["KALRO Liming Guide 2023"]
                    }
                })
                total_cost_kes += lime["cost_kes"]

        # --- Step 3: NPK deficits ---
        npk = self.calculate_npk_deficit(
            current_n=n_ppm, current_p=p_ppm, current_k=k_ppm,
            crop_name=crop_name, soil_type=soil_type,
            zone_area_m2=zone_area_m2, root_depth_cm=root_depth_cm
        )

        # --- Step 4: Fertilizer products for each deficit ---
        npk_recs = []
        for nutrient, deficit_ppm_key, deficit_kg_key in [
            ("nitrogen",   "nitrogen_deficit_ppm",   "nitrogen_deficit_kg"),
            ("phosphorus", "phosphorus_deficit_ppm", "phosphorus_deficit_kg"),
            ("potassium",  "potassium_deficit_ppm",  "potassium_deficit_kg"),
        ]:
            deficit_ppm = npk[deficit_ppm_key]
            deficit_kg  = npk[deficit_kg_key]

            if deficit_ppm < 10:
                continue  # Not worth recommending for tiny deficits

            fert = self.recommend_fertilizer(nutrient, deficit_kg, crop_name, growth_stage)
            if not fert:
                continue

            # Urgency based on deficit severity
            if deficit_ppm > (ranges.get(f"{nutrient[0]}_opt", 100) * 0.5):
                urgency = "HIGH"
            elif deficit_ppm > (ranges.get(f"{nutrient[0]}_opt", 100) * 0.25):
                urgency = "MEDIUM"
            else:
                urgency = "LOW"

            action = (
                f"Zone needs {nutrient}. Apply {fert['grams_to_apply']:.0f}g of "
                f"{fert['product_name']} (~KES {fert['cost_kes']:.0f}). "
                f"{fert['application_guide']}"
            )

            npk_recs.append({
                "recommendation_type": f"fertilize_{nutrient[0]}",
                "action_description": action,
                "action_quantity": fert["grams_to_apply"],
                "action_unit": "grams",
                "product_name": fert["product_name"],
                "estimated_cost_kes": fert["cost_kes"],
                "urgency_level": urgency,
                "calculation_breakdown": {
                    "npk_deficit": npk,
                    "fertilizer": fert,
                    "data_sources": [
                        "IFDC Fertilizer Use by Crop in Kenya 2019",
                        "CABI Soil Fertility in Africa",
                        npk["source"]
                    ]
                }
            })
            total_cost_kes += fert["cost_kes"]

        all_recs = lime_recs + npk_recs

        if not all_recs:
            return {
                "ph_gate_active": False,
                "recommendations": [{
                    "recommendation_type": "monitor",
                    "action_description": "Soil levels are within acceptable ranges. No amendments needed this week.",
                    "urgency_level": "LOW",
                    "estimated_cost_kes": 0
                }],
                "total_cost_kes": 0.0,
                "summary": "No soil amendments required."
            }

        return {
            "ph_gate_active": False,
            "recommendations": all_recs,
            "total_cost_kes": round(total_cost_kes, 2),
            "npk_summary": {
                "n_deficit_ppm": npk["nitrogen_deficit_ppm"],
                "p_deficit_ppm": npk["phosphorus_deficit_ppm"],
                "k_deficit_ppm": npk["potassium_deficit_ppm"],
            },
            "summary": f"{len(all_recs)} amendment(s) recommended. Total cost: KES {total_cost_kes:.0f}"
        }


# =============================================================================
# YIELD SEED MODEL
# =============================================================================

class YieldSeedModel:
    """
    Crop variety suitability scoring.
    Scores each available variety against current zone conditions.
    Source: ECOCROP (FAO), KALRO Crop Variety Catalogue 2023
    """

    def __init__(self):
        self.crop_ranges = CROP_OPTIMAL_RANGES

        # Kenyan variety baseline yields (kg/m2) and market prices
        # Source: KALRO 2023, KAMIS market data
        self.variety_data = {
            "maize": [
                {"name": "H614D",  "yield_kg_m2": 0.10, "days": 130, "altitude": "900-2100m", "drought_tolerant": False},
                {"name": "DK8031", "yield_kg_m2": 0.125,"days": 115, "altitude": "0-1800m",   "drought_tolerant": False},
                {"name": "DUMA 43","yield_kg_m2": 0.085,"days": 95,  "altitude": "0-1600m",   "drought_tolerant": True},
            ],
            "beans": [
                {"name": "Rosecoco GLP2","yield_kg_m2": 0.050,"days": 80, "altitude": "1200-2200m","drought_tolerant": False},
                {"name": "Mwezi Moja",  "yield_kg_m2": 0.045,"days": 65, "altitude": "0-1800m",   "drought_tolerant": True},
            ],
            "potatoes": [
                {"name": "Shangi",      "yield_kg_m2": 0.40, "days": 95,  "altitude": "1800-3000m","drought_tolerant": False},
                {"name": "Dutch Robjin","yield_kg_m2": 0.50, "days": 105, "altitude": "1800-3000m","drought_tolerant": False},
            ],
            "tomatoes": [
                {"name": "Rambo F1",   "yield_kg_m2": 1.15, "days": 80,  "altitude": "0-2000m", "drought_tolerant": False},
                {"name": "Money Maker","yield_kg_m2": 0.70, "days": 90,  "altitude": "0-2200m", "drought_tolerant": True},
            ],
            "kale": [
                {"name": "Collard Mfalme F1","yield_kg_m2": 0.10, "days": 55, "altitude": "0-2500m","drought_tolerant": True},
            ],
        }

    def score_variety(
        self,
        variety: Dict,
        zone_data: Dict,
        crop_name: str,
        altitude_m: float = 1500.0,
        rainfall_zone: str = "medium"
    ) -> Dict:
        """
        Score a single variety 0–100 based on how well the zone suits it.
        Uses Mitscherlich yield response principle — yield decreases as
        conditions deviate from optimal.
        Source: FAO Plant Nutrition for Food Security Bulletin 16
        """
        crop = crop_name.lower()
        ranges = self.crop_ranges.get(crop, self.crop_ranges["maize"])
        score = 100.0
        penalties = []

        ph = zone_data.get("ph_level", 6.5)
        moisture = zone_data.get("soil_moisture_pct", 60.0)

        # pH scoring
        if ranges["ph_opt_min"] <= ph <= ranges["ph_opt_max"]:
            pass  # perfect
        elif ranges["ph_min"] <= ph <= ranges["ph_max"]:
            deviation = min(abs(ph - ranges["ph_opt_min"]), abs(ph - ranges["ph_opt_max"]))
            penalty = deviation * 10
            score -= penalty
            penalties.append(f"pH {ph:.1f} slightly outside optimal range (-{penalty:.0f}pts)")
        else:
            score -= 40
            penalties.append(f"pH {ph:.1f} outside viable range (-40pts)")

        # Moisture scoring
        if ranges["moisture_opt_min"] <= moisture <= ranges["moisture_opt_max"]:
            pass
        else:
            deviation = max(
                ranges["moisture_opt_min"] - moisture,
                moisture - ranges["moisture_opt_max"],
                0
            )
            penalty = min(deviation * 0.5, 20)
            score -= penalty
            penalties.append(f"Moisture {moisture:.0f}% not ideal (-{penalty:.0f}pts)")

        # Drought tolerance bonus when rainfall is low
        if rainfall_zone == "low" and variety.get("drought_tolerant"):
            score += 10
            penalties.append("Drought tolerance bonus (+10pts)")

        # Altitude suitability (rough check)
        alt_range = variety.get("altitude", "0-3000m")
        try:
            parts = alt_range.replace("m", "").split("-")
            alt_min, alt_max = float(parts[0]), float(parts[1])
            if not (alt_min <= altitude_m <= alt_max):
                score -= 20
                penalties.append(f"Altitude {altitude_m:.0f}m outside variety range {alt_range} (-20pts)")
        except Exception:
            pass

        score = max(0.0, min(100.0, score))

        return {
            "variety_name": variety["name"],
            "suitability_score": round(score, 1),
            "baseline_yield_kg_m2": variety["yield_kg_m2"],
            "days_to_harvest": variety["days"],
            "drought_tolerant": variety.get("drought_tolerant", False),
            "penalties": penalties,
            "source": "ECOCROP (FAO), KALRO Variety Catalogue 2023"
        }

    def recommend_variety(
        self,
        crop_name: str,
        zone_data: Dict,
        altitude_m: float = 1500.0,
        rainfall_zone: str = "medium"
    ) -> Dict:
        """
        Score all varieties for a crop and return ranked recommendations.
        """
        crop = crop_name.lower()
        varieties = self.variety_data.get(crop, [])

        if not varieties:
            return {
                "crop": crop_name,
                "error": f"No variety data for {crop_name}",
                "recommendations": []
            }

        scored = []
        for v in varieties:
            scored.append(self.score_variety(v, zone_data, crop_name, altitude_m, rainfall_zone))

        scored.sort(key=lambda x: x["suitability_score"], reverse=True)
        best = scored[0]

        return {
            "crop": crop_name,
            "recommended_variety": best["variety_name"],
            "suitability_score": best["suitability_score"],
            "all_varieties_ranked": scored,
            "confidence_label": (
                "High confidence" if best["suitability_score"] >= 80
                else "Moderate confidence" if best["suitability_score"] >= 60
                else "Low confidence — consider improving soil conditions first"
            ),
            "source": "ECOCROP (FAO), KALRO Crop Variety Catalogue 2023"
        }


# =============================================================================
# MODULE-LEVEL SINGLETONS
# =============================================================================
soil_model = YieldSoilModel()
seed_model = YieldSeedModel()