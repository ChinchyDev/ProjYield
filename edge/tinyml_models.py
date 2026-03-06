"""
YieldVision TinyML Models for Arduino Mega 2560
Lightweight models for edge deployment on microcontrollers
"""

import numpy as np
import json
from typing import Dict, List, Tuple, Optional
import struct

class TinyMLSoilModel:
    """
    Simplified soil health model for Arduino Mega 2560
    Uses decision tree approximation for minimal memory footprint
    """
    
    def __init__(self):
        # Simplified decision tree thresholds (optimized for Arduino)
        self.moisture_threshold = 30.0
        self.nitrogen_threshold = 80.0
        self.phosphorus_threshold = 40.0
        self.potassium_threshold = 60.0
        self.ph_low_threshold = 6.0
        self.ph_high_threshold = 7.5
        
        # Health scoring weights (sum to 1.0)
        self.weights = {
            'moisture': 0.25,
            'nitrogen': 0.25,
            'phosphorus': 0.20,
            'potassium': 0.20,
            'ph': 0.10
        }
    
    def predict_soil_health(self, sensor_data: Dict) -> float:
        """
        Predict soil health score (0.0 - 1.0)
        Optimized for Arduino Mega 2560 with minimal memory usage
        """
        # Extract sensor values
        moisture = sensor_data.get('soil_moisture_20cm', 30.0)
        nitrogen = sensor_data.get('nitrogen_ppm', 50.0)
        phosphorus = sensor_data.get('phosphorus_ppm', 30.0)
        potassium = sensor_data.get('potassium_ppm', 40.0)
        ph = sensor_data.get('ph_level', 7.0)
        
        # Calculate individual scores (0.0 - 1.0)
        moisture_score = min(1.0, moisture / self.moisture_threshold)
        nitrogen_score = min(1.0, nitrogen / self.nitrogen_threshold)
        phosphorus_score = min(1.0, phosphorus / self.phosphorus_threshold)
        potassium_score = min(1.0, potassium / self.potassium_threshold)
        
        # pH score (optimal range 6.0-7.5)
        if self.ph_low_threshold <= ph <= self.ph_high_threshold:
            ph_score = 1.0
        elif ph < self.ph_low_threshold:
            ph_score = max(0.0, ph / self.ph_low_threshold)
        else:
            ph_score = max(0.0, (10.0 - ph) / (10.0 - self.ph_high_threshold))
        
        # Weighted average
        health_score = (
            moisture_score * self.weights['moisture'] +
            nitrogen_score * self.weights['nitrogen'] +
            phosphorus_score * self.weights['phosphorus'] +
            potassium_score * self.weights['potassium'] +
            ph_score * self.weights['ph']
        )
        
        return round(health_score, 3)
    
    def recommend_simple_action(self, sensor_data: Dict) -> Dict:
        """
        Recommend simple action for immediate response
        Returns action that can be executed without complex processing
        """
        health_score = self.predict_soil_health(sensor_data)
        moisture = sensor_data.get('soil_moisture_20cm', 30.0)
        nitrogen = sensor_data.get('nitrogen_ppm', 50.0)
        ph = sensor_data.get('ph_level', 7.0)
        
        action = {'type': 'none', 'amount': 0, 'reason': 'Conditions optimal'}
        
        # Priority-based decision tree
        if moisture < 20.0:
            action = {
                'type': 'irrigate',
                'amount': 5,  # 5 liters
                'reason': 'Critical moisture deficit'
            }
        elif nitrogen < 40.0:
            action = {
                'type': 'fertilize_nitrogen',
                'amount': 2,  # 2 kg
                'reason': 'Low nitrogen detected'
            }
        elif ph < 5.5:
            action = {
                'type': 'adjust_ph_up',
                'amount': 1,  # 1 liter lime
                'reason': 'Soil too acidic'
            }
        elif ph > 8.0:
            action = {
                'type': 'adjust_ph_down',
                'amount': 1,  # 1 liter sulfur
                'reason': 'Soil too alkaline'
            }
        elif moisture < 30.0:
            action = {
                'type': 'irrigate',
                'amount': 3,  # 3 liters
                'reason': 'Moderate moisture deficit'
            }
        
        action['health_score'] = health_score
        return action

