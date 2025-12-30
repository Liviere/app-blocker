import psutil
import json
import psutil
import json
import time
import os
import sys
from datetime import datetime, UTC

from app.logger_utils import get_logger
from app.single_instance import ensure_single_instance
from app.notification_manager import (
    NotificationManager,
    parse_warning_thresholds,
)
from app.common import get_app_directory
from app.config_manager import create_config_manager
from app.time_utils import (
    is_within_blocked_hours,
    get_minutes_until_blocked_hours,
)

# Use application directory for config files
APP_DIR = get_app_directory()

CONFIG_PATH = APP_DIR / "config.json"
LOG_PATH = APP_DIR / "usage_log.json"
HEARTBEAT_PATH = APP_DIR / "monitor_heartbeat.json"
PENDING_UPDATES_PATH = APP_DIR / "pending_time_limit_updates.json"


def _get_config_manager():
    """
    Get config manager instance using current APP_DIR.
    
    WHY: Created as function (not global) to allow tests to patch APP_DIR
    before config_manager is instantiated. Global initialization would
    capture APP_DIR at import time, making it impossible to test with
    different directories.
    """
    return create_config_manager(APP_DIR)


def _log_boot_proximity(logger, component, threshold):
    """Log warning if component started soon after system boot"""
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
    """Update monitor heartbeat file with current status"""
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


def load_usage_log():
    """Load usage log from file"""
    if LOG_PATH.exists():
        with open(LOG_PATH, "r") as f:
            return json.load(f)
    return {}


def save_log(usage_log):
    """Save usage log to file"""
    with open(LOG_PATH, "w") as f:
        json.dump(usage_log, f, indent=2)


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
    config_manager = _get_config_manager()
    config = config_manager.apply_pending_updates(config_manager.load_config())
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
            config = config_manager.apply_pending_updates(config_manager.load_config())
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
                    now.hour, now.minute, blocked_hours
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
            if is_within_blocked_hours(now.hour, now.minute, blocked_hours):
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
