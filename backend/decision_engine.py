"""
YieldVision Decision Impact Engine
Evaluates precision farming decisions using Monte Carlo simulations
"""

import numpy as np
import pandas as pd
import torch
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
import json
from precision_models import PrecisionSoilModel, PrecisionWaterModel, PrecisionSeedModel

class DecisionImpactEngine:
    """Core decision evaluation engine for precision farming"""
    
    def __init__(self):
        self.soil_model = PrecisionSoilModel()
        self.water_model = PrecisionWaterModel()
        self.seed_model = PrecisionSeedModel()
        self.mc_iterations = 10000  # Monte Carlo iterations
        
        # Sensor error ranges for uncertainty simulation
        self.sensor_errors = {
            'soil_moisture': 0.05,      # ±5%
            'nitrogen_ppm': 10.0,       # ±10 ppm
            'phosphorus_ppm': 5.0,      # ±5 ppm
            'potassium_ppm': 8.0,       # ±8 ppm
            'ph_level': 0.2,            # ±0.2 pH
            'temperature': 2.0,         # ±2°C
            'organic_matter': 0.5       # ±0.5%
        }
        
        # Action cost parameters (USD per unit)
        self.action_costs = {
            'irrigation': 0.001,        # per liter
            'nitrogen': 1.5,            # per kg
            'phosphorus': 2.0,          # per kg
            'potassium': 1.8,           # per kg
            'lime': 0.5,                # per liter
            'sulfur': 0.8,              # per liter
            'planting': 50.0            # per zone (seeds + labor)
        }
    
    def evaluate_action(self, zone_data: Dict, action: Dict, time_horizon: int = 14) -> Dict:
        """
        Evaluate impact of action on specific zone using Monte Carlo simulation
        
        Args:
            zone_data: Current zone sensor data
            action: Action to evaluate (type, amount, timing)
            time_horizon: Days to simulate forward
        
        Returns:
            Decision evaluation with uncertainty quantification
        """
        print(f"Evaluating {action['type']} action for zone {zone_data.get('zone_id')}")
        
        # Monte Carlo simulation
        outcomes = []
        for iteration in range(self.mc_iterations):
            # Perturb inputs to simulate sensor uncertainty
            perturbed_state = self.perturb_inputs(zone_data)
            
            # Apply action and simulate forward
            outcome = self.simulate_action(perturbed_state, action, time_horizon)
            outcomes.append(outcome)
        
        # Calculate statistics from Monte Carlo results
        decision_result = self.calculate_decision_statistics(outcomes, action, zone_data)
        
        return decision_result
    
    def perturb_inputs(self, zone_data: Dict) -> Dict:
        """Add realistic sensor noise to inputs"""
        perturbed = zone_data.copy()
        
        # Add Gaussian noise based on sensor characteristics
        perturbed['soil_moisture_20cm'] = np.clip(
            np.random.normal(zone_data.get('soil_moisture_20cm', 30), 
                           self.sensor_errors['soil_moisture'] * 30),
            0, 100
        )
        
        perturbed['nitrogen_ppm'] = max(0, np.random.normal(
            zone_data.get('nitrogen_ppm', 50),
            self.sensor_errors['nitrogen_ppm']
        ))
        
        perturbed['phosphorus_ppm'] = max(0, np.random.normal(
            zone_data.get('phosphorus_ppm', 30),
            self.sensor_errors['phosphorus_ppm']
        ))
        
        perturbed['potassium_ppm'] = max(0, np.random.normal(
            zone_data.get('potassium_ppm', 40),
            self.sensor_errors['potassium_ppm']
        ))
        
        perturbed['ph_level'] = np.clip(
            np.random.normal(zone_data.get('ph_level', 7.0),
                           self.sensor_errors['ph_level']),
            4.0, 9.0
        )
        
        perturbed['temperature_c'] = np.random.normal(
            zone_data.get('temperature_c', 25.0),
            self.sensor_errors['temperature']
        )
        
        perturbed['organic_matter_percent'] = max(0, np.random.normal(
            zone_data.get('organic_matter_percent', 2.0),
            self.sensor_errors['organic_matter']
        ))
        
        return perturbed
    
    def simulate_action(self, state: Dict, action: Dict, time_horizon: int) -> Dict:
        """Simulate action impact over time horizon"""
        
        # Apply action transformation (rule-based for now)
        new_state = self.apply_action_transform(state, action)
        
        # Project forward using ML models
        future_yield = self.project_yield(new_state, time_horizon)
        water_efficiency = self.calculate_water_efficiency(new_state)
        soil_health = self.project_soil_health(new_state, time_horizon)
        
        # Calculate costs and benefits
        action_cost = self.calculate_action_cost(action)
        revenue_benefit = future_yield * 0.30  # $0.30 per kg (average crop price)
        
        return {
            'yield_kg_per_zone': future_yield,
            'water_efficiency': water_efficiency,
            'soil_health_score': soil_health,
            'action_cost_usd': action_cost,
            'revenue_benefit_usd': revenue_benefit,
            'net_benefit_usd': revenue_benefit - action_cost,
            'roi_multiplier': (revenue_benefit / action_cost) if action_cost > 0 else 0
        }
    
    def apply_action_transform(self, state: Dict, action: Dict) -> Dict:
        """Apply immediate effects of action to state"""
        new_state = state.copy()
        action_type = action['type']
        amount = action.get('amount', 0)
        
        if action_type == 'irrigate':
            # Increase soil moisture
            moisture_increase = amount * 2.5  # 1 liter increases moisture by ~2.5% in 4m²
            new_state['soil_moisture_20cm'] = min(60, new_state['soil_moisture_20cm'] + moisture_increase)
            
            # Leaching effect on nutrients
            leaching_factor = 0.02 * (amount / 10)  # 2% leaching per 10 liters
            new_state['nitrogen_ppm'] *= (1 - leaching_factor)
            new_state['potassium_ppm'] *= (1 - leaching_factor * 0.5)  # K leaches less
            
        elif action_type == 'fertilize_nitrogen':
            # Add nitrogen with efficiency factor
            efficiency = 0.7  # 70% of fertilizer becomes available
            n_increase = amount * efficiency
            new_state['nitrogen_ppm'] += n_increase
            
        elif action_type == 'fertilize_phosphorus':
            # Add phosphorus (less mobile)
            efficiency = 0.8
            p_increase = amount * efficiency
            new_state['phosphorus_ppm'] += p_increase
            
        elif action_type == 'fertilize_potassium':
            # Add potassium
            efficiency = 0.75
            k_increase = amount * efficiency
            new_state['potassium_ppm'] += k_increase
            
        elif action_type == 'adjust_ph_up':
            # Add lime to raise pH
            ph_increase = amount * 0.1  # Simplified: 1 liter raises pH by 0.1
            new_state['ph_level'] = min(9.0, new_state['ph_level'] + ph_increase)
            
        elif action_type == 'adjust_ph_down':
            # Add sulfur to lower pH
            ph_decrease = amount * 0.08  # Simplified: 1 liter lowers pH by 0.08
            new_state['ph_level'] = max(4.0, new_state['ph_level'] - ph_decrease)
            
        elif action_type == 'plant_crop':
            # Reset for new planting (simplified)
            new_state['crop_stage'] = 'germination'
            new_state['days_since_planting'] = 0
            
        return new_state
    
    def project_yield(self, state: Dict, time_horizon: int) -> float:
        """Project yield based on state and time horizon"""
        
        # Base yield potential for 4m² zone
        base_yield = 8.0  # kg per zone for ideal conditions
        
        # Calculate yield factors based on state
        moisture_factor = self.calculate_moisture_yield_factor(state['soil_moisture_20cm'])
        nutrient_factor = self.calculate_nutrient_yield_factor(state)
        ph_factor = self.calculate_ph_yield_factor(state['ph_level'])
        temperature_factor = self.calculate_temperature_yield_factor(state['temperature_c'])
        
        # Time-based growth factor
        time_factor = min(1.0, time_horizon / 120)  # Full maturity at 120 days
        
        # Combined yield potential
        yield_potential = base_yield * moisture_factor * nutrient_factor * ph_factor * temperature_factor
        
        # Add some randomness for realistic simulation
        random_factor = np.random.normal(1.0, 0.1)  # ±10% random variation
        
        return max(0, yield_potential * time_factor * random_factor)
    
    def calculate_moisture_yield_factor(self, moisture: float) -> float:
        """Calculate yield factor based on soil moisture"""
        optimal_range = (30, 45)  # Optimal moisture range
        
        if optimal_range[0] <= moisture <= optimal_range[1]:
            return 1.0
        elif moisture < optimal_range[0]:
            # Drought stress
            return max(0.3, moisture / optimal_range[0])
        else:
            # Waterlogging stress
            return max(0.5, 1.0 - (moisture - optimal_range[1]) / 30)
    
    def calculate_nutrient_yield_factor(self, state: Dict) -> float:
        """Calculate yield factor based on NPK levels"""
        # Optimal NPK ranges (ppm)
        optimal_npk = {'N': (100, 200), 'P': (30, 70), 'K': (80, 150)}
        
        current_npk = {
            'N': state.get('nitrogen_ppm', 50),
            'P': state.get('phosphorus_ppm', 30),
            'K': state.get('potassium_ppm', 40)
        }
        
        factors = []
        for nutrient in ['N', 'P', 'K']:
            optimal_min, optimal_max = optimal_npk[nutrient]
            current = current_npk[nutrient]
            
            if optimal_min <= current <= optimal_max:
                factors.append(1.0)
            elif current < optimal_min:
                factors.append(max(0.4, current / optimal_min))
            else:
                factors.append(max(0.7, 1.0 - (current - optimal_max) / optimal_max))
        
        return np.mean(factors)  # Average of all three nutrients
    
    def calculate_ph_yield_factor(self, ph: float) -> float:
        """Calculate yield factor based on pH level"""
        optimal_range = (6.0, 7.0)
        
        if optimal_range[0] <= ph <= optimal_range[1]:
            return 1.0
        elif ph < optimal_range[0]:
            return max(0.5, 0.5 + (ph - 4.0) / 4.0)  # Linear from pH 4 to 6
        else:
            return max(0.6, 1.0 - (ph - 7.0) / 4.0)  # Linear from pH 7 to 9
    
    def calculate_temperature_yield_factor(self, temp: float) -> float:
        """Calculate yield factor based on temperature"""
        optimal_range = (20, 30)  # Celsius
        
        if optimal_range[0] <= temp <= optimal_range[1]:
            return 1.0
        elif temp < optimal_range[0]:
            return max(0.3, 0.3 + (temp - 10) / 20)  # Linear from 10°C to 20°C
        else:
            return max(0.4, 1.0 - (temp - 30) / 20)  # Linear from 30°C to 40°C
    
    def calculate_water_efficiency(self, state: Dict) -> float:
        """Calculate water use efficiency (yield per liter of water)"""
        moisture = state['soil_moisture_20cm']
        target_moisture = 35.0
        
        if moisture >= target_moisture:
            return 0.8  # Good efficiency when well-watered
        
        # Efficiency decreases when too dry
        efficiency = 0.8 * (moisture / target_moisture)
        return max(0.2, efficiency)
    
    def project_soil_health(self, state: Dict, time_horizon: int) -> float:
        """Project soil health score over time"""
        # Base soil health components
        organic_matter_score = min(1.0, state['organic_matter_percent'] / 4.0)
        ph_score = self.calculate_ph_yield_factor(state['ph_level'])
        nutrient_balance = self.calculate_nutrient_yield_factor(state)
        
        # Time degradation/ improvement factor
        time_factor = 1.0 - (time_horizon / 365) * 0.1  # 10% degradation per year
        
        soil_health = (organic_matter_score * 0.4 + ph_score * 0.3 + nutrient_balance * 0.3) * time_factor
        
        return max(0.2, min(1.0, soil_health))
    
    def calculate_action_cost(self, action: Dict) -> float:
        """Calculate cost of action in USD"""
        action_type = action['type']
        amount = action.get('amount', 0)
        
        if action_type == 'irrigate':
            return amount * self.action_costs['irrigation']
        elif action_type == 'fertilize_nitrogen':
            return amount * self.action_costs['nitrogen']
        elif action_type == 'fertilize_phosphorus':
            return amount * self.action_costs['phosphorus']
        elif action_type == 'fertilize_potassium':
            return amount * self.action_costs['potassium']
        elif action_type in ['adjust_ph_up', 'adjust_ph_down']:
            return amount * self.action_costs['lime']  # Use lime cost as proxy
        elif action_type == 'plant_crop':
            return self.action_costs['planting']
        else:
            return 0.0
    
    def calculate_decision_statistics(self, outcomes: List[Dict], action: Dict, zone_data: Dict) -> Dict:
        """Calculate statistics from Monte Carlo outcomes"""
        
        # Extract metrics from all outcomes
        yields = [o['yield_kg_per_zone'] for o in outcomes]
        water_efficiencies = [o['water_efficiency'] for o in outcomes]
        soil_health_scores = [o['soil_health_score'] for o in outcomes]
        net_benefits = [o['net_benefit_usd'] for o in outcomes]
        roi_multipliers = [o['roi_multiplier'] for o in outcomes]
        
        # Find best simulation outcome
        best_simulation_index = np.argmax(net_benefits)
        best_simulation = outcomes[best_simulation_index]
        
        # Calculate statistics
        decision_result = {
            'zone_id': zone_data.get('zone_id'),
            'action_evaluated': action,
            'evaluation_time': datetime.now().isoformat(),
            'monte_carlo_iterations': self.mc_iterations,
            
            # Best simulation results
            'best_simulation': {
                'expected_yield_kg_per_zone': best_simulation['yield_kg_per_zone'],
                'water_efficiency': best_simulation['water_efficiency'],
                'soil_health_score': best_simulation['soil_health_score'],
                'net_benefit_usd': best_simulation['net_benefit_usd'],
                'roi_multiplier': best_simulation['roi_multiplier'],
                'simulation_rank': best_simulation_index + 1
            },
            
            # Yield statistics
            'expected_yield_kg_per_zone': {
                'mean': np.mean(yields),
                'std': np.std(yields),
                'min': np.min(yields),
                'max': np.max(yields),
                'percentile_5': np.percentile(yields, 5),
                'percentile_95': np.percentile(yields, 95)
            },
            
            # Economic statistics
            'expected_net_benefit_usd': {
                'mean': np.mean(net_benefits),
                'std': np.std(net_benefits),
                'percentile_5': np.percentile(net_benefits, 5),
                'percentile_95': np.percentile(net_benefits, 95)
            },
            
            'expected_roi_multiplier': {
                'mean': np.mean(roi_multipliers),
                'std': np.std(roi_multipliers),
                'percentile_5': np.percentile(roi_multipliers, 5),
                'percentile_95': np.percentile(roi_multipliers, 95)
            },
            
            # Efficiency statistics
            'expected_water_efficiency': {
                'mean': np.mean(water_efficiencies),
                'std': np.std(water_efficiencies)
            },
            
            'expected_soil_health_impact': {
                'mean': np.mean(soil_health_scores),
                'std': np.std(soil_health_scores)
            },
            
            # Decision quality metrics
            'confidence_score': self.calculate_confidence_score(outcomes),
            'risk_assessment': self.assess_risk(outcomes),
            'decision_complexity_score': self.calculate_complexity_score(action, zone_data),
            'recommendation': self.generate_recommendation(outcomes, action)
        }
        
        return decision_result
    
    def calculate_confidence_score(self, outcomes: List[Dict]) -> float:
        """Calculate confidence in the prediction"""
        # Confidence based on variance of outcomes
        net_benefits = [o['net_benefit_usd'] for o in outcomes]
        
        if np.std(net_benefits) == 0:
            return 1.0
        
        # Lower variance = higher confidence
        cv = np.std(net_benefits) / abs(np.mean(net_benefits)) if np.mean(net_benefits) != 0 else 1.0
        confidence = max(0.3, min(1.0, 1.0 - cv))
        
        return confidence
    
    def assess_risk(self, outcomes: List[Dict]) -> Dict:
        """Assess risk levels for the decision"""
        net_benefits = [o['net_benefit_usd'] for o in outcomes]
        
        # Calculate risk metrics
        probability_loss = np.mean([1 for b in net_benefits if b < 0])
        expected_loss = np.mean([abs(b) for b in net_benefits if b < 0]) if probability_loss > 0 else 0
        var_95 = np.percentile(net_benefits, 5)  # Value at Risk (5% worst case)
        
        risk_level = 'low'
        if probability_loss > 0.3 or var_95 < -10:
            risk_level = 'high'
        elif probability_loss > 0.1 or var_95 < -5:
            risk_level = 'medium'
        
        return {
            'risk_level': risk_level,
            'probability_of_loss': round(probability_loss, 3),
            'expected_loss_usd': round(expected_loss, 2),
            'value_at_risk_5_percent': round(var_95, 2)
        }
    
    def calculate_complexity_score(self, action: Dict, zone_data: Dict) -> float:
        """Calculate decision complexity score (0-1)"""
        complexity = 0.0
        
        # Action type complexity
        action_complexity = {
            'irrigate': 0.2,
            'fertilize_nitrogen': 0.4,
            'fertilize_phosphorus': 0.4,
            'fertilize_potassium': 0.4,
            'adjust_ph_up': 0.6,
            'adjust_ph_down': 0.6,
            'plant_crop': 0.8
        }
        
        complexity += action_complexity.get(action['type'], 0.5)
        
        # Amount complexity (larger amounts = more complex)
        amount = action.get('amount', 0)
        if amount > 50:
            complexity += 0.2
        elif amount > 20:
            complexity += 0.1
        
        # Zone condition complexity
        current_moisture = zone_data.get('soil_moisture_20cm', 30)
        if current_moisture < 15 or current_moisture > 50:
            complexity += 0.2  # Extreme conditions
        
        # Nutrient imbalance complexity
        npk = [zone_data.get('nitrogen_ppm', 50), 
               zone_data.get('phosphorus_ppm', 30),
               zone_data.get('potassium_ppm', 40)]
        npk_cv = np.std(npk) / np.mean(npk) if np.mean(npk) > 0 else 1.0
        if npk_cv > 0.5:
            complexity += 0.2
        
        return min(1.0, complexity)
    
    def generate_recommendation(self, outcomes: List[Dict], action: Dict) -> str:
        """Generate human-readable recommendation"""
        net_benefits = [o['net_benefit_usd'] for o in outcomes]
        mean_benefit = np.mean(net_benefits)
        confidence = self.calculate_confidence_score(outcomes)
        risk = self.assess_risk(outcomes)
        
        if mean_benefit > 5 and confidence > 0.7 and risk['risk_level'] == 'low':
            return "HIGHLY RECOMMENDED - Strong expected benefits with low risk"
        elif mean_benefit > 2 and confidence > 0.5:
            return "RECOMMENDED - Positive expected benefits, monitor conditions"
        elif mean_benefit > 0:
            return "CONSIDER - Marginal benefits, evaluate alternatives"
        elif mean_benefit > -2:
            return "NEUTRAL - Minimal impact, optional action"
        else:
            return "NOT RECOMMENDED - Expected losses or high risk"


# Initialize global decision engine
decision_engine = DecisionImpactEngine()
