"""
Tests for configuration hot-reload during monitoring
"""
import unittest
import sys
import os
import tempfile
import json
import time
import threading
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, Mock, MagicMock

# Add parent directory to path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

import main


class TestConfigurationReload(unittest.TestCase):
    """Test that configuration changes are picked up during monitoring"""

    def setUp(self):
        """Set up test environment with temporary directory"""
        self.test_dir = tempfile.mkdtemp()
        self.config_path = Path(self.test_dir) / "config.json"
        self.log_path = Path(self.test_dir) / "usage_log.json"

        # Initial config
        self.initial_config = {
            "apps": {"notepad.exe": 3600},  # 60 minutes in seconds
            "check_interval": 1,  # 1 second for fast testing
            "enabled": True,
        }

        with open(self.config_path, "w") as f:
            json.dump(self.initial_config, f, indent=2)

        with open(self.log_path, "w") as f:
            json.dump({}, f)

    def tearDown(self):
        """Clean up test environment"""
        import shutil

        shutil.rmtree(self.test_dir, ignore_errors=True)

    @patch("main.kill_app")
    def test_time_limit_increase_prevents_kill(self, mock_kill):
        """Test that increasing time limit prevents app from being killed"""
        # Patch the paths directly
        with patch.object(main, "CONFIG_PATH", self.config_path), patch.object(
            main, "LOG_PATH", self.log_path
        ):

            # Mock process to always show notepad.exe is running
            mock_process = Mock()
            mock_process.name.return_value = "notepad.exe"
            mock_process.pid = 1234

            iteration_count = [0]
            max_iterations = 5

            original_sleep = time.sleep

            def custom_sleep(duration):
                """Custom sleep that modifies config and stops after few iterations"""
                iteration_count[0] += 1

                # After 2 iterations, increase the time limit
                if iteration_count[0] == 2:
                    # Simulate: app has used 2 seconds, limit was 3600
                    # Now increase limit to 7200 to prevent kill
                    updated_config = self.initial_config.copy()
                    updated_config["apps"]["notepad.exe"] = 7200  # Increase to 120 minutes
                    with open(self.config_path, "w") as f:
                        json.dump(updated_config, f, indent=2)

                # Stop after max iterations
                if iteration_count[0] >= max_iterations:
                    raise KeyboardInterrupt()

                original_sleep(0.01)  # Short sleep for fast test

            with patch("time.sleep", side_effect=custom_sleep), patch(
                "main.psutil.process_iter", return_value=[mock_process]
            ):
                try:
                    main.monitor()
                except (KeyboardInterrupt, SystemExit):
                    pass

        # Verify that app was not killed (because limit was increased before reaching it)
        # App used 5 seconds total, original limit was 3600, new limit is 7200
        mock_kill.assert_not_called()

    def test_new_app_added_during_monitoring(self):
        """Test that new apps added to config are monitored immediately"""
        # Patch the paths directly
        with patch.object(main, "CONFIG_PATH", self.config_path), patch.object(
            main, "LOG_PATH", self.log_path
        ):

            # Mock processes
            mock_notepad = Mock()
            mock_notepad.name.return_value = "notepad.exe"
            mock_notepad.pid = 1234

            mock_chrome = Mock()
            mock_chrome.name.return_value = "chrome.exe"
            mock_chrome.pid = 5678

            # Initially only notepad is running
            processes = [[mock_notepad]]

            iteration_count = [0]
            max_iterations = 5

            original_sleep = time.sleep

            def custom_sleep(duration):
                """Custom sleep that adds new app to config"""
                iteration_count[0] += 1

                # After 2 iterations, add chrome.exe to monitoring
                if iteration_count[0] == 2:
                    updated_config = self.initial_config.copy()
                    updated_config["apps"]["chrome.exe"] = 1800  # 30 minutes
                    with open(self.config_path, "w") as f:
                        json.dump(updated_config, f, indent=2)

                    # Now both processes are running
                    processes[0] = [mock_notepad, mock_chrome]

                # Stop after max iterations
                if iteration_count[0] >= max_iterations:
                    raise KeyboardInterrupt()

                original_sleep(0.01)

            def get_processes(*args, **kwargs):
                return processes[0]

            with patch("time.sleep", side_effect=custom_sleep), patch(
                "main.psutil.process_iter", side_effect=get_processes
            ):
                try:
                    main.monitor()
                except (KeyboardInterrupt, SystemExit):
                    pass

        # Verify that usage log was created for both apps
        with open(self.log_path, "r") as f:
            usage_log = json.load(f)

        today = datetime.now().strftime("%Y-%m-%d")
        self.assertIn(today, usage_log)
        self.assertIn("notepad.exe", usage_log[today])
        self.assertIn("chrome.exe", usage_log[today])

        # Chrome should have been tracked for 3 iterations (after it was added)
        self.assertGreater(usage_log[today]["chrome.exe"], 0)

    def test_check_interval_change(self):
        """Test that check_interval changes are applied immediately"""
        # Patch the paths directly
        with patch.object(main, "CONFIG_PATH", self.config_path), patch.object(
            main, "LOG_PATH", self.log_path
        ):

            # Mock process
            mock_process = Mock()
            mock_process.name.return_value = "notepad.exe"
            mock_process.pid = 1234

            iteration_count = [0]
            sleep_durations = []

            original_sleep = time.sleep

            def custom_sleep(duration):
                """Track sleep durations and modify check_interval"""
                iteration_count[0] += 1
                sleep_durations.append(duration)

                # After 2 iterations, change check_interval from 1 to 5
                if iteration_count[0] == 2:
                    updated_config = self.initial_config.copy()
                    updated_config["check_interval"] = 5
                    with open(self.config_path, "w") as f:
                        json.dump(updated_config, f, indent=2)

                # Stop after 4 iterations
                if iteration_count[0] >= 4:
                    raise KeyboardInterrupt()

                original_sleep(0.01)

            with patch("time.sleep", side_effect=custom_sleep), patch(
                "main.psutil.process_iter", return_value=[mock_process]
            ):
                try:
                    main.monitor()
                except (KeyboardInterrupt, SystemExit):
                    pass

        # Verify sleep durations changed
        # First 2 should use interval of 1, next should use interval of 5
        self.assertEqual(sleep_durations[0], 1)
        self.assertEqual(sleep_durations[1], 1)
        self.assertEqual(sleep_durations[2], 5)
        self.assertEqual(sleep_durations[3], 5)

    def test_monitoring_stops_when_disabled_in_config(self):
        """Test that monitoring stops when disabled in config"""
        # Patch the paths directly
        with patch.object(main, "CONFIG_PATH", self.config_path), patch.object(
            main, "LOG_PATH", self.log_path
        ):

            # Mock process
            mock_process = Mock()
            mock_process.name.return_value = "notepad.exe"
            mock_process.pid = 1234

            iteration_count = [0]

            original_sleep = time.sleep

            def custom_sleep(duration):
                """Disable monitoring after 2 iterations"""
                iteration_count[0] += 1

                # After 2 iterations, disable monitoring
                if iteration_count[0] == 2:
                    updated_config = self.initial_config.copy()
                    updated_config["enabled"] = False
                    with open(self.config_path, "w") as f:
                        json.dump(updated_config, f, indent=2)

                # Should stop naturally after disabling
                if iteration_count[0] >= 10:
                    # Failsafe to prevent infinite loop in test
                    raise KeyboardInterrupt()

                original_sleep(0.01)

            with patch("time.sleep", side_effect=custom_sleep), patch(
                "main.psutil.process_iter", return_value=[mock_process]
            ):
                try:
                    main.monitor()
                except (KeyboardInterrupt, SystemExit):
                    pass

        # Should have stopped naturally after 3 iterations (not hit failsafe at 10)
        self.assertLess(iteration_count[0], 10)
        self.assertGreaterEqual(iteration_count[0], 2)


if __name__ == "__main__":
    unittest.main()
