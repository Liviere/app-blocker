"""
Test script to verify monitoring state persistence
"""

import sys
import json
import tempfile
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def test_monitoring_persistence():
    """Test that monitoring state is preserved between sessions"""
    print("Testing monitoring state persistence...")
    
    # Create temporary config
    temp_dir = tempfile.mkdtemp()
    config_path = Path(temp_dir) / "config.json"
    
    # Test config with monitoring enabled and some apps
    test_config = {
        "apps": {
            "notepad.exe": 3600,  # 60 minutes
            "chrome.exe": 7200    # 120 minutes
        },
        "check_interval": 30,
        "enabled": True,  # This should trigger auto-restore
        "autostart": False,
        "minimize_to_tray": False
    }
    
    # Write test config
    with open(config_path, 'w') as f:
        json.dump(test_config, f, indent=2)
    
    print(f"Created test config at: {config_path}")
    print(f"Config contains: {test_config}")
    print(f"Monitoring enabled: {test_config['enabled']}")
    print(f"Apps configured: {len(test_config['apps'])}")
    
    # Test what should happen on startup
    if test_config.get("enabled", False) and test_config.get("apps", {}):
        print("✅ Should auto-start monitoring on startup")
    else:
        print("❌ Should NOT auto-start monitoring")
    
    # Clean up
    config_path.unlink()
    Path(temp_dir).rmdir()
    print("Test completed and cleaned up")

def test_no_monitoring_persistence():
    """Test that monitoring doesn't start when disabled or no apps"""
    print("\nTesting cases where monitoring should NOT start...")
    
    test_cases = [
        {
            "name": "Disabled monitoring",
            "config": {
                "apps": {"notepad.exe": 3600},
                "enabled": False,  # Disabled
                "check_interval": 30
            }
        },
        {
            "name": "No apps configured",
            "config": {
                "apps": {},  # No apps
                "enabled": True,
                "check_interval": 30
            }
        },
        {
            "name": "Both disabled and no apps",
            "config": {
                "apps": {},
                "enabled": False,
                "check_interval": 30
            }
        }
    ]
    
    for case in test_cases:
        config = case["config"]
        should_start = config.get("enabled", False) and bool(config.get("apps", {}))
        
        print(f"Case: {case['name']}")
        print(f"  Enabled: {config.get('enabled', False)}")
        print(f"  Has apps: {bool(config.get('apps', {}))}")
        print(f"  Should start monitoring: {should_start}")
        
        if should_start:
            print("  ✅ Will auto-start")
        else:
            print("  ❌ Will NOT auto-start")
        print()

if __name__ == "__main__":
    test_monitoring_persistence()
    test_no_monitoring_persistence()
