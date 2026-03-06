"""
Test the new best simulation feature in decision engine
"""

import sys
import os
# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from decision_engine import DecisionImpactEngine

def test_best_simulation():
    """Test that best simulation results are included in decision evaluation"""
    print("🏆 Testing Best Simulation Feature")
    print("=" * 40)
    
    # Initialize decision engine
    engine = DecisionImpactEngine()
    # Temporarily reduce iterations for quick test
    original_iterations = engine.mc_iterations
    engine.mc_iterations = 100
    
    # Create test zone data
    zone_data = {
        'zone_id': 'TEST_ZONE_001',
        'soil_moisture_20cm': 28.5,
        'nitrogen_ppm': 45.0,
        'phosphorus_ppm': 25.0,
        'potassium_ppm': 35.0,
        'ph_level': 6.2,
        'temperature_c': 26.0,
        'organic_matter_percent': 2.1,
        'soil_type': 'loamy'
    }
    
    # Test action
    action = {
        'type': 'irrigate',
        'amount': 20.0,
        'unit': 'liters'
    }
    
    print(f"📍 Zone: {zone_data['zone_id']}")
    print(f"💧 Action: {action['type']} {action['amount']} {action['unit']}")
    print(f"🔢 Monte Carlo Iterations: {engine.mc_iterations}")
    print()
    
    # Evaluate decision
    result = engine.evaluate_action(zone_data, action, time_horizon=14)
    
    # Display best simulation results
    print("🏆 BEST SIMULATION RESULTS:")
    print("-" * 30)
    best_sim = result['best_simulation']
    print(f"📈 Expected Yield: {best_sim['expected_yield_kg_per_zone']:.3f} kg/zone")
    print(f"💧 Water Efficiency: {best_sim['water_efficiency']:.2f}%")
    print(f"🌱 Soil Health Score: {best_sim['soil_health_score']:.3f}")
    print(f"💰 Net Benefit: ${best_sim['net_benefit_usd']:.3f}")
    print(f"📊 ROI Multiplier: {best_sim['roi_multiplier']:.2f}x")
    print(f"🏅 Simulation Rank: #{best_sim['simulation_rank']} of {result['monte_carlo_iterations']}")
    print()
    
    # Compare with average results
    print("📊 COMPARISON WITH AVERAGE:")
    print("-" * 30)
    avg_yield = result['expected_yield_kg_per_zone']['mean']
    avg_benefit = result['expected_net_benefit_usd']['mean']
    
    yield_improvement = ((best_sim['expected_yield_kg_per_zone'] - avg_yield) / avg_yield) * 100
    benefit_improvement = ((best_sim['net_benefit_usd'] - avg_benefit) / avg_benefit) * 100
    
    print(f"📈 Yield Improvement: {yield_improvement:+.1f}% vs average")
    print(f"💰 Benefit Improvement: {benefit_improvement:+.1f}% vs average")
    print()
    
    # Show range
    print("📏 SIMULATION RANGE:")
    print("-" * 30)
    yield_range = result['expected_yield_kg_per_zone']
    print(f"📈 Yield Range: {yield_range['min']:.3f} - {yield_range['max']:.3f} kg/zone")
    print(f"🎯 Best vs Worst: {(yield_range['max'] / yield_range['min']):.1f}x difference")
    print()
    
    # Test different actions
    print("🔄 TESTING DIFFERENT ACTIONS:")
    print("-" * 30)
    
    actions = [
        {'type': 'fertilize_nitrogen', 'amount': 2.0, 'unit': 'kg'},
        {'type': 'irrigate', 'amount': 15.0, 'unit': 'liters'},
        {'type': 'adjust_ph_up', 'amount': 1.0, 'unit': 'liters'}
    ]
    
    for action in actions:
        result = engine.evaluate_action(zone_data, action, time_horizon=14)
        best_sim = result['best_simulation']
        avg_benefit = result['expected_net_benefit_usd']['mean']
        
        print(f"💧 {action['type']} {action['amount']} {action['unit']}:")
        print(f"   🏆 Best Yield: {best_sim['expected_yield_kg_per_zone']:.3f} kg/zone")
        print(f"   📊 Avg Yield: {avg_yield:.3f} kg/zone")
        print(f"   💰 Best Benefit: ${best_sim['net_benefit_usd']:.3f}")
        print(f"   📊 Avg Benefit: ${avg_benefit:.3f}")
        print()
    
    # Restore original iterations
    engine.mc_iterations = original_iterations
    
    print("✅ Best Simulation Feature Test Complete!")
    print("💡 The system now shows the optimal outcome from all Monte Carlo simulations")

if __name__ == "__main__":
    test_best_simulation()