class TinyMLIrrigationModel:
    """
    Simplified irrigation model for Arduino Mega 2560
    Uses rule-based approach with minimal computation
    """
    
    def __init__(self):
        # Crop-specific water requirements (liters per day for 4m² zone)
        self.crop_requirements = {
            'maize': 8.0,
            'tomatoes': 10.0,
            'wheat': 6.0,
            'beans': 5.0,
            'potatoes': 9.0
        }
        
        # Soil type multipliers
        self.soil_multipliers = {
            'sandy': 1.3,    # Drains faster
            'clay': 0.8,     # Holds water
            'loamy': 1.0,    # Balanced
            'silty': 1.1     # Good drainage
        }
        
        # Temperature adjustments
        self.temp_adjustments = {
            'cool': 0.8,      # < 20°C
            'moderate': 1.0,  # 20-25°C
            'warm': 1.2,      # 25-30°C
            'hot': 1.4        # > 30°C
        }
    
    def calculate_irrigation_need(self, sensor_data: Dict) -> Dict:
        """
        Calculate irrigation need for immediate action
        Optimized for real-time Arduino processing
        """
        crop_type = sensor_data.get('crop_type', 'maize')
        soil_type = sensor_data.get('soil_type', 'loamy')
        moisture = sensor_data.get('soil_moisture_20cm', 30.0)
        temperature = sensor_data.get('temperature_c', 25.0)
        
        # Get base requirement
        base_requirement = self.crop_requirements.get(crop_type, 8.0)
        
        # Apply soil multiplier
        soil_multiplier = self.soil_multipliers.get(soil_type, 1.0)
        
        # Apply temperature adjustment
        temp_category = self._get_temp_category(temperature)
        temp_multiplier = self.temp_adjustments.get(temp_category, 1.0)
        
        # Calculate adjusted requirement
        adjusted_requirement = base_requirement * soil_multiplier * temp_multiplier
        
        # Calculate deficit
        moisture_deficit = max(0, 35.0 - moisture)  # Target 35% moisture
        
        # Determine irrigation amount
        if moisture_deficit > 15.0:
            irrigation_amount = adjusted_requirement * 1.5  # Heavy irrigation
            urgency = 'high'
        elif moisture_deficit > 8.0:
            irrigation_amount = adjusted_requirement  # Normal irrigation
            urgency = 'medium'
        elif moisture_deficit > 3.0:
            irrigation_amount = adjusted_requirement * 0.5  # Light irrigation
            urgency = 'low'
        else:
            irrigation_amount = 0.0
            urgency = 'none'
        
        return {
            'irrigation_liters': round(irrigation_amount, 1),
            'urgency': urgency,
            'moisture_deficit': round(moisture_deficit, 1),
            'base_requirement': round(base_requirement, 1),
            'soil_multiplier': soil_multiplier,
            'temp_multiplier': temp_multiplier
        }
    
    def _get_temp_category(self, temp: float) -> str:
        """Categorize temperature for adjustment factor"""
        if temp < 20:
            return 'cool'
        elif temp <= 25:
            return 'moderate'
        elif temp <= 30:
            return 'warm'
        else:
            return 'hot'

class TinyMLSensorFusion:
    """
    Sensor fusion model for combining multiple sensor readings
    Optimized for Arduino Mega 2560 with limited RAM
    """
    
    def __init__(self):
        # Sensor reliability weights (based on sensor quality)
        self.sensor_weights = {
            'soil_moisture_20cm': 0.3,
            'soil_moisture_5cm': 0.2,
            'nitrogen_ppm': 0.2,
            'phosphorus_ppm': 0.1,
            'potassium_ppm': 0.1,
            'ph_level': 0.1
        }
        
        # Outlier detection thresholds
        self.outlier_thresholds = {
            'soil_moisture': (0.0, 60.0),
            'nitrogen_ppm': (0.0, 300.0),
            'phosphorus_ppm': (0.0, 200.0),
            'potassium_ppm': (0.0, 250.0),
            'ph_level': (4.0, 9.0),
            'temperature': (-10.0, 50.0)
        }
    
    def validate_sensors(self, sensor_data: Dict) -> Dict:
        """
        Validate sensor readings and detect outliers
        Simple statistical validation for Arduino
        """
        validated_data = sensor_data.copy()
        outliers = []
        
        # Check each sensor value against thresholds
        for sensor, (min_val, max_val) in self.outlier_thresholds.items():
            value = sensor_data.get(sensor.replace('_ppm', '_ppm').replace('soil_moisture', 'soil_moisture_20cm'))
            
            if value is not None:
                if value < min_val or value > max_val:
                    outliers.append(sensor)
                    # Replace with default value
                    if 'moisture' in sensor:
                        validated_data[sensor] = 30.0
                    elif 'ppm' in sensor:
                        validated_data[sensor] = 50.0
                    elif 'ph_level' in sensor:
                        validated_data[sensor] = 7.0
                    elif 'temperature' in sensor:
                        validated_data[sensor] = 25.0
        
        return {
            'validated_data': validated_data,
            'outliers_detected': outliers,
            'data_quality': 'good' if not outliers else 'suspicious'
        }
    
    def fuse_moisture_readings(self, sensor_data: Dict) -> float:
        """
        Fuse multiple moisture readings into single value
        Weighted average based on depth reliability
        """
        moisture_5cm = sensor_data.get('soil_moisture_5cm')
        moisture_20cm = sensor_data.get('soil_moisture_20cm')
        moisture_50cm = sensor_data.get('soil_moisture_50cm')
        
        readings = []
        weights = []
        
        if moisture_5cm is not None:
            readings.append(moisture_5cm)
            weights.append(0.2)  # Less reliable (more variable)
        
        if moisture_20cm is not None:
            readings.append(moisture_20cm)
            weights.append(0.5)  # Most reliable (root zone)
        
        if moisture_50cm is not None:
            readings.append(moisture_50cm)
            weights.append(0.3)  # Moderately reliable
        
        if not readings:
            return 30.0  # Default value
        
        # Weighted average
        fused_moisture = sum(r * w for r, w in zip(readings, weights)) / sum(weights)
        return round(fused_moisture, 1)

