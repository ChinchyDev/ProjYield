"""
Test the irrigation planning feature for yield goal optimization
"""

import sys
import os
# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from irrigation_planner import create_irrigation_plan_from_yield_goal, IrrigationPlanner
import json

def test_irrigation_planning():
    """Test irrigation planning for different yield goals"""
    print("💧 Testing Irrigation Planning for Yield Goals")
    print("=" * 50)
    
    # Example zone data
    zone_data = {
        'zone_id': 'Z_1.286400_36.817200',
        'soil_type': 'loamy',
        'soil_moisture_20cm': 28.5,
        'temperature_c': 26.0,
        'days_since_planting': 15,
        'nitrogen_ppm': 45.0,
        'phosphorus_ppm': 25.0,
        'potassium_ppm': 35.0,
        'ph_level': 6.2,
        'organic_matter_percent': 2.1
    }
    
    # Test different scenarios
    scenarios = [
        {'crop': 'maize', 'yield_goal': 6.0, 'description': 'Conservative maize yield'},
        {'crop': 'maize', 'yield_goal': 8.0, 'description': 'Optimal maize yield'},
        {'crop': 'maize', 'yield_goal': 10.0, 'description': 'Ambitious maize yield'},
        {'crop': 'tomatoes', 'yield_goal': 15.0, 'description': 'Conservative tomato yield'},
        {'crop': 'tomatoes', 'yield_goal': 20.0, 'description': 'Optimal tomato yield'},
        {'crop': 'beans', 'yield_goal': 8.0, 'description': 'Conservative bean yield'},
        {'crop': 'beans', 'yield_goal': 12.0, 'description': 'Optimal bean yield'}
    ]
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n📊 Scenario {i}: {scenario['description']}")
        print("-" * 40)
        print(f"🌾 Crop: {scenario['crop']}")
        print(f"🎯 Yield Goal: {scenario['yield_goal']} kg/zone")
        
        try:
            # Create irrigation plan
            plan = create_irrigation_plan_from_yield_goal(
                zone_data, scenario['crop'], scenario['yield_goal']
            )
            
            schedule = plan['irrigation_schedule']
            water_req = schedule['water_requirements']
            summary = schedule['summary']
            optimization = plan['water_optimization']
            
            print(f"💧 Total Water Required: {water_req['total_water_required_liters']:.1f} liters")
            print(f"📅 Planning Period: {schedule['planning_period_days']} days")
            print(f"🌱 Daily Water Requirement: {water_req['daily_water_requirement_liters']:.1f} liters")
            print(f"💰 Water Use Efficiency: {water_req['water_use_efficiency']:.1f} kg/m³")
            print(f"📊 Irrigation Days: {summary['irrigated_days']} of {schedule['planning_period_days']}")
            print(f"📈 Average Daily Irrigation: {summary['average_daily_irrigation']:.1f} liters")
            
            # Show optimization recommendation
            rec = optimization['recommendation']
            print(f"🏆 Best Optimization: {rec['strategy_name']}")
            print(f"💰 Water Savings: {rec['water_savings_liters']:.1f} liters")
            print(f"🔧 Implementation: {rec['implementation']}")
            
            # Show monitoring guidelines
            monitoring = plan['monitoring_guidelines']
            print(f"🔍 Monitoring: {monitoring['measurement_frequency']}")
            print(f"🎯 Target Moisture: {monitoring['target_moisture_range'][0]}% - {monitoring['target_moisture_range'][1]}%")
            
        except Exception as e:
            print(f"❌ Error: {e}")
    
    print("\n" + "=" * 50)
    print("✅ Irrigation Planning Test Complete!")

def test_water_conservation_optimization():
    """Test water conservation optimization strategies"""
    print("\n💰 Testing Water Conservation Optimization")
    print("=" * 50)
    
    zone_data = {
        'zone_id': 'Z_1.286400_36.817200',
        'soil_type': 'loamy',
        'soil_moisture_20cm': 30.0,
        'temperature_c': 25.0,
        'days_since_planting': 10
    }
    
    planner = IrrigationPlanner()
    
    # Test optimization for maize
    print("🌾 Testing Maize Water Conservation (Yield Goal: 8.0 kg/zone)")
    print("-" * 40)
    
    optimization = planner.optimize_for_water_conservation(
        zone_data, 'maize', 8.0
    )
    
    standard = optimization['standard_schedule']
    print(f"📊 Standard Water Use: {standard['summary']['total_irrigation_liters']:.1f} liters")
    
    print("\n🔄 Available Optimization Strategies:")
    for strategy_name, strategy_data in optimization['optimized_schedules'].items():
        strategy_info = strategy_data['strategy_info']
        savings_percent = strategy_info['water_savings_percent']
        savings_liters = strategy_data['water_savings_liters']
        
        print(f"\n🏆 {strategy_name.replace('_', ' ').title()}:")
        print(f"   💰 Water Savings: {savings_liters:.1f} liters ({savings_percent}%)")
        print(f"   📝 Description: {strategy_info['description']}")
        print(f"   🔧 Implementation: {strategy_info['implementation']}")
    
    # Show recommendation
    rec = optimization['recommendation']
    print(f"\n🎯 Recommended Strategy:")
    print(f"   🏆 Strategy: {rec['strategy_name']}")
    print(f"   💰 Savings: {rec['water_savings_liters']:.1f} liters")
    print(f"   ⭐ Score: {rec['score']:.2f}")
    print(f"   🔧 Implementation: {rec['implementation']}")

def test_crop_water_requirements():
    """Test crop water requirements database"""
    print("\n🌱 Testing Crop Water Requirements Database")
    print("=" * 50)
    
    planner = IrrigationPlanner()
    
    for crop_type, crop_info in planner.crop_water_requirements.items():
        print(f"\n🌾 {crop_type.upper()}:")
        print(f"   💧 Daily Water Requirement: {crop_info['daily_water_mm']} mm/day")
        print(f"   🎯 Optimal Moisture Range: {crop_info['optimal_moisture_range']}%")
        print(f"   💰 Water Use Efficiency: {crop_info['water_use_efficiency']} kg yield per m³")
        
        print(f"   🌱 Growth Stages:")
        for stage_name, stage_info in crop_info['critical_growth_stages'].items():
            print(f"      • {stage_name}: {stage_info['duration_days']} days (factor: {stage_info['water_factor']})")
    
    print(f"\n🌡️ Temperature Factors:")
    for temp_type, factor in planner.evapotranspiration_factors.items():
        print(f"   • {temp_type}: {factor}x")
    
    print(f"\n🏗️ Soil Water Holding Capacity:")
    for soil_type, props in planner.soil_water_holding_capacity.items():
        print(f"   • {soil_type}: FC={props['field_capacity']}%, WP={props['wilting_point']}%, AW={props['available_water']}%")

if __name__ == "__main__":
    test_irrigation_planning()
    test_water_conservation_optimization()
    test_crop_water_requirements()
    
    print("\n" + "=" * 60)
    print("🎉 ALL IRRIGATION PLANNING TESTS COMPLETED!")
    print("💡 Key Features Demonstrated:")
    print("   ✅ Yield goal-based irrigation planning")
    print("   ✅ Crop-specific water requirements")
    print("   ✅ Growth stage optimization")
    print("   ✅ Water conservation strategies")
    print("   ✅ Performance monitoring guidelines")
    print("   ✅ Temperature and soil type adjustments")
    print("🚀 Ready for integration with YieldVision GUI!")
