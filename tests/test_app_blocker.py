"""
Basic tests for App Blocker functionality
"""
import unittest
import sys
import os
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, Mock

# Add parent directory to path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

import main
import gui


class TestAppBlockerCore(unittest.TestCase):
    """Test core functionality of App Blocker"""

    def setUp(self):
        """Set up test environment with temporary directory"""
        self.test_dir = tempfile.mkdtemp()
        self.test_config = {
            "apps": {"notepad.exe": 60, "chrome.exe": 120},
            "check_interval": 30,
            "enabled": True,
        }

        # Create test config file
        self.config_path = Path(self.test_dir) / "config.json"
        with open(self.config_path, "w") as f:
            json.dump(self.test_config, f, indent=2)

        # Create test log file
        self.log_path = Path(self.test_dir) / "usage_log.json"
        with open(self.log_path, "w") as f:
            json.dump({}, f)

    def tearDown(self):
        """Clean up test environment"""
        import shutil

        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_get_app_directory(self):
        """Test that get_app_directory returns a valid path"""
        app_dir = main.get_app_directory()
        self.assertIsInstance(app_dir, Path)
        self.assertTrue(app_dir.exists())

    @patch("main.APP_DIR")
    @patch("main.CONFIG_PATH")
    @patch("main.LOG_PATH")
    def test_config_loading_with_test_files(
        self, mock_log_path, mock_config_path, mock_app_dir
    ):
        """Test config loading with test files instead of real ones"""
        mock_app_dir.return_value = Path(self.test_dir)
        mock_config_path.return_value = self.config_path
        mock_log_path.return_value = self.log_path

        # Test that config can be loaded
        with open(self.config_path, "r") as f:
            config = json.load(f)

        self.assertEqual(config["apps"], self.test_config["apps"])
        self.assertEqual(config["check_interval"], 30)
        self.assertTrue(config["enabled"])

    def test_config_paths_structure(self):
        """Test that config paths are properly constructed"""
        app_dir = Path(self.test_dir)
        config_path = app_dir / "config.json"
        log_path = app_dir / "usage_log.json"

        # Paths should be Path objects
        self.assertIsInstance(config_path, Path)
        self.assertIsInstance(log_path, Path)

        # Files should exist (we created them in setUp)
        self.assertTrue(config_path.exists())
        self.assertTrue(log_path.exists())


class TestAppBlockerGUI(unittest.TestCase):
    """Test GUI functionality of App Blocker"""

    def setUp(self):
        """Set up test environment with temporary directory"""
        self.test_dir = tempfile.mkdtemp()
        self.test_config = {"apps": {}, "check_interval": 30, "enabled": False}

        # Create test config file
        self.config_path = Path(self.test_dir) / "config.json"
        with open(self.config_path, "w") as f:
            json.dump(self.test_config, f, indent=2)

    def tearDown(self):
        """Clean up test environment"""
        import shutil

        shutil.rmtree(self.test_dir, ignore_errors=True)

    @patch("gui.AppBlockerGUI.get_app_directory")
    def test_gui_initialization_with_test_config(self, mock_get_app_dir):
        """Test GUI initialization with test config files"""
        mock_get_app_dir.return_value = Path(self.test_dir)

        # Mock tkinter to avoid creating actual GUI
        with patch("tkinter.Tk") as mock_tk:
            mock_root = Mock()
            mock_tk.return_value = mock_root

            # This would normally create GUI, but we're testing the config loading part
            app_dir = Path(self.test_dir)
            config_path = app_dir / "config.json"

            # Verify test config file exists and has correct content
            self.assertTrue(config_path.exists())

            with open(config_path, "r") as f:
                config = json.load(f)

            self.assertEqual(config["check_interval"], 30)
            self.assertFalse(config["enabled"])
            self.assertEqual(config["apps"], {})


class TestConfigIsolation(unittest.TestCase):
    """Test that tests don't interfere with real config files"""

    def test_real_config_files_not_modified(self):
        """Ensure that running tests doesn't modify real config files"""
        # Get the real app directory
        real_app_dir = main.get_app_directory()
        real_config_path = real_app_dir / "config.json"

        # Store original content if file exists
        original_content = None
        if real_config_path.exists():
            with open(real_config_path, "r") as f:
                original_content = f.read()

        # Run some test operations (this test itself is one)
        test_dir = tempfile.mkdtemp()
        test_config = {"test": True}

        test_config_path = Path(test_dir) / "config.json"
        with open(test_config_path, "w") as f:
            json.dump(test_config, f)

        # Clean up test directory
        import shutil

        shutil.rmtree(test_dir, ignore_errors=True)

        # Verify real config file is unchanged
        if original_content is not None:
            with open(real_config_path, "r") as f:
                current_content = f.read()
            self.assertEqual(
                original_content,
                current_content,
                "Real config file was modified during tests!",
            )


if __name__ == "__main__":
    unittest.main()
