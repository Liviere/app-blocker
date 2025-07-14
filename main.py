import psutil
import json
import time
import os
from datetime import datetime

CONFIG_PATH = "config.json"
LOG_PATH = "usage_log.json"

# Load configuration
with open(CONFIG_PATH, "r") as f:
    config = json.load(f)

apps = config["apps"]
interval = config.get("check_interval", 30)

# Initialize or load log
if os.path.exists(LOG_PATH):
    with open(LOG_PATH, "r") as f:
        usage_log = json.load(f)
else:
    usage_log = {}

today = datetime.now().strftime("%Y-%m-%d")

if today not in usage_log:
    usage_log[today] = {app: 0 for app in apps}

def save_log():
    with open(LOG_PATH, "w") as f:
        json.dump(usage_log, f, indent=2)

def kill_app(app_name):
    os.system(f"taskkill /f /im {app_name}")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] CLOSED: {app_name}")

def monitor():
    print("⏳ Monitoring applications...")
    while True:
        now = datetime.now()
        current_day = now.strftime("%Y-%m-%d")

        # Reset counter for new day
        if current_day != today:
            usage_log[current_day] = {app: 0 for app in apps}

        running = {p.name(): p.pid for p in psutil.process_iter(['pid', 'name'])}

        for app, limit in apps.items():
            if app in running:
                usage_log[current_day][app] += interval
                print(f"[{now.strftime('%H:%M:%S')}] {app} - {usage_log[current_day][app]} seconds")
                print("Remaining:", limit - usage_log[current_day][app], "seconds")
                if usage_log[current_day][app] >= limit:
                    kill_app(app)

        save_log()
        time.sleep(interval)

if __name__ == "__main__":
    monitor()
