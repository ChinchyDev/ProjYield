"""
YieldVision Precision Farming ML Models
Zone-specific soil amendment, water, and seed recommendation models
"""

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from xgboost import XGBRegressor
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from typing import Dict, List, Tuple
import joblib
import json

class PrecisionSoilModel:
    """Zone-specific soil amendment recommendation model"""
    
    def __init__(self):
        self.model = XGBRegressor(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1,
            random_state=42
        )
        self.scaler = StandardScaler()
        self.is_trained = False
        
        # Optimal NPK levels for different crops (ppm)
        self.optimal_npk = {
            'maize': {'N': 150, 'P': 50, 'K': 120},
            'wheat': {'N': 120, 'P': 40, 'K': 100},
            'tomatoes': {'N': 200, 'P': 60, 'K': 150},
            'beans': {'N': 80, 'P': 50, 'K': 80},
            'potatoes': {'N': 180, 'P': 70, 'K': 200}
        }
        
        # Optimal pH ranges for different crops
        self.optimal_ph = {
            'maize': [6.0, 7.0],
            'wheat': [6.0, 7.5],
            'tomatoes': [6.0, 6.8],
            'beans': [6.0, 7.0],
            'potatoes': [5.0, 6.0]
        }
    
    def calculate_optimal_npk(self, crop_type: str, soil_type: str) -> Dict[str, float]:
        """Calculate optimal NPK for specific crop and soil type"""
        base_npk = self.optimal_npk.get(crop_type, self.optimal_npk['maize'])
        
        # Adjust based on soil type
        soil_adjustments = {
            'sandy': {'N': 1.2, 'P': 1.1, 'K': 0.9},  # Leaching, need more N
            'clay': {'N': 0.9, 'P': 1.2, 'K': 1.1},   # Better retention
            'loamy': {'N': 1.0, 'P': 1.0, 'K': 1.0},   # Balanced
            'silty': {'N': 1.1, 'P': 1.0, 'K': 1.0}    # Good drainage
        }
        
        adjustment = soil_adjustments.get(soil_type, soil_adjustments['loamy'])
        
        return {
            'N': base_npk['N'] * adjustment['N'],
            'P': base_npk['P'] * adjustment['P'],
            'K': base_npk['K'] * adjustment['K']
        }
    
    def calculate_ph_needs(self, current_ph: float, crop_type: str) -> float:
        """Calculate pH adjustment needs in liters per zone"""
        optimal_range = self.optimal_ph.get(crop_type, [6.0, 7.0])
        
        if current_ph < optimal_range[0]:
            # Need to raise pH (add lime)
            ph_deficit = optimal_range[0] - current_ph
            lime_needed = ph_deficit * 2.0  # Simplified calculation
            return lime_needed
        elif current_ph > optimal_range[1]:
            # Need to lower pH (add sulfur)
            ph_excess = current_ph - optimal_range[1]
            sulfur_needed = ph_excess * 1.5  # Simplified calculation
            return -sulfur_needed  # Negative indicates lowering pH
        
        return 0.0  # pH is in optimal range
    
    def recommend_amendments(self, zone_data: Dict) -> Dict:
        """Recommend precise amendments for a 2m² zone"""
        current_npk = {
            'N': zone_data.get('nitrogen_ppm', 0),
            'P': zone_data.get('phosphorus_ppm', 0),
            'K': zone_data.get('potassium_ppm', 0)
        }
        
        crop_type = zone_data.get('crop_type', 'maize')
        soil_type = zone_data.get('soil_type', 'loamy')
        
        # Calculate optimal levels for this zone
        target_npk = self.calculate_optimal_npk(crop_type, soil_type)
        
        # Calculate exact deficit per zone (convert ppm to kg per 2m²)
        zone_area_m2 = 4.0  # 2m x 2m
        ppm_to_kg_per_m2 = 0.001  # Approximate conversion
        
        amendments = {
            'zone_id': zone_data.get('zone_id'),
            'nitrogen_kg_per_zone': max(0, (target_npk['N'] - current_npk['N']) * ppm_to_kg_per_m2 * zone_area_m2),
            'phosphorus_kg_per_zone': max(0, (target_npk['P'] - current_npk['P']) * ppm_to_kg_per_m2 * zone_area_m2),
            'potassium_kg_per_zone': max(0, (target_npk['K'] - current_npk['K']) * ppm_to_kg_per_m2 * zone_area_m2),
            'ph_adjustment_liters_per_zone': self.calculate_ph_needs(
                zone_data.get('ph_level', 7.0), crop_type
            ),
            'organic_matter_kg_per_zone': max(0, (3.0 - zone_data.get('organic_matter_percent', 0)) * zone_area_m2 * 0.01),
            'estimated_cost_usd': 0.0  # Will be calculated based on local prices
        }
        
        # Calculate estimated cost (simplified pricing)
        fertilizer_prices = {
            'nitrogen_per_kg': 1.5,
            'phosphorus_per_kg': 2.0,
            'potassium_per_kg': 1.8,
            'lime_per_liter': 0.5,
            'sulfur_per_liter': 0.8,
            'organic_matter_per_kg': 0.3
        }
        
        amendments['estimated_cost_usd'] = (
            amendments['nitrogen_kg_per_zone'] * fertilizer_prices['nitrogen_per_kg'] +
            amendments['phosphorus_kg_per_zone'] * fertilizer_prices['phosphorus_per_kg'] +
            amendments['potassium_kg_per_zone'] * fertilizer_prices['potassium_per_kg'] +
            abs(amendments['ph_adjustment_liters_per_zone']) * 
            (fertilizer_prices['lime_per_liter'] if amendments['ph_adjustment_liters_per_zone'] > 0 
             else fertilizer_prices['sulfur_per_liter']) +
            amendments['organic_matter_kg_per_zone'] * fertilizer_prices['organic_matter_per_kg']
        )
        
        return amendments
    
    def train(self, X: np.ndarray, y: np.ndarray):
        """Train the soil model"""
        X_scaled = self.scaler.fit_transform(X)
        self.model.fit(X_scaled, y)
        self.is_trained = True
    
    def predict(self, zone_data: Dict) -> float:
        """Predict soil health score for a zone"""
        if not self.is_trained:
            return 0.75  # Default score if not trained
        
        features = np.array([[
            zone_data.get('nitrogen_ppm', 0),
            zone_data.get('phosphorus_ppm', 0),
            zone_data.get('potassium_ppm', 0),
            zone_data.get('ph_level', 7.0),
            zone_data.get('organic_matter_percent', 2.0),
            zone_data.get('soil_moisture_20cm', 30)
        ]])
        
        features_scaled = self.scaler.transform(features)
        return self.model.predict(features_scaled)[0]