class TinyMLModelManager:
    """
    Main manager for all TinyML models on Arduino Mega 2560
    Coordinates model execution and decision making
    """
    
    def __init__(self):
        self.soil_model = TinyMLSoilModel()
        self.irrigation_model = TinyMLIrrigationModel()
        self.sensor_fusion = TinyMLSensorFusion()
        
        # Model memory usage estimation (bytes)
        self.memory_usage = {
            'soil_model': 512,      # Simple thresholds and weights
            'irrigation_model': 768, # Lookup tables and multipliers
            'sensor_fusion': 384,   # Validation rules
            'total': 1664           # Total < 2KB (Arduino Mega has 8KB SRAM)
        }
    
    def process_sensor_data(self, sensor_data: Dict) -> Dict:
        """
        Process sensor data and return comprehensive analysis
        Main entry point for Arduino edge processing
        """
        # Validate sensor readings
        validation_result = self.sensor_fusion.validate_sensors(sensor_data)
        validated_data = validation_result['validated_data']
        
        # Fuse moisture readings
        fused_moisture = self.sensor_fusion.fuse_moisture_readings(validated_data)
        validated_data['fused_moisture'] = fused_moisture
        
        # Predict soil health
        health_score = self.soil_model.predict_soil_health(validated_data)
        
        # Get simple action recommendation
        simple_action = self.soil_model.recommend_simple_action(validated_data)
        
        # Calculate irrigation need
        irrigation_need = self.irrigation_model.calculate_irrigation_need(validated_data)
        
        # Compile results
        result = {
            'timestamp': sensor_data.get('timestamp', 'unknown'),
            'zone_id': sensor_data.get('zone_id', 'unknown'),
            'soil_health_score': health_score,
            'fused_moisture': fused_moisture,
            'simple_action': simple_action,
            'irrigation_need': irrigation_need,
            'data_quality': validation_result['data_quality'],
            'outliers_detected': validation_result['outliers_detected'],
            'memory_usage_bytes': self.memory_usage['total']
        }
        
        return result
    
    def get_arduino_code_template(self) -> str:
        """
        Generate Arduino code template for TinyML deployment
        Returns C++ code structure for Arduino Mega 2560
        """
        return '''
// YieldVision TinyML for Arduino Mega 2560
// Optimized for precision farming edge processing

#include <Arduino.h>
#include <SoftwareSerial.h>

// Sensor pins
#define MOISTURE_PIN_5CM A0
#define MOISTURE_PIN_20CM A1
#define NITROGEN_PIN A2
#define PHOSPHORUS_PIN A3
#define POTASSIUM_PIN A4
#define PH_PIN A5
#define TEMP_PIN A6

// Actuator pins
#define IRRIGATION_PUMP_RELAY 2
#define NUTRIENT_PUMP_RELAY 3
#define PH_UP_PUMP_RELAY 4
#define PH_DOWN_PUMP_RELAY 5

// TinyML Model Class
class TinyMLSoilModel {
private:
    float moisture_threshold = 30.0;
    float nitrogen_threshold = 80.0;
    
public:
    float predictSoilHealth(float moisture, float nitrogen, float phosphorus, float potassium, float ph) {
        float moisture_score = min(1.0, moisture / moisture_threshold);
        float nitrogen_score = min(1.0, nitrogen / nitrogen_threshold);
        
        return (moisture_score * 0.5 + nitrogen_score * 0.5);
    }
    
    String recommendAction(float moisture, float nitrogen, float ph) {
        if (moisture < 20.0) return "IRRIGATE_HIGH";
        if (nitrogen < 40.0) return "FERTILIZE_N";
        if (ph < 6.0) return "PH_UP";
        if (ph > 8.0) return "PH_DOWN";
        return "NONE";
    }
};

TinyMLSoilModel soilModel;

void setup() {
    Serial.begin(9600);
    
    // Initialize sensor pins
    pinMode(MOISTURE_PIN_5CM, INPUT);
    pinMode(MOISTURE_PIN_20CM, INPUT);
    pinMode(NITROGEN_PIN, INPUT);
    pinMode(PHOSPHORUS_PIN, INPUT);
    pinMode(POTASSIUM_PIN, INPUT);
    pinMode(PH_PIN, INPUT);
    pinMode(TEMP_PIN, INPUT);
    
    // Initialize actuator pins
    pinMode(IRRIGATION_PUMP_RELAY, OUTPUT);
    pinMode(NUTRIENT_PUMP_RELAY, OUTPUT);
    pinMode(PH_UP_PUMP_RELAY, OUTPUT);
    pinMode(PH_DOWN_PUMP_RELAY, OUTPUT);
    
    Serial.println("YieldVision TinyML Edge Processing Started");
}

void loop() {
    // Read sensors
    float moisture_5cm = analogRead(MOISTURE_PIN_5CM) * 100.0 / 1023.0;
    float moisture_20cm = analogRead(MOISTURE_PIN_20CM) * 100.0 / 1023.0;
    float nitrogen = analogRead(NITROGEN_PIN) * 300.0 / 1023.0;
    float phosphorus = analogRead(PHOSPHORUS_PIN) * 200.0 / 1023.0;
    float potassium = analogRead(POTASSIUM_PIN) * 250.0 / 1023.0;
    float ph = analogRead(PH_PIN) * 14.0 / 1023.0;
    
    // Process with TinyML
    float health_score = soilModel.predictSoilHealth(moisture_20cm, nitrogen, phosphorus, potassium, ph);
    String action = soilModel.recommendAction(moisture_20cm, nitrogen, ph);
    
    // Execute action
    executeAction(action);
    
    // Send results to server
    sendResultsToServer(moisture_20cm, nitrogen, phosphorus, potassium, ph, health_score, action);
    
    delay(60000); // Process every minute
}

void executeAction(String action) {
    // Turn off all actuators first
    digitalWrite(IRRIGATION_PUMP_RELAY, LOW);
    digitalWrite(NUTRIENT_PUMP_RELAY, LOW);
    digitalWrite(PH_UP_PUMP_RELAY, LOW);
    digitalWrite(PH_DOWN_PUMP_RELAY, LOW);
    
    if (action == "IRRIGATE_HIGH") {
        digitalWrite(IRRIGATION_PUMP_RELAY, HIGH);
        delay(5000); // 5 seconds of irrigation
        digitalWrite(IRRIGATION_PUMP_RELAY, LOW);
    } else if (action == "FERTILIZE_N") {
        digitalWrite(NUTRIENT_PUMP_RELAY, HIGH);
        delay(2000); // 2 seconds of nutrient application
        digitalWrite(NUTRIENT_PUMP_RELAY, LOW);
    } else if (action == "PH_UP") {
        digitalWrite(PH_UP_PUMP_RELAY, HIGH);
        delay(1000); // 1 second of pH adjustment
        digitalWrite(PH_UP_PUMP_RELAY, LOW);
    } else if (action == "PH_DOWN") {
        digitalWrite(PH_DOWN_PUMP_RELAY, HIGH);
        delay(1000); // 1 second of pH adjustment
        digitalWrite(PH_DOWN_PUMP_RELAY, LOW);
    }
}

void sendResultsToServer(float moisture, float nitrogen, float phosphorus, float potassium, float ph, float health, String action) {
    Serial.print("DATA:");
    Serial.print(moisture); Serial.print(",");
    Serial.print(nitrogen); Serial.print(",");
    Serial.print(phosphorus); Serial.print(",");
    Serial.print(potassium); Serial.print(",");
    Serial.print(ph); Serial.print(",");
    Serial.print(health); Serial.print(",");
    Serial.println(action);
}
        '''

# Global instance for use across the application
tinyml_manager = TinyMLModelManager()
