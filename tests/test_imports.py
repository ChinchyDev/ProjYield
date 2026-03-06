"""
Test that all imports work correctly from the tests folder
"""

import sys
import os
import json
# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_imports():
    """Test that all modules can be imported from tests folder"""
    print("🧪 Testing Imports from Tests Folder")
    print("=" * 40)
    
    try:
        # Test core modules
        print("📦 Testing core module imports...")
        import precision_gui
        print("   ✅ precision_gui imported")
        
        import main_server
        print("   ✅ main_server imported")
        
        import decision_engine
        print("   ✅ decision_engine imported")
        
        import precision_models
        print("   ✅ precision_models imported")
        
        # Test mock data access
        print("\n📊 Testing mock data access...")
        mock_data_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'mock_data')
        
        with open(os.path.join(mock_data_path, 'mock_zones.json'), 'r') as f:
            zones = json.load(f)
        print(f"   ✅ mock_zones.json: {len(zones)} zones")
        
        with open(os.path.join(mock_data_path, 'mock_variety_report.json'), 'r') as f:
            report = json.load(f)
        print(f"   ✅ mock_variety_report.json: {len(report['crop_comparisons'])} crop types")
        
        print("\n✅ All imports and file access working correctly!")
        return True
        
    except Exception as e:
        print(f"\n❌ Import error: {e}")
        return False

if __name__ == "__main__":
    test_imports()
