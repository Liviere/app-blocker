"""
Tests for environment mode (PRODUCTION vs DEVELOPMENT).

WHY: Verify that development mode bypasses time limit update delays
     while production mode maintains scheduled updates.
Uses APP_BLOCKER_ENV environment variable.
"""

import json
import os
import pytest
from datetime import datetime, UTC, timedelta
from pathlib import Path
from tests.test_utils import isolated_config, ConfigManager
from config_manager import create_config_manager


class TestEnvironmentMode:
    """Test environment mode functionality"""

    def test_default_environment_is_production(self):
        """Environment should default to PRODUCTION mode"""
        # Clear any existing env var
        old_env = os.environ.pop("APP_BLOCKER_ENV", None)
        try:
            from common import is_development_mode
            assert not is_development_mode()
        finally:
            if old_env:
                os.environ["APP_BLOCKER_ENV"] = old_env

    def test_development_mode_applies_changes_immediately(self):
        """In DEVELOPMENT mode, time limit changes should be applied immediately"""
        old_env = os.environ.get("APP_BLOCKER_ENV")
        try:
            os.environ["APP_BLOCKER_ENV"] = "DEVELOPMENT"
            
            with isolated_config() as manager:
                config = manager.get_config()
                config["time_limits"] = {"overall": 0, "dedicated": {}}
                manager.update_config(config)

                # Simulate adding an app in development mode
                config = manager.get_config()
                config["time_limits"]["dedicated"]["test.exe"] = 3600
                manager.update_config(config)

                # Verify no pending updates were created
                pending_path = manager.pending_updates_path
                pending_data = json.loads(pending_path.read_text())
                assert pending_data == []

                # Verify config was updated directly
                config = manager.get_config()
                assert "test.exe" in config["time_limits"]["dedicated"]
                assert config["time_limits"]["dedicated"]["test.exe"] == 3600
        finally:
            if old_env:
                os.environ["APP_BLOCKER_ENV"] = old_env
            else:
                os.environ.pop("APP_BLOCKER_ENV", None)

    def test_production_mode_schedules_changes(self):
        """In PRODUCTION mode, time limit changes should be scheduled"""
        old_env = os.environ.get("APP_BLOCKER_ENV")
        try:
            os.environ["APP_BLOCKER_ENV"] = "PRODUCTION"
            
            with isolated_config() as manager:
                config = manager.get_config()
                config["time_limit_update_delay_hours"] = 2
                config["time_limits"] = {"overall": 0, "dedicated": {}}
                manager.update_config(config)

                # In production mode, changes would be added to pending updates
                pending_path = manager.pending_updates_path

                # Simulate scheduling an update
                apply_at = datetime.now(UTC) + timedelta(hours=2)
                pending_update = {
                    "type": "set_limit",
                    "app": "test.exe",
                    "limit": 3600,
                    "apply_at": apply_at.isoformat(),
                }

                with open(pending_path, "w") as f:
                    json.dump([pending_update], f, indent=2)

                # Verify pending update exists
                loaded_pending = json.loads(pending_path.read_text())
                assert len(loaded_pending) == 1
                assert loaded_pending[0]["app"] == "test.exe"
        finally:
            if old_env:
                os.environ["APP_BLOCKER_ENV"] = old_env
            else:
                os.environ.pop("APP_BLOCKER_ENV", None)

    def test_environment_mode_toggle(self):
        """Should be able to toggle between PRODUCTION and DEVELOPMENT"""
        old_env = os.environ.get("APP_BLOCKER_ENV")
        try:
            from common import is_development_mode
            
            # Start in production
            os.environ["APP_BLOCKER_ENV"] = "PRODUCTION"
            assert not is_development_mode()

            # Switch to development
            os.environ["APP_BLOCKER_ENV"] = "DEVELOPMENT"
            assert is_development_mode()

            # Switch back to production
            os.environ["APP_BLOCKER_ENV"] = "PRODUCTION"
            assert not is_development_mode()
        finally:
            if old_env:
                os.environ["APP_BLOCKER_ENV"] = old_env
            else:
                os.environ.pop("APP_BLOCKER_ENV", None)

    def test_case_insensitive_environment_check(self):
        """Environment check should be case-insensitive"""
        old_env = os.environ.get("APP_BLOCKER_ENV")
        try:
            from common import is_development_mode

            # Test various cases for development
            for env_value in ["development", "DEVELOPMENT", "Development", "DevelopMent"]:
                os.environ["APP_BLOCKER_ENV"] = env_value
                assert is_development_mode()

            # Test various cases for production
            for env_value in ["production", "PRODUCTION", "Production", "ProDuction"]:
                os.environ["APP_BLOCKER_ENV"] = env_value
                assert not is_development_mode()
        finally:
            if old_env:
                os.environ["APP_BLOCKER_ENV"] = old_env
            else:
                os.environ.pop("APP_BLOCKER_ENV", None)

    def test_missing_environment_defaults_to_production(self):
        """If environment variable is missing, should default to PRODUCTION"""
        old_env = os.environ.pop("APP_BLOCKER_ENV", None)
        try:
            from common import is_development_mode
            assert not is_development_mode()
        finally:
            if old_env:
                os.environ["APP_BLOCKER_ENV"] = old_env

    def test_invalid_environment_treated_as_production(self):
        """Invalid environment values should be treated as PRODUCTION"""
        old_env = os.environ.get("APP_BLOCKER_ENV")
        try:
            from common import is_development_mode
            
            for invalid_value in ["STAGING", "TEST", "DEBUG", ""]:
                os.environ["APP_BLOCKER_ENV"] = invalid_value
                assert not is_development_mode(), f"Invalid value '{invalid_value}' was treated as DEVELOPMENT"
        finally:
            if old_env:
                os.environ["APP_BLOCKER_ENV"] = old_env
            else:
                os.environ.pop("APP_BLOCKER_ENV", None)


