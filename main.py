import psutil
import json
import time
import os
import sys
from datetime import datetime, UTC
from pathlib import Path
from logger_utils import get_logger
from single_instance import ensure_single_instance
from notification_manager import (
    NotificationManager,
    parse_warning_thresholds,
)
from common import get_app_directory, is_development_mode, normalize_time_limits


# === Blocked hours time range checking ===
# Functions to determine if current time falls within any blocked time range.


def parse_time_str(time_str: str) -> tuple[int, int]:
    """
    Parse 'HH:MM' string to (hours, minutes) tuple.
    
    WHY: We need numeric values for time comparison logic.
    """
    parts = time_str.strip().split(":")
    return int(parts[0]), int(parts[1])


def time_to_minutes(hours: int, minutes: int) -> int:
    """
    Convert hours and minutes to total minutes since midnight.
    
    WHY: Simplifies time comparison - single number instead of two.
    """
    return hours * 60 + minutes


def is_time_in_range(current_minutes: int, start_minutes: int, end_minutes: int) -> bool:
    """
    Check if current time (in minutes) falls within a range.
    
    WHY: Handles both normal ranges (09:00-17:00) and overnight ranges (23:00-02:00).
    Overnight ranges are detected when start > end.
    """
    if start_minutes <= end_minutes:
        # Normal range: e.g., 09:00 to 17:00
        return start_minutes <= current_minutes < end_minutes
    else:
        # Overnight range: e.g., 23:00 to 02:00
        # Current time is in range if it's >= start OR < end
        return current_minutes >= start_minutes or current_minutes < end_minutes


def is_within_blocked_hours(now: datetime, blocked_hours: list) -> bool:
    """
    Check if current datetime falls within any blocked time range.
    
    WHY: Main entry point for blocked hours checking in the monitor loop.
    Returns True if apps should be blocked right now.
    """
    if not blocked_hours:
        return False
    
    current_minutes = time_to_minutes(now.hour, now.minute)
    
    for time_range in blocked_hours:
        start_str = time_range.get("start", "")
        end_str = time_range.get("end", "")
        
        if not start_str or not end_str:
            continue
        
        try:
            start_h, start_m = parse_time_str(start_str)
            end_h, end_m = parse_time_str(end_str)
            
            start_minutes = time_to_minutes(start_h, start_m)
            end_minutes = time_to_minutes(end_h, end_m)
            
            if is_time_in_range(current_minutes, start_minutes, end_minutes):
                return True
        except (ValueError, IndexError):
            # Invalid time format - skip this range
            continue
    
    return False


# === Blocked hours approaching calculation ===
# Calculate minutes until the next blocked hours period starts.


def get_minutes_until_blocked_hours(now: datetime, blocked_hours: list) -> tuple[int, str]:
    """
    Calculate minutes until the nearest blocked hours period starts.
    
    WHY: Needed to trigger warning notifications before blocked hours begin.
    Returns (minutes_until_block, start_time_str) or (-1, "") if no upcoming block.
    Returns -1 if currently within blocked hours (already blocking).
    """
    if not blocked_hours:
        return -1, ""
    
    current_minutes = time_to_minutes(now.hour, now.minute)
    min_distance = float('inf')
    nearest_start_str = ""
    
    for time_range in blocked_hours:
        start_str = time_range.get("start", "")
        end_str = time_range.get("end", "")
        
        if not start_str or not end_str:
            continue
        
        try:
            start_h, start_m = parse_time_str(start_str)
            start_minutes = time_to_minutes(start_h, start_m)
            
            # Check if we're currently in this blocked period
            end_h, end_m = parse_time_str(end_str)
            end_minutes = time_to_minutes(end_h, end_m)
            
            if is_time_in_range(current_minutes, start_minutes, end_minutes):
                # Already in blocked hours - no warning needed
                return -1, ""
            
            # Calculate distance to start of this blocked period
            if current_minutes < start_minutes:
                # Same day: start is ahead
                distance = start_minutes - current_minutes
            else:
                # Next day: wrap around midnight (1440 = minutes in day)
                distance = (1440 - current_minutes) + start_minutes
            
            if distance < min_distance:
                min_distance = distance
                nearest_start_str = start_str
                
        except (ValueError, IndexError):
            continue
    
    if min_distance == float('inf'):
        return -1, ""
    
    return int(min_distance), nearest_start_str


# Use application directory for config files
APP_DIR = get_app_directory()

CONFIG_PATH = APP_DIR / "config.json"
LOG_PATH = APP_DIR / "usage_log.json"
HEARTBEAT_PATH = APP_DIR / "monitor_heartbeat.json"
PENDING_UPDATES_PATH = APP_DIR / "pending_time_limit_updates.json"


