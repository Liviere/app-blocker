"""
Configuration management for App Blocker.

This module centralizes all configuration-related operations
"""

import json
from datetime import datetime, UTC
from pathlib import Path
from typing import Dict, Any, List
from .common import get_app_directory, is_development_mode, normalize_time_limits


class ConfigManager:
    """
    Centralized configuration management for App Blocker.
    
    WHY THIS CLASS EXISTS:
    - Provides consistent interface for all config operations
    - Handles pending updates, defaults, and normalization in one place
    - Makes testing and maintenance easier
    """
    
    def __init__(self, app_dir: Path = None):
        """
        Initialize ConfigManager with application directory.
        
        Args:
            app_dir: Application directory path. If None, uses get_app_directory()
        """
        self.app_dir = app_dir or get_app_directory()
        self.config_path = self.app_dir / "config.json"
        self.default_config_path = self.app_dir / "config.default.json"
        self.pending_updates_path = self.app_dir / "pending_time_limit_updates.json"
    
    def load_config(self) -> Dict[str, Any]:
        """
        Load configuration from file with normalization and defaults.
        
        WHY: Handles default config fallback and automatic normalization.
        
        Returns:
            Dict: Configuration dictionary with normalized structure
        """
        config = None
        
        try:
            with open(self.config_path, "r") as f:
                config = json.load(f)
        except FileNotFoundError:
            # Try to load default config
            try:
                with open(self.default_config_path, "r") as f:
                    config = json.load(f)
                print(f"Loaded default configuration from {self.default_config_path}")
                # Save as user config
                self.save_config(config)
            except FileNotFoundError:
                # Fallback to hardcoded default
                config = {
                    "time_limits": {"overall": 0, "dedicated": {}},
                    "check_interval": 30,
                    "enabled": False,
                    "autostart": False,
                    "minimize_to_tray": False,
                }
                print("Using hardcoded default configuration")
                self.save_config(config)
        
        if config is None:
            return None
        
        # Normalize and ensure defaults
        config = normalize_time_limits(config)
        config = self.ensure_config_defaults(config)
        
        return config
    
    def save_config(self, config: Dict[str, Any]) -> None:
        """
        Save configuration to file.
        
        Args:
            config: Configuration dictionary to save
        """
        try:
            with open(self.config_path, "w") as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"Failed to save configuration: {e}")
    
    def load_pending_updates(self) -> List[Dict[str, Any]]:
        """
        Load pending time limit updates from file.

        Returns:
            List: List of pending update dictionaries
        """
        try:
            with open(self.pending_updates_path, "r") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except FileNotFoundError:
            return []
        except Exception:
            return []
        return []
    
    def save_pending_updates(self, updates: List[Dict[str, Any]]) -> None:
        """
        Save pending time limit updates to file.
        
        Args:
            updates: List of pending update dictionaries
        """
        try:
            with open(self.pending_updates_path, "w") as f:
                json.dump(updates, f, indent=2)
        except Exception:
            pass
    
    def apply_pending_updates(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply due pending time limit updates to config and persist both files.
        
        WHY: Handles development mode bypass and automatic application of scheduled changes.
        
        Args:
            config: Current configuration dictionary
            
        Returns:
            Dict: Updated configuration with applied changes
        """
        # === Skip pending updates in development mode ===
        # In dev mode, changes are applied immediately, so no pending updates exist.
        if is_development_mode():
            return config
        
        updates = self.load_pending_updates()
        if not updates:
            return config

        now = datetime.now(UTC)
        due = []
        future = []
        
        for item in updates:
            try:
                apply_at = datetime.fromisoformat(item.get("apply_at"))
            except Exception:
                # Malformed entries: drop
                continue
            if apply_at <= now:
                due.append(item)
            else:
                future.append(item)

        limits = config.get("time_limits", {}) if isinstance(config, dict) else {}
        dedicated = limits.get("dedicated", {}) if isinstance(limits, dict) else {}

        for item in due:
            itype = item.get("type")
            if itype == "set_limit":
                app = item.get("app")
                limit = item.get("limit")
                if app and limit is not None:
                    dedicated[app] = limit
            elif itype == "set_overall":
                limit = item.get("limit")
                if limit is not None:
                    limits["overall"] = limit
            elif itype == "remove_app":
                app = item.get("app")
                if app and app in dedicated:
                    dedicated.pop(app, None)
            elif itype == "replace_app":
                old_app = item.get("old_app")
                new_app = item.get("new_app")
                limit = item.get("limit")
                if new_app and limit is not None:
                    if old_app:
                        dedicated.pop(old_app, None)
                    dedicated[new_app] = limit

        limits["dedicated"] = dedicated
        config["time_limits"] = limits

        # Save updated pending updates and config
        self.save_pending_updates(future)
        self.save_config(config)

        return config
    
    def ensure_config_defaults(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ensure all required config fields have default values.
        
        WHY: Prevents missing config fields from breaking the application.
        
        Args:
            config: Configuration dictionary to check/update
            
        Returns:
            Dict: Configuration with all required fields populated
        """
        changed = False
        
        # Ensure required fields exist in config
        if "autostart" not in config:
            config["autostart"] = False
            changed = True

        if "minimize_to_tray" not in config:
            config["minimize_to_tray"] = False
            changed = True

        if "watchdog_enabled" not in config:
            config["watchdog_enabled"] = True
            changed = True

        if "watchdog_restart" not in config:
            config["watchdog_restart"] = True
            changed = True

        if "watchdog_check_interval" not in config:
            config["watchdog_check_interval"] = 5
            changed = True

        if "heartbeat_ttl_seconds" not in config:
            # Default to roughly 2 cycles of the monitoring interval plus buffer
            config["heartbeat_ttl_seconds"] = (
                config.get("check_interval", 30) * 2 + 10
            )
            changed = True

        if "event_log_enabled" not in config:
            config["event_log_enabled"] = True
            changed = True

        if "boot_start_window_seconds" not in config:
            config["boot_start_window_seconds"] = 300
            changed = True

        if "time_limit_update_delay_hours" not in config:
            config["time_limit_update_delay_hours"] = 2
            changed = True

        try:
            delay_hours = int(config.get("time_limit_update_delay_hours", 2))
        except Exception:
            delay_hours = 2
        if delay_hours < 2:
            delay_hours = 2
        if config["time_limit_update_delay_hours"] != delay_hours:
            config["time_limit_update_delay_hours"] = delay_hours
            changed = True

        # === Notification settings defaults ===
        # Ensure notification configuration exists with sensible defaults.
        if "notifications_enabled" not in config:
            config["notifications_enabled"] = True
            changed = True
        
        if "notification_warning_minutes" not in config:
            config["notification_warning_minutes"] = "5,3,1"
            changed = True
        
        # Save config if any defaults were added
        if changed:
            self.save_config(config)
        
        return config


# === Factory function for convenience ===

def create_config_manager(app_dir: Path = None) -> ConfigManager:
    """
    Create a ConfigManager instance.
    
    Args:
        app_dir: Application directory. If None, uses get_app_directory()
        
    Returns:
        ConfigManager: Configured instance ready to use
    """
    return ConfigManager(app_dir)