class PrecisionWaterModel(nn.Module):
    """Neural network model for irrigation scheduling"""
    
    def __init__(self, input_size=8, hidden_size=32, num_layers=2):
        super(PrecisionWaterModel, self).__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        
        # LSTM layers for time series analysis
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, 
                           batch_first=True, dropout=0.2)
        
        # Fully connected layers for final prediction
        self.fc = nn.Sequential(
            nn.Linear(hidden_size, 16),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(16, 3)  # Output: water_amount, efficiency, stress_level
        )
        
        # Crop-specific water requirements
        self.crop_water_needs = {
            'maize': {'base_requirement': 4.5, 'critical_stages': ['flowering', 'fruiting']},
            'wheat': {'base_requirement': 3.8, 'critical_stages': ['flowering', 'grain_filling']},
            'tomatoes': {'base_requirement': 5.2, 'critical_stages': ['flowering', 'fruiting']},
            'beans': {'base_requirement': 3.2, 'critical_stages': ['flowering', 'pod_filling']},
            'potatoes': {'base_requirement': 4.8, 'critical_stages': ['tuber_initiation', 'bulking']}
        }
    
    def forward(self, x):
        # Initialize hidden state
        h0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size).to(x.device)
        c0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size).to(x.device)
        
        # LSTM forward pass
        out, _ = self.lstm(x, (h0, c0))
        
        # Use the last time step output
        out = self.fc(out[:, -1, :])
        return out
    
    def zone_irrigation_schedule(self, zone_id: str, current_moisture: float, 
                               crop_stage: str, zone_data: Dict) -> Dict:
        """Generate irrigation schedule for a specific zone"""
        
        crop_type = zone_data.get('crop_type', 'maize')
        soil_type = zone_data.get('soil_type', 'loamy')
        
        # Get crop-specific requirements
        crop_info = self.crop_water_needs.get(crop_type, self.crop_water_needs['maize'])
        base_requirement = crop_info['base_requirement']
        
        # Adjust based on growth stage
        if crop_stage in crop_info['critical_stages']:
            stage_multiplier = 1.3
        else:
            stage_multiplier = 1.0
        
        # Soil type adjustments
        soil_factors = {
            'sandy': 1.2,    # Drains faster, needs more water
            'clay': 0.8,     # Holds water well
            'loamy': 1.0,    # Balanced
            'silty': 1.1     # Good drainage
        }
        
        soil_factor = soil_factors.get(soil_type, 1.0)
        
        # Calculate water amount for 4m² zone
        moisture_deficit = max(0, 35.0 - current_moisture)  # Target 35% moisture
        water_liters_per_hour = base_requirement * stage_multiplier * soil_factor * (moisture_deficit / 20.0)
        
        # Calculate irrigation duration
        flow_rate_liters_per_hour = 2.0  # Typical drip irrigation flow rate
        duration_minutes = (water_liters_per_hour / flow_rate_liters_per_hour) * 60
        
        # Calculate efficiency
        efficiency_score = self.calculate_water_efficiency(current_moisture, zone_data)
        
        return {
            'zone_id': zone_id,
            'water_liters_per_hour': round(water_liters_per_hour, 2),
            'duration_minutes': round(duration_minutes, 1),
            'efficiency_score': round(efficiency_score, 3),
            'optimal_time': self.calculate_optimal_irrigation_time(zone_data),
            'soil_moisture_target': 35.0,  # Target moisture percentage
            'estimated_cost_usd': round(water_liters_per_hour * 0.001, 3),  # $0.001 per liter
            'roi_multiplier': round(efficiency_score * 2.5, 2)  # Simplified ROI calculation
        }
    
    def calculate_water_efficiency(self, current_moisture: float, zone_data: Dict) -> float:
        """Calculate water use efficiency for current conditions"""
        target_moisture = 35.0
        
        if current_moisture >= target_moisture:
            return 0.8  # Good efficiency when well-watered
        
        # Efficiency decreases when too dry
        efficiency = 0.8 * (current_moisture / target_moisture)
        return max(0.2, efficiency)
    
    def calculate_optimal_irrigation_time(self, zone_data: Dict) -> str:
        """Calculate optimal irrigation time based on conditions"""
        temperature = zone_data.get('temperature_c', 25.0)
        
        if temperature > 30:
            return "05:00-07:00"  # Early morning for hot days
        elif temperature < 20:
            return "14:00-16:00"  # Afternoon for cool days
        else:
            return "06:00-08:00"  # Morning for moderate days