def _load_pending_updates():
    try:
        with open(PENDING_UPDATES_PATH, "r") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
    except FileNotFoundError:
        return []
    except Exception:
        return []
    return []


def _save_pending_updates(updates):
    try:
        with open(PENDING_UPDATES_PATH, "w") as f:
            json.dump(updates, f, indent=2)
    except Exception:
        pass


def _apply_pending_updates(config):
    """Apply due pending time limit updates to config and persist both files"""
    # === Skip pending updates in development mode ===
    # In dev mode, changes are applied immediately, so no pending updates exist.
    if is_development_mode():
        return config
    
    updates = _load_pending_updates()
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

    _save_pending_updates(future)
    try:
        with open(CONFIG_PATH, "w") as f:
            json.dump(config, f, indent=2)
    except Exception:
        pass

    return config

def _log_boot_proximity(logger, component, threshold):
    if threshold <= 0:
        return
    try:
        uptime = time.time() - psutil.boot_time()
    except Exception:
        return
    if uptime <= threshold:
        logger.warning(
            "%s started %.0fs after system boot (threshold=%ss)",
            component,
            uptime,
            threshold,
        )


def _update_heartbeat(status="running", pid=None):
    try:
        heartbeat = {
            "status": status,
            "pid": pid or os.getpid(),
            "timestamp": datetime.now(UTC).isoformat(),
        }
        with open(HEARTBEAT_PATH, "w") as f:
            json.dump(heartbeat, f, indent=2)
    except Exception:
        pass


def load_config():
    """Load configuration from file"""
    try:
        with open(CONFIG_PATH, "r") as f:
            return normalize_time_limits(json.load(f))
    except FileNotFoundError:
        # Try to load default config
        default_config_path = APP_DIR / "config.default.json"
        try:
            with open(default_config_path, "r") as f:
                config = normalize_time_limits(json.load(f))
            print(f"Loaded default configuration from {default_config_path}")
            # Save as user config
            with open(CONFIG_PATH, "w") as f:
                json.dump(config, f, indent=2)
            return config
        except FileNotFoundError:
            print(
                "Config file not found. Please run GUI first to configure applications."
            )
            return None


def save_log(usage_log):
    """Save usage log to file"""
    with open(LOG_PATH, "w") as f:
        json.dump(usage_log, f, indent=2)


def load_usage_log():
    """Load usage log from file"""
    if LOG_PATH.exists():
        with open(LOG_PATH, "r") as f:
            return json.load(f)
    return {}


def kill_app(app_name, logger=None):
    """Kill application by name"""
    if sys.platform == "win32":
        # Escape app name for PowerShell by wrapping in double quotes
        escaped_name = app_name.replace('"', '""')
        os.system(f'taskkill /f /im "{escaped_name}"')
    else:
        # For other platforms, you might need different commands
        os.system(f"pkill -f {app_name}")
    if logger:
        logger.warning("Closed application due to limit: %s", app_name)
    else:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] CLOSED: {app_name}")


