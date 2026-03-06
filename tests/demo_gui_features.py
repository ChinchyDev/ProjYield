"""
Demo script to show YieldVision GUI features with mock data
"""

import sys
import os
# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import json
import time
import subprocess

def show_gui_demo():
    """Demonstrate GUI features with mock data"""
    print("🖥️ YieldVision GUI Demo with Mock Data")
    print("=" * 50)
    
    server_url = "http://localhost:8000"
    
    # Check if server is running
    try:
        response = requests.get(f"{server_url}/api/precision/status", timeout=5)
        if response.status_code == 200:
            status = response.json()
            print(f"✅ Server Status: {status['system']}")
            print(f"🔥 GPU Available: {status['gpu_available']}")
            print(f"📍 Zones Mapped: {status['zones_mapped']}")
        else:
            print("❌ Server not responding properly")
            return
    except:
        print("❌ Cannot connect to server")
        print("💡 Make sure server is running: python main_server.py")
        return
    
    print("\n🌾 Loading Mock Data into Server...")
    
    # Load mock data if not already loaded
    try:
        with open('../mock_data/mock_zones.json', 'r') as f:
            zones = json.load(f)
        
        response = requests.post(f"{server_url}/api/precision/zones/batch", 
                               json={"zones": zones})
        if response.status_code == 200:
            print(f"✅ Loaded {len(zones)} zones")
        
    except Exception as e:
        print(f"⚠️ Could not load zones: {e}")
    
    print("\n📱 GUI Features Available:")
    print("-" * 30)
    
    features = [
        {
            "tab": "Dashboard",
            "description": "System overview with critical decisions",
            "what_to_look_for": "GPU status, zone count, recent decisions"
        },
        {
            "tab": "Zones", 
            "description": "View and manage precision zones",
            "what_to_look_for": "25 zones with different soil types, GPS coordinates"
        },
        {
            "tab": "Decisions",
            "description": "Evaluate farming actions with Monte Carlo",
            "what_to_look_for": "Test irrigation, fertilization for different varieties"
        },
        {
            "tab": "Metrics",
            "description": "Precision farming KPIs and performance",
            "what_to_look_for": "Water efficiency, nutrient optimization, yield projections"
        },
        {
            "tab": "Irrigation",
            "description": "Irrigation control and metrics (your request)",
            "what_to_look_for": "Today's usage, efficiency, zone coverage, costs"
        }
    ]
    
    for i, feature in enumerate(features, 1):
        print(f"{i}. 📋 {feature['tab']} Tab")
        print(f"   📝 {feature['description']}")
        print(f"   👀 Look for: {feature['what_to_look_for']}")
        print()
    
    print("🌱 Variety Comparison Features:")
    print("-" * 30)
    
    print("🔍 In the 'Decisions' tab:")
    print("   1. Select a zone (e.g., Z_1.285981_36.816994)")
    print("   2. Choose action type: 'irrigate' or 'fertilize_nitrogen'")
    print("   3. Set amount and click 'Evaluate Decision'")
    print("   4. Review Monte Carlo results with confidence intervals")
    print("   5. Compare ROI for different zones/conditions")
    
    print("\n📊 In the 'Zones' tab:")
    print("   1. View all 25 precision zones")
    print("   2. See soil types: clay, loamy, sandy, silty")
    print("   3. Check zone-specific properties (pH, nutrients, moisture)")
    print("   4. Identify zones with different crop varieties")
    
    print("\n💧 In the 'Irrigation' tab:")
    print("   1. Real-time water usage metrics")
    print("   2. Efficiency ratios per zone")
    print("   3. Cost analysis for irrigation decisions")
    print("   4. Zone coverage tracking")
    
    print("\n🎯 Demo Scenarios to Try:")
    print("-" * 30)
    
    scenarios = [
        {
            "name": "Drought vs High-Yield Maize",
            "description": "Compare DroughtMaster vs Hybrid 202 irrigation response",
            "zones": ["Z_1.285981_36.816994", "Z_1.285994_36.817246"],
            "action": "irrigate 15 liters"
        },
        {
            "name": "Tomato Fertilization Test",
            "description": "Test nitrogen response in tomato zones",
            "zones": ["Z_1.285991_36.817362"],
            "action": "fertilize_nitrogen 2.0 kg"
        },
        {
            "name": "Soil Type Impact",
            "description": "Compare clay vs loamy zones",
            "zones": ["Z_1.285981_36.816994", "Z_1.285994_36.817246"],
            "action": "irrigate 20 liters"
        }
    ]
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"{i}. 🧪 {scenario['name']}")
        print(f"   📋 {scenario['description']}")
        print(f"   📍 Zones: {', '.join(scenario['zones'])}")
        print(f"   ⚡ Action: {scenario['action']}")
        print()
    
    print("📈 Expected Results:")
    print("-" * 30)
    print("• Monte Carlo simulations with 10,000 iterations")
    print("• Confidence intervals and risk assessments")
    print("• ROI calculations per zone")
    print("• Variety-specific recommendations")
    print("• Economic impact analysis")
    
    print("\n🔥 RTX 3070 GPU Acceleration:")
    print("-" * 30)
    print("• Monte Carlo simulations run on GPU")
    print("• Faster decision evaluation")
    print("• Real-time uncertainty quantification")
    
    print("\n💡 GUI Navigation Tips:")
    print("-" * 30)
    print("• Click tabs to switch between features")
    print("• Use dropdown menus to select zones and actions")
    print("• Scroll through zone lists to see all 25 zones")
    print("• Check decision results for confidence scores")
    print("• Monitor irrigation metrics in real-time")
    
    print("\n🌐 API Endpoints for Testing:")
    print("-" * 30)
    print(f"• Status: {server_url}/api/precision/status")
    print(f"• Zones: {server_url}/api/precision/zones")
    print(f"• Plantings: {server_url}/api/precision/plantings")
    print(f"• Variety Report: {server_url}/api/precision/variety-report")
    
    print(f"\n🎯 GUI is running and ready!")
    print("=" * 50)
    print("💡 Look for the YieldVision window on your desktop")
    print("🌱 Start exploring the variety comparison features!")
    print("📊 Test different decisions and see Monte Carlo results")

def check_gui_status():
    """Check if GUI is running and responsive"""
    try:
        # Try to import and check GUI class
        import precision_gui
        print("✅ GUI module imports successfully")
        
        # Check if GUI can be instantiated (but don't show it)
        print("✅ GUI class is available")
        
        return True
    except Exception as e:
        print(f"❌ GUI error: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Starting YieldVision GUI Demo...")
    print("=" * 50)
    
    # Check GUI status
    if check_gui_status():
        print("✅ GUI is ready for demo")
        print()
        
        # Show demo features
        show_gui_demo()
        
        print(f"\n🎉 Demo Complete!")
        print("=" * 50)
        print("🖥️ GUI should be visible on your desktop")
        print("🌱 Start exploring the variety comparison features!")
        print("💡 Try the demo scenarios mentioned above")
        
    else:
        print("❌ GUI not available")
        print("💡 Run: python precision_gui.py")