class TestEnvironmentModeIntegration:
    """Integration tests for environment mode with monitor behavior"""

    def test_monitor_respects_development_mode(self):
        """Monitor should skip pending updates processing in DEVELOPMENT mode"""
        old_env = os.environ.get("APP_BLOCKER_ENV")
        try:
            os.environ["APP_BLOCKER_ENV"] = "DEVELOPMENT"
            
            with isolated_config() as manager:
                config = manager.get_config()
                config["time_limits"] = {"overall": 0, "dedicated": {"test.exe": 3600}}
                config["enabled"] = True
                manager.update_config(config)

                # Create a stale pending update (should be ignored in dev mode)
                pending_path = manager.pending_updates_path
                stale_update = {
                    "type": "set_limit",
                    "app": "old.exe",
                    "limit": 1800,
                    "apply_at": datetime.now(UTC).isoformat(),  # Already due
                }
                with open(pending_path, "w") as f:
                    json.dump([stale_update], f, indent=2)

                # Import and call apply_pending_updates from config_manager
                config_manager = create_config_manager(Path(manager.test_dir))

                # Apply pending updates (should be skipped in dev mode)
                config = config_manager.apply_pending_updates(config)

                # Verify config hasn't been modified by pending updates
                assert "old.exe" not in config["time_limits"]["dedicated"]
                assert "test.exe" in config["time_limits"]["dedicated"]
        finally:
            if old_env:
                os.environ["APP_BLOCKER_ENV"] = old_env
            else:
                os.environ.pop("APP_BLOCKER_ENV", None)

    def test_production_mode_processes_pending_updates(self):
        """Monitor should process pending updates in PRODUCTION mode"""
        old_env = os.environ.get("APP_BLOCKER_ENV")
        try:
            os.environ["APP_BLOCKER_ENV"] = "PRODUCTION"
            
            with isolated_config() as manager:
                config = manager.get_config()
                config["time_limits"] = {"overall": 0, "dedicated": {"test.exe": 3600}}
                config["enabled"] = True
                manager.update_config(config)

                # Create a due pending update
                pending_path = manager.pending_updates_path
                due_update = {
                    "type": "set_limit",
                    "app": "new.exe",
                    "limit": 1800,
                    "apply_at": datetime.now(UTC).isoformat(),  # Due now
                }
                with open(pending_path, "w") as f:
                    json.dump([due_update], f, indent=2)

                # Import and call apply_pending_updates from config_manager
                config_manager = create_config_manager(Path(manager.test_dir))

                # Apply pending updates
                config = config_manager.apply_pending_updates(config)

                # Verify the update was applied
                assert "new.exe" in config["time_limits"]["dedicated"]
                assert config["time_limits"]["dedicated"]["new.exe"] == 1800

                # Verify pending updates were cleared
                if pending_path.exists():
                    pending = json.loads(pending_path.read_text())
                    assert len(pending) == 0 or all(
                        p["app"] != "new.exe" for p in pending
                    )  # Update should be removed
        finally:
            if old_env:
                os.environ["APP_BLOCKER_ENV"] = old_env
            else:
                os.environ.pop("APP_BLOCKER_ENV", None)
