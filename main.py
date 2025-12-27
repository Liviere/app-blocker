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
            return json.load(f)
    except FileNotFoundError:
        # Try to load default config
        default_config_path = APP_DIR / "config.default.json"
        try:
            with open(default_config_path, "r") as f:
                config = json.load(f)
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
        os.system(f"taskkill /f /im {app_name}")
    else:
        # For other platforms, you might need different commands
        os.system(f"pkill -f {app_name}")
    if logger:
        logger.warning("Closed application due to limit: %s", app_name)
    else:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] CLOSED: {app_name}")


def monitor():
    """Main monitoring function"""
    config = load_config()
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

    if not config["apps"]:
        logger.info("No applications configured for monitoring; exiting")
        sys.exit(0)

    # Initialize or load log
    usage_log = load_usage_log()
    today = datetime.now().strftime("%Y-%m-%d")

    if today not in usage_log:
        usage_log[today] = {app: 0 for app in config["apps"]}

    logger.info("Monitoring applications: %s", ", ".join(config["apps"].keys()))

    while True:
        try:
            # Reload config on each iteration to pick up changes immediately
            # This allows users to modify time limits, add/remove apps, or change
            # settings without restarting monitoring. The performance impact is
            # negligible (loading a small JSON file every 30+ seconds).
            config = load_config()
            if config is None:
                logger.error("Config file missing; stopping monitoring")
                break

            apps = config["apps"]
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
