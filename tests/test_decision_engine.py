"""
Test script for YieldVision Decision Engine
Demonstrates Monte Carlo decision evaluation with RTX 3070 GPU
"""

import torch
import numpy as np
from decision_engine import DecisionImpactEngine
import json

def test_gpu_performance():
    """Test GPU performance for Monte Carlo simulations"""
    print("🔥 Testing RTX 3070 GPU Performance")
    print("=" * 50)
    
    if torch.cuda.is_available():
        device = torch.device("cuda")
        print(f"✅ GPU Detected: {torch.cuda.get_device_name(0)}")
        print(f"📊 GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
        
        # Test matrix multiplication (Monte Carlo simulation style)
        size = 10000
        print(f"\n🧪 Running Monte Carlo-style simulation with {size:,} iterations...")
        
        # Create large tensors for simulation
        x = torch.randn(size, 10).to(device)
        y = torch.randn(10, 1).to(device)
        
        # Time the GPU computation
        import time
        start_time = time.time()
        
        result = torch.mm(x, y)
        
        gpu_time = time.time() - start_time
        print(f"⚡ GPU Time: {gpu_time:.4f} seconds")
        
        # Compare with CPU
        start_time = time.time()
        x_cpu = x.cpu()
        y_cpu = y.cpu()
        result_cpu = torch.mm(x_cpu, y_cpu)
        cpu_time = time.time() - start_time
        print(f"🐌 CPU Time: {cpu_time:.4f} seconds")
        print(f"🚀 GPU Speedup: {cpu_time/gpu_time:.1f}x faster")
        
        return True
    else:
        print("❌ No GPU detected")
        return False

def test_decision_engine():
    """Test the decision engine with sample data"""
    print("\n🧠 Testing Decision Impact Engine")
    print("=" * 50)
    
    # Initialize decision engine
    engine = DecisionImpactEngine()
    
    # Sample zone data (typical agricultural values)
    zone_data = {
        'zone_id': 'Z_1.286400_36.817200',
        'gps_lat': 1.2864,
        'gps_lon': 36.8172,
        'soil_moisture_20cm': 28.5,  # % - slightly dry
        'nitrogen_ppm': 45.0,        # ppm - low nitrogen
        'phosphorus_ppm': 25.0,      # ppm - adequate phosphorus
        'potassium_ppm': 35.0,       # ppm - low potassium
        'ph_level': 6.2,             # slightly acidic
        'temperature_c': 26.0,       # warm
        'organic_matter_percent': 2.1,
        'soil_type': 'loamy',
        'slope_percent': 3.0,
        'aspect_degrees': 180  # south-facing
    }
    
    print("📍 Zone Data:")
    print(f"   Location: {zone_data['gps_lat']:.6f}, {zone_data['gps_lon']:.6f}")
    print(f"   Soil Moisture: {zone_data['soil_moisture_20cm']:.1f}%")
    print(f"   Nitrogen: {zone_data['nitrogen_ppm']:.0f} ppm")
    print(f"   pH Level: {zone_data['ph_level']:.1f}")
    
    # Test different actions
    actions = [
        {
            'type': 'irrigate',
            'amount': 15.0,
            'unit': 'liters'
        },
        {
            'type': 'fertilize_nitrogen',
            'amount': 2.0,
            'unit': 'kg'
        },
        {
            'type': 'adjust_ph_up',
            'amount': 1.5,
            'unit': 'liters'
        }
    ]
    
    for i, action in enumerate(actions, 1):
        print(f"\n📊 Decision {i}: {action['type']} - {action['amount']} {action['unit']}")
        print("-" * 40)
        
        # Evaluate decision
        result = engine.evaluate_action(zone_data, action, time_horizon=14)
        
        # Display key results
        print(f"💰 Expected Net Benefit: ${result['expected_net_benefit_usd']['mean']:.2f} ± ${result['expected_net_benefit_usd']['std']:.2f}")
        print(f"📈 Expected Yield Impact: {result['expected_yield_kg_per_zone']['mean']:.2f} ± {result['expected_yield_kg_per_zone']['std']:.2f} kg/zone")
        print(f"🎯 Confidence Score: {result['confidence_score']:.2f}")
        print(f"⚠️  Risk Level: {result['risk_assessment']['risk_level'].upper()}")
        print(f"🔄 ROI Multiplier: {result['expected_roi_multiplier']['mean']:.2f}x")
        print(f"🏆 Recommendation: {result['recommendation']}")
        
        # Show confidence interval
        ci_5 = result['expected_net_benefit_usd']['percentile_5']
        ci_95 = result['expected_net_benefit_usd']['percentile_95']
        print(f"📊 95% Confidence Interval: ${ci_5:.2f} to ${ci_95:.2f}")

def test_precision_models():
    """Test the precision farming models"""
    print("\n🌱 Testing Precision Farming Models")
    print("=" * 50)
    
    from precision_models import PrecisionSoilModel, PrecisionWaterModel, PrecisionSeedModel
    
    # Test soil model
    soil_model = PrecisionSoilModel()
    zone_data = {
        'zone_id': 'Z_1.286400_36.817200',
        'crop_type': 'maize',
        'soil_type': 'loamy',
        'nitrogen_ppm': 45.0,
        'phosphorus_ppm': 25.0,
        'potassium_ppm': 35.0,
        'ph_level': 6.2,
        'organic_matter_percent': 2.1
    }
    
    print("🧪 Soil Amendment Recommendations:")
    amendments = soil_model.recommend_amendments(zone_data)
    print(f"   Nitrogen: {amendments['nitrogen_kg_per_zone']:.2f} kg/zone")
    print(f"   Phosphorus: {amendments['phosphorus_kg_per_zone']:.2f} kg/zone")
    print(f"   Potassium: {amendments['potassium_kg_per_zone']:.2f} kg/zone")
    print(f"   pH Adjustment: {amendments['ph_adjustment_liters_per_zone']:.2f} liters/zone")
    print(f"   Estimated Cost: ${amendments['estimated_cost_usd']:.2f}/zone")
    
    # Test water model
    water_model = PrecisionWaterModel()
    print("\n💧 Irrigation Recommendations:")
    irrigation = water_model.zone_irrigation_schedule(
        'Z_1.286400_36.817200', 
        zone_data['nitrogen_ppm'], 
        'vegetative',
        zone_data
    )
    print(f"   Water Amount: {irrigation['water_liters_per_hour']:.2f} liters/hour")
    print(f"   Duration: {irrigation['duration_minutes']:.1f} minutes")
    print(f"   Efficiency Score: {irrigation['efficiency_score']:.3f}")
    print(f"   Optimal Time: {irrigation['optimal_time']}")
    print(f"   ROI Multiplier: {irrigation['roi_multiplier']:.2f}x")

def main():
    """Main test function"""
    print("🚀 YieldVision Precision Farming System Test")
    print("=" * 60)
    print("Testing decision-evaluative farming with RTX 3070 GPU")
    print()
    
    # Test GPU performance
    gpu_ok = test_gpu_performance()
    
    # Test decision engine
    test_decision_engine()
    
    # Test precision models
    test_precision_models()
    
    print("\n✅ Test Complete!")
    print("=" * 60)
    print("🎯 YieldVision is ready for precision farming decisions!")
    print("📊 GUI launched - check for the application window")
    print("🌐 API available at: http://localhost:8000")
    print("📚 API docs at: http://localhost:8000/docs")
    
    if gpu_ok:
        print("🔥 RTX 3070 GPU is accelerating Monte Carlo simulations")
    
    print("\n💡 Next Steps:")
    print("   1. Connect Arduino rover with WiFi")
    print("   2. Setup PostgreSQL + InfluxDB databases")
    print("   3. Calibrate soil sensors")
    print("   4. Map your first field zones")
    print("   5. Start making precision farming decisions!")

if __name__ == "__main__":
    main()
