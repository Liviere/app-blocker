"""
Test script to verify minimized startup functionality
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from autostart import AutostartManager

def test_minimized_startup():
    """Test the minimized startup feature"""
    print("Testing minimized startup functionality...")
    
    # Create autostart manager
    manager = AutostartManager()
    
    # Test without config (should be False)
    print(f"Should start minimized (no config): {manager.should_start_minimized()}")
    
    # Create test config with tray enabled
    config_path = manager.app_dir / "config.json"
    config_backup = None
    
    # Backup existing config if it exists
    if config_path.exists():
        import shutil
        config_backup = config_path.with_suffix('.json.backup')
        shutil.copy2(config_path, config_backup)
        print("Backed up existing config")
    
    try:
        # Create test config
        import json
        test_config = {
            "time_limits": {"overall": 0, "dedicated": {}},
            "check_interval": 30,
            "enabled": False,
            "autostart": False,
            "minimize_to_tray": True,
        }
        
        with open(config_path, 'w') as f:
            json.dump(test_config, f, indent=2)
        
        print(f"Should start minimized (tray enabled): {manager.should_start_minimized()}")
        
        # Test executable path generation
        print("Testing executable path generation:")
        print(f"Normal: {manager.get_gui_executable_path()}")
        print(f"With --minimized: {manager.get_gui_executable_path('--minimized')}")
        
    finally:
        # Restore original config
        if config_backup and config_backup.exists():
            import shutil
            shutil.copy2(config_backup, config_path)
            config_backup.unlink()
            print("Restored original config")
        elif config_path.exists():
            config_path.unlink()
            print("Removed test config")

if __name__ == "__main__":
    test_minimized_startup()
