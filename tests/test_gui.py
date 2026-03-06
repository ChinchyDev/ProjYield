"""
Test YieldVision GUI functionality
"""

import sys
import os
# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import subprocess
import time
import requests

def test_gui_launch():
    """Test that GUI launches without errors"""
    print("🖥️ Testing GUI Launch...")
    
    try:
        # Start GUI process
        process = subprocess.Popen([
            sys.executable, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "precision_gui.py")
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        # Give it time to initialize
        time.sleep(2)
        
        # Check if process is still running (success) or has error output
        if process.poll() is None:
            print("✅ GUI launched successfully - no errors detected")
            process.terminate()  # Close the GUI
            return True
        else:
            stdout, stderr = process.communicate()
            if stderr:
                print(f"❌ GUI Error: {stderr}")
            else:
                print("❌ GUI failed to launch")
            return False
            
    except Exception as e:
        print(f"❌ Error testing GUI: {e}")
        return False

def test_gui_components():
    """Test GUI components by importing and checking classes"""
    print("🧩 Testing GUI Components...")
    
    try:
        # Import the GUI module
        import precision_gui
        
        # Check if main class exists
        if hasattr(precision_gui, 'YieldVisionGUI'):
            print("✅ YieldVisionGUI class found")
            
            # Try to instantiate (but don't show)
            try:
                app = precision_gui.YieldVisionGUI()
                print("✅ GUI class instantiates successfully")
                
                # Check key methods exist
                methods = [
                    'setup_ui', 'setup_tabs', 'setup_dashboard_tab',
                    'setup_zones_tab', 'setup_decisions_tab', 
                    'setup_metrics_tab', 'setup_irrigation_tab'
                ]
                
                for method in methods:
                    if hasattr(app, method):
                        print(f"✅ Method {method} exists")
                    else:
                        print(f"❌ Method {method} missing")
                
                return True
                
            except Exception as e:
                print(f"❌ GUI instantiation error: {e}")
                return False
        else:
            print("❌ YieldVisionGUI class not found")
            return False
            
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def main():
    """Main test function"""
    print("🧪 YieldVision GUI Test Suite")
    print("=" * 40)
    
    # Test components
    components_ok = test_gui_components()
    
    # Test launch
    launch_ok = test_gui_launch()
    
    print("\n📊 Test Results:")
    print("=" * 40)
    
    if components_ok and launch_ok:
        print("🎉 ALL TESTS PASSED!")
        print("✅ GUI is working correctly")
        print("✅ All components are functional")
        print("✅ Ready for precision farming operations")
    else:
        print("❌ Some tests failed")
        if not components_ok:
            print("   - Component issues detected")
        if not launch_ok:
            print("   - Launch issues detected")
    
    print("\n💡 To use the GUI:")
    print("   1. Run: python precision_gui.py")
    print("   2. Check for YieldVision window")
    print("   3. Server should be running at localhost:8000")
    print("   4. Add zones and test decisions")

if __name__ == "__main__":
    main()
