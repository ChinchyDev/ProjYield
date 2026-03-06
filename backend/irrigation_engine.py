"""
YieldVision Irrigation Engine
Offloaded irrigation planning and optimization from decision engine
"""

import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import json
import logging

class IrrigationEngine:
    """Intelligent irrigation planning and optimization system"""
    
    def __init__(self):
        self.crop_water_requirements = {
            'maize': {
                'daily_water_mm': 4.5,
                'critical_stages': {
                    'germination': {'duration_days': 10, 'water_factor': 0.7},
                    'vegetative': {'duration_days': 30, 'water_factor': 1.0},
                    'flowering': {'duration_days': 15, 'water_factor': 1.3},
                    'fruiting': {'duration_days': 25, 'water_factor': 1.2},
                    'maturity': {'duration_days': 20, 'water_factor': 0.8}
                },
                'optimal_moisture_range': (30, 45),
                'water_use_efficiency': 15.0
            },
            'tomatoes': {
                'daily_water_mm': 3.8,
                'critical_stages': {
                    'germination': {'duration_days': 8, 'water_factor': 0.6},
                    'vegetative': {'duration_days': 25, 'water_factor': 0.9},
                    'flowering': {'duration_days': 20, 'water_factor': 1.4},
                    'fruiting': {'duration_days': 30, 'water_factor': 1.3},
                    'maturity': {'duration_days': 15, 'water_factor': 0.9}
                },
                'optimal_moisture_range': (35, 50),
                'water_use_efficiency': 20.0
            },
            'beans': {
                'daily_water_mm': 3.2,
                'critical_stages': {
                    'germination': {'duration_days': 7, 'water_factor': 0.6},
                    'vegetative': {'duration_days': 20, 'water_factor': 0.8},
                    'flowering': {'duration_days': 15, 'water_factor': 1.2},
                    'pod_filling': {'duration_days': 18, 'water_factor': 1.3},
                    'maturity': {'duration_days': 10, 'water_factor': 0.7}
                },
                'optimal_moisture_range': (32, 48),
                'water_use_efficiency': 12.0
            }
        }
        
        self.soil_water_holding_capacity = {
            'sandy': {'field_capacity': 15, 'wilting_point': 5, 'available_water': 10},
            'loamy': {'field_capacity': 25, 'wilting_point': 10, 'available_water': 15},
            'clay': {'field_capacity': 35, 'wilting_point': 15, 'available_water': 20},
            'silty': {'field_capacity': 30, 'wilting_point': 12, 'available_water': 18}
        }
        
        self.evapotranspiration_factors = {
            'cool': 0.7,      # < 20°C
            'moderate': 1.0,  # 20-25°C
            'warm': 1.3,      # 25-30°C
            'hot': 1.6        # > 30°C
        }

    def calculate_irrigation_requirement(self, zone_data: Dict, crop_type: str, 
                                        target_yield_kg_per_zone: float) -> Dict:
        """Calculate irrigation requirement for specific yield goal"""
        
        if crop_type not in self.crop_water_requirements:
            raise ValueError(f"Unsupported crop type: {crop_type}")
        
        crop_info = self.crop_water_requirements[crop_type]
        
        # Calculate water needed based on water use efficiency
        water_needed_m3 = target_yield_kg_per_zone / crop_info['water_use_efficiency']
        water_needed_liters = water_needed_m3 * 1000
        
        # Calculate daily water requirement
        total_growing_days = sum(stage['duration_days'] for stage in crop_info['critical_stages'].values())
        daily_water_liters = water_needed_liters / total_growing_days
        
        return {
            'target_yield_kg_per_zone': target_yield_kg_per_zone,
            'total_water_required_liters': water_needed_liters,
            'daily_water_requirement_liters': daily_water_liters,
            'total_growing_days': total_growing_days,
            'water_use_efficiency': crop_info['water_use_efficiency'],
            'crop_type': crop_type
        }

    def create_irrigation_schedule(self, zone_data: Dict, crop_type: str, 
                                 target_yield_kg_per_zone: float, 
                                 planning_period_days: int = 30) -> Dict:
        """Create detailed irrigation schedule to reach yield goal"""
        
        water_req = self.calculate_irrigation_requirement(zone_data, crop_type, target_yield_kg_per_zone)
        
        # Get soil and current conditions
        soil_type = zone_data.get('soil_type', 'loamy')
        current_moisture = zone_data.get('soil_moisture_20cm', 30.0)
        temperature = zone_data.get('temperature_c', 25.0)
        
        soil_props = self.soil_water_holding_capacity[soil_type]
        crop_info = self.crop_water_requirements[crop_type]
        
        # Determine growth stage
        days_since_planting = zone_data.get('days_since_planting', 0)
        current_stage = self._get_growth_stage(crop_type, days_since_planting)
        
        # Calculate daily irrigation plan
        schedule = []
        cumulative_water = 0
        
        for day in range(planning_period_days):
            date = datetime.now() + timedelta(days=day)
            
            # Adjust water requirement based on growth stage
            stage_factor = crop_info['critical_stages'][current_stage]['water_factor']
            
            # Adjust for temperature
            temp_factor = self._get_temperature_factor(temperature)
            
            # Calculate today's water requirement
            daily_requirement = water_req['daily_water_requirement_liters'] * stage_factor * temp_factor
            
            # Check soil moisture deficit
            optimal_range = crop_info['optimal_moisture_range']
            moisture_deficit = max(0, optimal_range[0] - current_moisture)
            
            # Calculate irrigation amount
            if moisture_deficit > 0:
                irrigation_amount = min(daily_requirement, moisture_deficit * 0.4)
                current_moisture += irrigation_amount * 0.4
            else:
                irrigation_amount = 0
            
            # Account for daily water loss
            daily_loss = crop_info['daily_water_mm'] * temp_factor * 0.4
            current_moisture = max(soil_props['wilting_point'], current_moisture - daily_loss)
            
            cumulative_water += irrigation_amount
            
            schedule.append({
                'day': day + 1,
                'date': date.strftime('%Y-%m-%d'),
                'growth_stage': current_stage,
                'irrigation_liters': round(irrigation_amount, 1),
                'soil_moisture_percent': round(current_moisture, 1),
                'temperature_factor': temp_factor,
                'stage_factor': stage_factor,
                'cumulative_water_liters': round(cumulative_water, 1)
            })
            
            # Update growth stage
            if day % 7 == 0:
                days_since_planting += 7
                current_stage = self._get_growth_stage(crop_type, days_since_planting)
        
        return {
            'zone_id': zone_data.get('zone_id', 'UNKNOWN'),
            'crop_type': crop_type,
            'target_yield_kg_per_zone': target_yield_kg_per_zone,
            'planning_period_days': planning_period_days,
            'soil_type': soil_type,
            'initial_soil_moisture': zone_data.get('soil_moisture_20cm', 30.0),
            'water_requirements': water_req,
            'irrigation_schedule': schedule,
            'summary': self._generate_schedule_summary(schedule, water_req)
        }

    def optimize_for_water_conservation(self, zone_data: Dict, crop_type: str, 
                                      target_yield_kg_per_zone: float) -> Dict:
        """Optimize irrigation plan for water conservation while maintaining yield"""
        
        # Create standard schedule
        standard_schedule = self.create_irrigation_schedule(
            zone_data, crop_type, target_yield_kg_per_zone, planning_period_days=30
        )
        
        # Optimization strategies
        optimization_strategies = {
            'timing_optimization': {
                'description': 'Irrigate during early morning/late evening to reduce evaporation',
                'water_savings_percent': 15,
                'implementation': 'Schedule irrigation for 05:00-07:00 and 18:00-20:00'
            },
            'moisture_sensor_optimization': {
                'description': 'Use real-time moisture data to avoid over-irrigation',
                'water_savings_percent': 20,
                'implementation': 'Only irrigate when soil moisture falls below 40%'
            },
            # FUTURE INTEGRATION: weather_based_adjustment
            # Requires external weather API (e.g. OpenWeatherMap)
            # 'weather_based_adjustment': {
            #     'description': 'Adjust irrigation based on weather forecasts',
            #     'water_savings_percent': 10,
            #     'implementation': 'Reduce irrigation by 30% on rainy days'
            # },
            'drip_irrigation_upgrade': {
                'description': 'Switch to drip irrigation for targeted water delivery',
                'water_savings_percent': 35,
                'implementation': 'Install drip irrigation system with emitters per zone'
            }
        }
        
        # Calculate optimized schedules
        optimized_schedules = {}
        for strategy_name, strategy_info in optimization_strategies.items():
            adjusted_schedule = []
            water_savings_factor = 1 - (strategy_info['water_savings_percent'] / 100)
            
            for day_plan in standard_schedule['irrigation_schedule']:
                optimized_plan = day_plan.copy()
                optimized_plan['irrigation_liters'] *= water_savings_factor
                optimized_plan['optimization_strategy'] = strategy_name
                adjusted_schedule.append(optimized_plan)
            
            optimized_schedules[strategy_name] = {
                'schedule': adjusted_schedule,
                'total_water_liters': sum(day['irrigation_liters'] for day in adjusted_schedule),
                'water_savings_liters': standard_schedule['summary']['total_irrigation_liters'] - 
                                       sum(day['irrigation_liters'] for day in adjusted_schedule),
                'strategy_info': strategy_info
            }
        
        return {
            'zone_id': zone_data.get('zone_id', 'UNKNOWN'),
            'crop_type': crop_type,
            'target_yield_kg_per_zone': target_yield_kg_per_zone,
            'standard_schedule': standard_schedule,
            'optimization_strategies': optimization_strategies,
            'optimized_schedules': optimized_schedules,
            'recommendation': self._select_best_optimization(optimized_schedules)
        }

    def monitor_irrigation_performance(self, zone_id: str, planned_schedule: List[Dict], 
                                    actual_moisture_readings: List[Dict]) -> Dict:
        """Monitor irrigation performance and provide recommendations"""
        
        performance_analysis = {
            'zone_id': zone_id,
            'monitoring_period_days': len(planned_schedule),
            'schedule_adherence': {},
            'efficiency_metrics': {},
            'recommendations': []
        }
        
        # Compare planned vs actual
        total_planned_water = sum(day['irrigation_liters'] for day in planned_schedule)
        
        # Calculate adherence metrics
        days_with_data = min(len(planned_schedule), len(actual_moisture_readings))
        
        if days_with_data > 0:
            moisture_deviations = []
            water_usage_efficiency = []
            
            for i in range(days_with_data):
                planned = planned_schedule[i]
                actual = actual_moisture_readings[i]
                
                # Moisture deviation
                planned_moisture = planned['soil_moisture_percent']
                actual_moisture = actual.get('soil_moisture_20cm', planned_moisture)
                deviation = abs(actual_moisture - planned_moisture)
                moisture_deviations.append(deviation)
                
                # Water usage efficiency
                if planned['irrigation_liters'] > 0:
                    efficiency = min(1.0, actual_moisture / planned_moisture)
                    water_usage_efficiency.append(efficiency)
            
            performance_analysis['schedule_adherence'] = {
                'average_moisture_deviation': np.mean(moisture_deviations),
                'max_moisture_deviation': np.max(moisture_deviations),
                'schedule_compliance_percentage': np.mean(water_usage_efficiency) * 100 if water_usage_efficiency else 0
            }
            
            # Generate recommendations
            avg_deviation = np.mean(moisture_deviations)
            if avg_deviation > 5.0:
                performance_analysis['recommendations'].append(
                    "High moisture variability detected - consider more frequent monitoring"
                )
            
            if np.mean(water_usage_efficiency) < 0.8:
                performance_analysis['recommendations'].append(
                    "Irrigation schedule not meeting targets - adjust timing or amounts"
                )
            
            if max(moisture_deviations) > 10.0:
                performance_analysis['recommendations'].append(
                    "Extreme moisture deviations - check for irrigation system issues"
                )
        
        return performance_analysis

    def _get_growth_stage(self, crop_type: str, days_since_planting: int) -> str:
        """Determine current growth stage based on days since planting"""
        
        stages = self.crop_water_requirements[crop_type]['critical_stages']
        cumulative_days = 0
        
        for stage_name, stage_info in stages.items():
            cumulative_days += stage_info['duration_days']
            if days_since_planting <= cumulative_days:
                return stage_name
        
        return 'maturity'

    def _get_temperature_factor(self, temperature_c: float) -> float:
        """Get temperature-based evapotranspiration factor"""
        
        if temperature_c < 20:
            return self.evapotranspiration_factors['cool']
        elif temperature_c <= 25:
            return self.evapotranspiration_factors['moderate']
        elif temperature_c <= 30:
            return self.evapotranspiration_factors['warm']
        else:
            return self.evapotranspiration_factors['hot']

    def _generate_schedule_summary(self, schedule: List[Dict], water_req: Dict) -> Dict:
        """Generate summary statistics for irrigation schedule"""
        
        total_irrigation = sum(day['irrigation_liters'] for day in schedule)
        irrigated_days = sum(1 for day in schedule if day['irrigation_liters'] > 0)
        
        return {
            'total_irrigation_liters': round(total_irrigation, 1),
            'irrigated_days': irrigated_days,
            'average_daily_irrigation': round(total_irrigation / len(schedule), 1),
            'peak_irrigation_day': max(schedule, key=lambda x: x['irrigation_liters'])['day'],
            'water_efficiency_vs_target': round((total_irrigation / water_req['total_water_required_liters']) * 100, 1)
        }

    def _select_best_optimization(self, optimized_schedules: Dict) -> Dict:
        """Select the best optimization strategy based on water savings and feasibility"""
        
        best_strategy = None
        best_score = -1
        
        for strategy_name, strategy_data in optimized_schedules.items():
            water_savings = strategy_data['water_savings_liters']
            
            # Simplicity score (lower is better, so we invert)
            complexity_scores = {
                'timing_optimization': 1,
                'moisture_sensor_optimization': 2,
                # 'weather_based_adjustment': 3,  # FUTURE: requires weather API
                'drip_irrigation_upgrade': 4
            }
            
            complexity = complexity_scores.get(strategy_name, 5)
            score = water_savings / complexity  # Higher score is better
            
            if score > best_score:
                best_score = score
                best_strategy = {
                    'strategy_name': strategy_name,
                    'water_savings_liters': water_savings,
                    'implementation': strategy_data['strategy_info']['implementation'],
                    'score': round(score, 2)
                }
        
        return best_strategy

# Global instance for use across the application
irrigation_engine = IrrigationEngine()
