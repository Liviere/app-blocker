"""
Test utilities for App Blocker testing
Provides helpers for creating isolated test environments
"""
import tempfile
import json
import shutil
from pathlib import Path
from contextlib import contextmanager
from unittest.mock import patch


class ConfigManager:
    """Manager for isolated test configurations"""

    def __init__(self):
        self.test_dir = None
        self.config_path = None
        self.log_path = None
        self.heartbeat_path = None
        self.pending_updates_path = None

    def setup(self, config_data=None, log_data=None):
        """Set up isolated test environment"""
        self.test_dir = tempfile.mkdtemp()
        self.config_path = Path(self.test_dir) / "config.json"
        self.log_path = Path(self.test_dir) / "usage_log.json"
        self.heartbeat_path = Path(self.test_dir) / "monitor_heartbeat.json"
        self.pending_updates_path = Path(self.test_dir) / "pending_time_limit_updates.json"

        # Default test config
        if config_data is None:
            config_data = {
                "time_limits": {"overall": 0, "dedicated": {}},
                "check_interval": 30,
                "enabled": False,
                "autostart": False,
                "minimize_to_tray": False,
                "boot_start_window_seconds": 300,
            }

        # Default test log
        if log_data is None:
            log_data = {}

        # Write test files
        with open(self.config_path, "w") as f:
            json.dump(config_data, f, indent=2)

        with open(self.log_path, "w") as f:
            json.dump(log_data, f, indent=2)

        # Precreate heartbeat file placeholder
        with open(self.heartbeat_path, "w") as f:
            json.dump({}, f, indent=2)

        with open(self.pending_updates_path, "w") as f:
            json.dump([], f, indent=2)

        return self.test_dir

    def cleanup(self):
        """Clean up test environment"""
        if self.test_dir and Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def get_config(self):
        """Load current test config"""
        with open(self.config_path, "r") as f:
            return json.load(f)

    def update_config(self, updates):
        """Update test config with new values"""
        config = self.get_config()
        config.update(updates)

        with open(self.config_path, "w") as f:
            json.dump(config, f, indent=2)

    def get_log(self):
        """Load current test log"""
        with open(self.log_path, "r") as f:
            return json.load(f)

    def update_log(self, updates):
        """Update test log with new values"""
        log = self.get_log()
        log.update(updates)

        with open(self.log_path, "w") as f:
            json.dump(log, f, indent=2)


@contextmanager
def isolated_config(config_data=None, log_data=None):
    """Context manager for isolated test configuration"""
    manager = ConfigManager()

    try:
        test_dir = manager.setup(config_data, log_data)

        # Patch the config paths to point to test files
        with patch("app.main.CONFIG_PATH", manager.config_path), patch(
            "app.main.LOG_PATH", manager.log_path
        ), patch("app.main.HEARTBEAT_PATH", manager.heartbeat_path), patch(
            "app.main.APP_DIR", Path(manager.test_dir)
        ), patch("app.main.PENDING_UPDATES_PATH", manager.pending_updates_path):
            yield manager

    finally:
        manager.cleanup()


def create_test_config(apps=None, check_interval=30, enabled=False):
    """Create a test configuration dictionary"""
    if apps is None:
        apps = {}

    return {
        "time_limits": {"overall": 0, "dedicated": apps},
        "check_interval": check_interval,
        "enabled": enabled,
        "boot_start_window_seconds": 300,
    }


def create_test_log(entries=None):
    """Create a test log dictionary"""
    if entries is None:
        entries = {}

    return entries


def verify_real_files_unchanged():
    """Verify that real config files haven't been modified by tests"""
    from app import main

    real_config_path = main.get_app_directory() / "config.json"
    real_log_path = main.get_app_directory() / "usage_log.json"

    # This is a basic check - in a real scenario you might want to
    # store checksums before tests and verify them after
    results = {
        "config_exists": real_config_path.exists(),
        "log_exists": real_log_path.exists(),
        "config_readable": False,
        "log_readable": False,
    }

    if results["config_exists"]:
        try:
            with open(real_config_path, "r") as f:
                json.load(f)
            results["config_readable"] = True
        except (json.JSONDecodeError, IOError):
            pass

    if results["log_exists"]:
        try:
            with open(real_log_path, "r") as f:
                json.load(f)
            results["log_readable"] = True
        except (json.JSONDecodeError, IOError):
            pass

    return results
