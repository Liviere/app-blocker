import psutil
import json
import time
import os
import sys
from datetime import datetime, UTC
from pathlib import Path
from logger_utils import get_logger
from single_instance import ensure_single_instance


def get_app_directory():
    """Get application directory - works with both development and PyInstaller"""
    if getattr(sys, "frozen", False):
        # Running as compiled executable
        return Path(sys.executable).parent
    else:
        # Running as script
        return Path(__file__).parent


# Use application directory for config files
APP_DIR = get_app_directory()

CONFIG_PATH = APP_DIR / "config.json"
LOG_PATH = APP_DIR / "usage_log.json"
HEARTBEAT_PATH = APP_DIR / "monitor_heartbeat.json"
PENDING_UPDATES_PATH = APP_DIR / "pending_time_limit_updates.json"


def _normalize_time_limits(config):
    """Ensure time_limits supports dedicated and overall limits (legacy apps supported)"""
    raw_limits = config.get("time_limits")
    legacy = config.get("apps") if "time_limits" not in config else None

    source = raw_limits if isinstance(raw_limits, dict) else legacy if isinstance(legacy, dict) else {}

    if "dedicated" in source or "overall" in source:
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
            return _normalize_time_limits(json.load(f))
    except FileNotFoundError:
        # Try to load default config
        default_config_path = APP_DIR / "config.default.json"
        try:
            with open(default_config_path, "r") as f:
                config = _normalize_time_limits(json.load(f))
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
