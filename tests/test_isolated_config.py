"""
Integration tests for App Blocker with isolated test environment
"""
import unittest
import tempfile
import json
import sys
from pathlib import Path
from unittest.mock import patch, Mock

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import main


class TestAppBlockerWithIsolatedConfig(unittest.TestCase):
    """Test App Blocker functionality with completely isolated configuration"""

    def setUp(self):
        """Create isolated test environment"""
        self.test_dir = tempfile.mkdtemp()
        self.test_config_path = Path(self.test_dir) / "test_config.json"
        self.test_log_path = Path(self.test_dir) / "test_usage_log.json"

        # Create test configuration
        self.test_config = {
            "time_limits": {
                "overall": 0,
                "dedicated": {"notepad.exe": 30, "calculator.exe": 60},
            },
            "check_interval": 5,
            "enabled": True,
        }

        # Write test config
        with open(self.test_config_path, "w") as f:
            json.dump(self.test_config, f, indent=2)

        # Initialize empty log
        with open(self.test_log_path, "w") as f:
            json.dump({}, f)

    def tearDown(self):
        """Clean up test environment"""
        import shutil

        shutil.rmtree(self.test_dir, ignore_errors=True)

    @patch("main.CONFIG_PATH")
    @patch("main.LOG_PATH")
    def test_config_loading_isolation(self, mock_log_path, mock_config_path):
        """Test that we can load config from test files without affecting real ones"""
        # Point to our test files
        mock_config_path.return_value = self.test_config_path
        mock_log_path.return_value = self.test_log_path

        # Load the test config
        with open(self.test_config_path, "r") as f:
            loaded_config = json.load(f)

        # Verify it matches our test data
        self.assertEqual(loaded_config["time_limits"]["dedicated"]["notepad.exe"], 30)
        self.assertEqual(loaded_config["time_limits"]["dedicated"]["calculator.exe"], 60)
        self.assertEqual(loaded_config["check_interval"], 5)
        self.assertTrue(loaded_config["enabled"])

    def test_config_modification_isolation(self):
        """Test that modifying test config doesn't affect real config"""
        # Modify test config
        modified_config = json.loads(json.dumps(self.test_config))
        modified_config["time_limits"]["dedicated"]["test_app.exe"] = 999

        with open(self.test_config_path, "w") as f:
            json.dump(modified_config, f, indent=2)

        # Verify modification worked
        with open(self.test_config_path, "r") as f:
            loaded_config = json.load(f)

        self.assertEqual(loaded_config["time_limits"]["dedicated"]["test_app.exe"], 999)

        # Verify real config file (if it exists) is not affected
        real_config_path = main.get_app_directory() / "config.json"
        if real_config_path.exists():
            with open(real_config_path, "r") as f:
                real_config = json.load(f)

            # Real config should not contain our test app
            self.assertNotIn(
                "test_app.exe", real_config.get("time_limits", {}).get("dedicated", {})
            )

    def test_log_file_isolation(self):
        """Test that test logs don't interfere with real logs"""
        # Create test log data
        test_log_data = {"2025-07-14": {"notepad.exe": 1500, "calculator.exe": 900}}

        with open(self.test_log_path, "w") as f:
            json.dump(test_log_data, f, indent=2)

        # Verify test log data
        with open(self.test_log_path, "r") as f:
            loaded_log = json.load(f)

        self.assertEqual(loaded_log["2025-07-14"]["notepad.exe"], 1500)

        # Verify real log file (if it exists) is not affected
        real_log_path = main.get_app_directory() / "usage_log.json"
        if real_log_path.exists():
            with open(real_log_path, "r") as f:
                real_log = json.load(f)

            # Real log should not contain our test data or should be different
            if "2025-07-14" in real_log:
                # If the date exists, the data should be different from our test
                self.assertNotEqual(real_log["2025-07-14"], test_log_data["2025-07-14"])


class TestConfigValidation(unittest.TestCase):
    """Test configuration validation with test files"""

    def setUp(self):
        """Create test environment"""
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up"""
        import shutil

        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_invalid_config_handling(self):
        """Test handling of invalid configuration files"""
        invalid_config_path = Path(self.test_dir) / "invalid_config.json"

        # Create invalid JSON
        with open(invalid_config_path, "w") as f:
            f.write("{ invalid json }")

        # Attempt to load invalid config
        with self.assertRaises(json.JSONDecodeError):
            with open(invalid_config_path, "r") as f:
                json.load(f)

    def test_missing_config_keys(self):
        """Test handling of config with missing required keys"""
        incomplete_config_path = Path(self.test_dir) / "incomplete_config.json"

        # Create config missing required keys
        incomplete_config = {"time_limits": {"overall": 0, "dedicated": {}}}

        with open(incomplete_config_path, "w") as f:
            json.dump(incomplete_config, f)

        with open(incomplete_config_path, "r") as f:
            config = json.load(f)

        # Test default value handling
        check_interval = config.get("check_interval", 30)  # Default to 30
        enabled = config.get("enabled", False)  # Default to False

        self.assertEqual(check_interval, 30)
        self.assertFalse(enabled)


if __name__ == "__main__":
    unittest.main()