class PrecisionSeedModel:
    """Machine learning model for crop variety recommendation"""
    
    def __init__(self):
        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            random_state=42
        )
        self.scaler = StandardScaler()
        self.is_trained = False
        
        # Crop variety database with characteristics
        self.crop_varieties = {
            'maize': [
                {'name': 'Hybrid 101', 'yield_potential': 9.2, 'drought_tolerance': 0.6, 'disease_resistance': 0.8, 'maturity_days': 115},
                {'name': 'Hybrid 202', 'yield_potential': 10.1, 'drought_tolerance': 0.4, 'disease_resistance': 0.9, 'maturity_days': 120},
                {'name': 'DroughtMaster', 'yield_potential': 8.5, 'drought_tolerance': 0.9, 'disease_resistance': 0.7, 'maturity_days': 110},
                {'name': 'HighYield Pro', 'yield_potential': 11.2, 'drought_tolerance': 0.3, 'disease_resistance': 0.85, 'maturity_days': 125}
            ],
            'wheat': [
                {'name': 'Hard Red Winter', 'yield_potential': 4.5, 'drought_tolerance': 0.7, 'disease_resistance': 0.8, 'maturity_days': 95},
                {'name': 'Soft White', 'yield_potential': 4.1, 'drought_tolerance': 0.8, 'disease_resistance': 0.7, 'maturity_days': 90},
                {'name': 'Durum Gold', 'yield_potential': 3.9, 'drought_tolerance': 0.6, 'disease_resistance': 0.9, 'maturity_days': 100}
            ],
            'tomatoes': [
                {'name': 'Roma VF', 'yield_potential': 16.2, 'drought_tolerance': 0.5, 'disease_resistance': 0.8, 'maturity_days': 80},
                {'name': 'Cherry Sweet', 'yield_potential': 14.5, 'drought_tolerance': 0.7, 'disease_resistance': 0.9, 'maturity_days': 75},
                {'name': 'Beefsteak XL', 'yield_potential': 18.0, 'drought_tolerance': 0.4, 'disease_resistance': 0.7, 'maturity_days': 85}
            ]
        }
    
    def microclimate_analysis(self, zone_data: Dict) -> Dict:
        """Analyze microclimate and recommend suitable varieties"""
        zone_id = zone_data.get('zone_id', 'unknown')
        crop_type = zone_data.get('crop_type', 'maize')
        
        # Get available varieties for this crop
        varieties = self.crop_varieties.get(crop_type, self.crop_varieties['maize'])
        
        # Analyze zone conditions
        conditions = self.analyze_zone_conditions(zone_data)
        
        # Score each variety based on zone conditions
        scored_varieties = []
        for variety in varieties:
            score = self.calculate_variety_score(variety, conditions)
            scored_varieties.append({
                'variety_name': variety['name'],
                'suitability_score': round(score, 3),
                'expected_yield_kg_per_zone': round(variety['yield_potential'] * score, 2),
                'drought_tolerance': variety['drought_tolerance'],
                'disease_resistance': variety['disease_resistance'],
                'maturity_days': variety['maturity_days'],
                'recommendation_reason': self.get_recommendation_reason(variety, conditions)
            })
        
        # Sort by suitability score
        scored_varieties.sort(key=lambda x: x['suitability_score'], reverse=True)
        
        return {
            'zone_id': zone_id,
            'crop_type': crop_type,
            'zone_conditions': conditions,
            'recommended_varieties': scored_varieties[:3],  # Top 3 recommendations
            'analysis_timestamp': pd.Timestamp.now().isoformat()
        }
    
    def analyze_zone_conditions(self, zone_data: Dict) -> Dict:
        """Analyze and categorize zone conditions"""
        return {
            'soil_moisture_level': self.categorize_moisture(zone_data.get('soil_moisture_20cm', 30)),
            'temperature_range': self.categorize_temperature(zone_data.get('temperature_c', 25)),
            'soil_fertility': self.categorize_fertility(zone_data),
            'drainage_quality': zone_data.get('soil_type', 'loamy'),
            'sun_exposure': 'full'  # Assuming full sun for most zones
        }
    
    def categorize_moisture(self, moisture: float) -> str:
        """Categorize soil moisture level"""
        if moisture < 20:
            return 'dry'
        elif moisture < 35:
            return 'moderate'
        else:
            return 'wet'
    
    def categorize_temperature(self, temp: float) -> str:
        """Categorize temperature range"""
        if temp < 15:
            return 'cool'
        elif temp < 25:
            return 'moderate'
        else:
            return 'warm'
    
    def categorize_fertility(self, zone_data: Dict) -> str:
        """Categorize soil fertility based on NPK levels"""
        n = zone_data.get('nitrogen_ppm', 50)
        p = zone_data.get('phosphorus_ppm', 30)
        k = zone_data.get('potassium_ppm', 40)
        
        avg_npk = (n + p + k) / 3
        
        if avg_npk < 40:
            return 'low'
        elif avg_npk < 80:
            return 'moderate'
        else:
            return 'high'
    
    def calculate_variety_score(self, variety: Dict, conditions: Dict) -> float:
        """Calculate suitability score for a variety based on conditions"""
        base_score = 0.5
        
        # Drought tolerance scoring
        if conditions['soil_moisture_level'] == 'dry':
            base_score += variety['drought_tolerance'] * 0.3
        else:
            base_score += (1 - variety['drought_tolerance']) * 0.1
        
        # Disease resistance scoring (always beneficial)
        base_score += variety['disease_resistance'] * 0.2
        
        # Temperature compatibility
        if conditions['temperature_range'] == 'warm' and variety['maturity_days'] < 110:
            base_score += 0.1  # Early maturing varieties better in warm conditions
        
        # Yield potential (normalized)
        max_yield = 20.0  # Maximum expected yield for normalization
        yield_score = variety['yield_potential'] / max_yield
        base_score += yield_score * 0.2
        
        return min(1.0, base_score)
    
    def get_recommendation_reason(self, variety: Dict, conditions: Dict) -> str:
        """Generate explanation for variety recommendation"""
        reasons = []
        
        if conditions['soil_moisture_level'] == 'dry' and variety['drought_tolerance'] > 0.7:
            reasons.append("excellent drought tolerance")
        
        if variety['disease_resistance'] > 0.8:
            reasons.append("strong disease resistance")
        
        if variety['yield_potential'] > 10:
            reasons.append("high yield potential")
        
        if conditions['temperature_range'] == 'warm' and variety['maturity_days'] < 110:
            reasons.append("early maturity for warm conditions")
        
        if not reasons:
            reasons.append("well-balanced characteristics")
        
        return f"Selected for {', '.join(reasons)}"
    
    def train(self, X: np.ndarray, y: np.ndarray):
        """Train the seed model"""
        X_scaled = self.scaler.fit_transform(X)
        self.model.fit(X_scaled, y)
        self.is_trained = True

# Global instances for use across the application
soil_model = PrecisionSoilModel()
water_model = PrecisionWaterModel()
seed_model = PrecisionSeedModel()
