"""
Example tests using the isolated test utilities
"""
import unittest
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.test_utils import isolated_config, create_test_config, create_test_log, verify_real_files_unchanged


class TestWithIsolatedUtils(unittest.TestCase):
    """Example tests using isolated configuration utilities"""
    
    def test_isolated_config_context_manager(self):
        """Test using the isolated_config context manager"""
        
        # Define test data
        test_apps = {
            "notepad.exe": 45,
            "paint.exe": 30
        }
        
        test_config = create_test_config(
            apps=test_apps,
            check_interval=15,
            enabled=True
        )
        
        test_log = create_test_log({
            "2025-07-14": {
                "notepad.exe": 1200,
                "paint.exe": 800
            }
        })
        
        # Use isolated configuration
        with isolated_config(test_config, test_log) as manager:
            # Test config operations
            config = manager.get_config()
            self.assertEqual(config["apps"]["notepad.exe"], 45)
            self.assertEqual(config["check_interval"], 15)
            self.assertTrue(config["enabled"])
            
            # Test log operations
            log = manager.get_log()
            self.assertEqual(log["2025-07-14"]["notepad.exe"], 1200)
            
            # Test config updates
            manager.update_config({"enabled": False})
            updated_config = manager.get_config()
            self.assertFalse(updated_config["enabled"])
            
            # Test log updates
            manager.update_log({
                "2025-07-15": {
                    "calculator.exe": 600
                }
            })
            updated_log = manager.get_log()
            self.assertIn("2025-07-15", updated_log)
            self.assertEqual(updated_log["2025-07-15"]["calculator.exe"], 600)
    
    def test_empty_isolated_config(self):
        """Test using isolated config with default empty data"""
        
        with isolated_config() as manager:
            config = manager.get_config()
            log = manager.get_log()
            
            # Should have default values
            self.assertEqual(config["apps"], {})
            self.assertEqual(config["check_interval"], 30)
            self.assertFalse(config["enabled"])
            self.assertEqual(log, {})
    
    def test_real_files_verification(self):
        """Test that real files are not affected by isolated tests"""
        
        # Check initial state
        initial_state = verify_real_files_unchanged()
        
        # Perform isolated operations
        with isolated_config() as manager:
            manager.update_config({
                "apps": {"test_isolation.exe": 999},
                "enabled": True
            })
            
            manager.update_log({
                "test_date": {"test_app": 123456}
            })
            
            # Verify our test changes work
            config = manager.get_config()
            self.assertEqual(config["apps"]["test_isolation.exe"], 999)
        
        # Check final state - should be same as initial
        final_state = verify_real_files_unchanged()
        self.assertEqual(initial_state, final_state)
    
    def test_multiple_isolated_environments(self):
        """Test that multiple isolated environments don't interfere"""
        
        # First environment
        with isolated_config(create_test_config(apps={"app1.exe": 10})) as manager1:
            config1 = manager1.get_config()
            
            # Second environment
            with isolated_config(create_test_config(apps={"app2.exe": 20})) as manager2:
                config2 = manager2.get_config()
                
                # Should be different
                self.assertIn("app1.exe", config1["apps"])
                self.assertNotIn("app1.exe", config2["apps"])
                
                self.assertIn("app2.exe", config2["apps"])
                self.assertNotIn("app2.exe", config1["apps"])


if __name__ == '__main__':
    # Run tests and verify real files are unchanged
    unittest.main(verbosity=2)