def monitor():
    """Main monitoring function"""
    config = _apply_pending_updates(load_config())
    if config is None:
        sys.exit(1)

    event_log_enabled = config.get("event_log_enabled", False)
    logger = get_logger("app_blocker.monitor", APP_DIR, event_log_enabled)
    _log_boot_proximity(
        logger,
        "Monitor process",
        config.get("boot_start_window_seconds", 0),
    )

    logger.info("Monitor start")
    _update_heartbeat("running")

    # === Initialize notification manager ===
    # Set up notification system for warning users before app closure.
    notification_manager = NotificationManager(APP_DIR)

    # Check if monitoring is enabled
    if not config.get("enabled", False):
        logger.info("Monitoring disabled in config; exiting")
        sys.exit(0)

    limits = config.get("time_limits", {}) if isinstance(config, dict) else {}
    dedicated_apps = limits.get("dedicated", {}) if isinstance(limits, dict) else {}
    overall_limit = limits.get("overall", 0) if isinstance(limits, dict) else 0

    if not dedicated_apps:
        logger.info("No applications configured for monitoring; exiting")
        sys.exit(0)

    # Initialize or load log
    usage_log = load_usage_log()
    today = datetime.now().strftime("%Y-%m-%d")

    if today not in usage_log:
        usage_log[today] = {app: 0 for app in dedicated_apps}

    logger.info("Monitoring applications: %s", ", ".join(dedicated_apps.keys()))

    while True:
        try:
            # Reload config on each iteration to pick up changes immediately
            # This allows users to modify time limits, add/remove apps, or change
            # settings without restarting monitoring. The performance impact is
            # negligible (loading a small JSON file every 30+ seconds).
            config = _apply_pending_updates(load_config())
            if config is None:
                logger.error("Config file missing; stopping monitoring")
                break

            limits = config.get("time_limits", {}) if isinstance(config, dict) else {}
            apps = limits.get("dedicated", {}) if isinstance(limits, dict) else {}
            overall_limit = limits.get("overall", 0) if isinstance(limits, dict) else 0
            interval = config.get("check_interval", 30)

            # === Load notification settings ===
            # Parse notification configuration for warning thresholds.
            notifications_enabled = config.get("notifications_enabled", True)
            warning_thresholds = parse_warning_thresholds(
                config.get("notification_warning_minutes", "5,3,1")
            )

            # Check if monitoring is still enabled
            if not config.get("enabled", False):
                logger.info("Monitoring disabled via configuration; stopping")
                break

            if not apps:
                logger.info("No applications configured; stopping monitoring")
                break

            now = datetime.now()
            current_day = now.strftime("%Y-%m-%d")

            # Initialize day if needed
            if current_day not in usage_log:
                usage_log[current_day] = {app: 0 for app in apps}

            # Add any new apps to today's log
            for app in apps:
                if app not in usage_log[current_day]:
                    usage_log[current_day][app] = 0

            running = {p.name(): p.pid for p in psutil.process_iter(["pid", "name"])}

            # === Blocked hours approaching notification ===
            # Warn user before blocked hours period begins.
            blocked_hours = config.get("blocked_hours", [])
            
            if notifications_enabled and blocked_hours:
                minutes_until_block, block_start_time = get_minutes_until_blocked_hours(
                    now, blocked_hours
                )
                if minutes_until_block > 0:
                    # Check if any monitored app is running - only notify if so
                    any_app_running = any(app in running for app in apps)
                    if any_app_running:
                        notification_manager.notify_blocked_hours_approaching(
                            minutes_until_block,
                            block_start_time,
                            warning_thresholds
                        )

            # === Blocked hours enforcement ===
            # Check if current time falls within any blocked time range.
            # If so, kill all monitored apps regardless of time limits.
            if is_within_blocked_hours(now, blocked_hours):
                apps_killed = False
                for app in apps:
                    if app in running:
                        logger.warning("Blocked hours active - closing: %s", app)
                        kill_app(app, logger)
                        apps_killed = True
                if apps_killed:
                    logger.info("Blocked hours enforcement completed")
                # Skip normal time limit checks during blocked hours
                save_log(usage_log)
                _update_heartbeat("running")
                time.sleep(interval)
                continue

            # === Normal time limit enforcement ===
            for app, limit in apps.items():
                if app in running:
                    usage_log[current_day][app] += interval
                    remaining = limit - usage_log[current_day][app]

                    logger.info(
                        "%s | used=%ss remaining=%ss",
                        app,
                        usage_log[current_day][app],
                        remaining,
                    )

                    # === Dedicated app limit notification ===
                    # Warn user before specific app limit is reached.
                    if notifications_enabled and remaining > 0:
                        notification_manager.notify_dedicated_limit(
                            app,
                            remaining,
                            warning_thresholds
                        )

                    if usage_log[current_day][app] >= limit:
                        kill_app(app, logger)

            # === Overall usage enforcement ===
            if overall_limit and overall_limit > 0:
                total_used = sum(usage_log[current_day].get(app, 0) for app in apps)
                remaining_overall = overall_limit - total_used
                logger.info(
                    "Overall usage | used=%ss remaining=%ss",
                    total_used,
                    remaining_overall,
                )
                
                # === Overall limit notification ===
                # Warn user before overall time limit is reached.
                if notifications_enabled and remaining_overall > 0:
                    # Only notify if at least one monitored app is running
                    any_app_running = any(app in running for app in apps)
                    if any_app_running:
                        notification_manager.notify_overall_limit(
                            remaining_overall,
                            warning_thresholds
                        )
                
                if total_used >= overall_limit:
                    for app in running:
                        if app in apps:
                            kill_app(app, logger)

            save_log(usage_log)
            _update_heartbeat("running")
            time.sleep(interval)

        except KeyboardInterrupt:
            logger.info("Monitoring stopped by user")
            break
        except Exception as e:
            logger.error("Monitoring error: %s", e)
            time.sleep(5)

    logger.info("Monitor stop")
    _update_heartbeat("stopped")


def main():
    """Entry point for the app-blocker command"""
    # Check for single instance - only one monitor instance allowed
    single_instance_lock = ensure_single_instance("AppBlocker_Monitor")
    if single_instance_lock is None:
        # Another instance is already running
        print("App Blocker monitoring is already running. Only one instance allowed.")
        sys.exit(1)

    try:
        monitor()
    finally:
        # Release the lock when monitoring exits
        if single_instance_lock:
            single_instance_lock.release()


if __name__ == "__main__":
    main()
