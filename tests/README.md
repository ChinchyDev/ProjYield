# YieldVision Test Suite

This directory contains all test files for the YieldVision Precision Farming System.

## 🧪 Test Files

### Core System Tests
- **`test_gpu.py`** - Tests RTX 3070 GPU detection and performance
- **`test_decision_engine.py`** - Tests Monte Carlo decision evaluation engine
- **`test_gui.py`** - Tests GUI application launch and components
- **`test_imports.py`** - Verifies all imports work from tests folder

### Integration Tests
- **`test_mock_system.py`** - Complete system test with mock data and variety comparison
- **`interactive_gui_test.py`** - Interactive demonstration of GUI functionality

### Demo Files
- **`demo_gui_features.py`** - Comprehensive GUI feature demonstration

## 🔧 Import Path Fix

All test files include the following code to fix import issues:

```python
import sys
import os
# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```

This allows tests to import modules from the parent directory:
- `import precision_gui` ✅
- `import decision_engine` ✅  
- `import main_server` ✅
- `from precision_models import *` ✅

Mock data paths use:
```python
mock_data_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'mock_data')
```

## 🚀 Running Tests

### Individual Tests
```bash
# Test GPU functionality
python tests\test_gpu.py

# Test decision engine
python tests\test_decision_engine.py

# Test GUI functionality
python tests\test_gui.py

# Complete system test
python tests\test_mock_system.py

# Interactive GUI demo
python tests\interactive_gui_test.py

# GUI feature demo
python tests\demo_gui_features.py
```

### All Tests
```bash
# Run all tests (from main directory)
python -m pytest tests/

# Or run individually
python tests\test_gpu.py && python tests\test_decision_engine.py && python tests\test_mock_system.py
```

## 📊 Test Coverage

### ✅ What's Tested
- GPU detection and CUDA support
- Monte Carlo simulation accuracy
- Decision engine uncertainty quantification
- GUI component functionality
- API endpoint connectivity
- Mock data integration
- Variety comparison algorithms

### 🎯 Test Scenarios
- RTX 3070 GPU performance benchmarks
- Decision evaluation with 10,000 Monte Carlo iterations
- Crop variety comparison (9 varieties across 3 crops)
- Zone-specific recommendation accuracy
- Economic analysis and ROI calculations
- Risk assessment and confidence intervals

## 🔧 Test Requirements

- Python 3.8+
- PyTorch with CUDA support
- All dependencies from requirements.txt
- Running server (python main_server.py) for integration tests

## 📈 Expected Results

### GPU Tests
- Should detect NVIDIA GeForce RTX 3070 Laptop GPU
- 8.6 GB GPU memory available
- CUDA acceleration enabled

### Decision Engine Tests
- Monte Carlo simulations complete successfully
- Confidence intervals calculated correctly
- Risk assessments provided
- ROI calculations accurate

### GUI Tests
- Application launches without errors
- All tabs render correctly
- API connectivity working
- Mock data displays properly

### System Tests
- 25 precision zones loaded
- 525 sensor readings processed
- 9 crop varieties compared
- Decision evaluations working

## 🐛 Troubleshooting

### Common Issues
1. **GPU not detected**: Ensure CUDA-enabled PyTorch is installed
2. **Server connection failed**: Start server with `python main_server.py`
3. **GUI import errors**: Check CustomTkinter installation
4. **Mock data missing**: Run `python mock_data\mock_data_generator.py`

### Debug Mode
Add debug output by setting environment variable:
```bash
set DEBUG=true
python tests\test_mock_system.py
```

## 📝 Test Data

Tests use mock data from the `../mock_data/` folder:
- 25 precision zones with realistic soil properties
- 9 crop varieties across 3 crop types
- 525 time-series sensor readings
- Historical decision evaluations

## 🎯 Next Steps

1. Add unit tests for individual functions
2. Create performance benchmarks
3. Add integration tests with real hardware
4. Implement automated testing pipeline
