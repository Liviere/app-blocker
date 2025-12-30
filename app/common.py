"""
Common utilities shared across App Blocker modules.

This module provides shared functionality to eliminate code duplication
across main.py, gui.py, notification_manager.py, and logger_utils.py.

WHY THIS EXISTS:
- get_app_directory() was duplicated in 4 different files
- _is_development_mode() was duplicated in main.py and gui.py
- _normalize_time_limits() was duplicated in main.py and gui.py
- Centralizing these functions makes maintenance easier
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any


def get_app_directory() -> Path:
    """
    Get application directory - works with both development and PyInstaller.
    
    WHY: Sound files, config files, and logs are located relative to app directory.
    This function was previously duplicated in 4 different files.
    
    Returns:
        Path: Application directory path
    """
    if getattr(sys, "frozen", False):
        # Running as compiled executable
        return Path(sys.executable).parent
    else:
        # Running as script (repository layout: app/ holds code, configs are one level up)
        return Path(__file__).resolve().parent.parent


def is_development_mode() -> bool:
    """
    Check if application is running in development mode.
    
    WHY: Development mode bypasses time limit update delays for faster iteration.
    Reads from APP_BLOCKER_ENV environment variable.
    This function was previously duplicated in main.py and gui.py.
    
    Returns:
        bool: True if APP_BLOCKER_ENV is set to 'DEVELOPMENT'
    """
    return os.environ.get("APP_BLOCKER_ENV", "PRODUCTION").upper() == "DEVELOPMENT"


def set_environment_mode(mode: str) -> None:
    """
    Set environment mode via OS environment variable.
    
    WHY: Environment variable persists for the current process and child processes.
    Note: This only affects current session. For permanent change, set system env var.
    
    Args:
        mode: Either 'DEVELOPMENT' or 'PRODUCTION'
    """
    os.environ["APP_BLOCKER_ENV"] = mode.upper()


def normalize_time_limits(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensure time_limits supports dedicated and overall limits (legacy apps supported).
    
    WHY: Maintains backward compatibility with old config format while ensuring
    consistent structure. This function was previously duplicated in main.py and gui.py.
    
    Args:
        config: Configuration dictionary to normalize
        
    Returns:
        Dict: Configuration with normalized time_limits structure
    """
    raw_limits = config.get("time_limits")
    legacy = config.get("apps") if "time_limits" not in config else None

    source = raw_limits if isinstance(raw_limits, dict) else legacy if isinstance(legacy, dict) else {}

    if "dedicated" in source or "overall" in source:
        # Already in new format
        dedicated = source.get("dedicated", {}) or {}
        overall = source.get("overall", 0) or 0
        normalized = {"overall": overall, "dedicated": dedicated}
    else:
        # Backward compatibility: flat mapping of app limits
        normalized = {"overall": 0, "dedicated": source}

    config["time_limits"] = normalized
    
    # Drop legacy key to avoid divergence
    if "apps" in config:
        config.pop("apps", None)
    
    return config