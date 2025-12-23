import tkinter as tk
from tkinter import ttk, messagebox
import json
import subprocess
import sys
from datetime import datetime, UTC
from pathlib import Path
from autostart import AutostartManager
from system_tray import SystemTrayManager, is_tray_supported
from single_instance import ensure_single_instance
from logger_utils import get_logger


class AppBlockerGUI:
    def __init__(self, root, single_instance_lock=None):
        self.root = root
        self.root.title("App Blocker - Manager")
        self.root.geometry("600x500")

        # Store single instance lock to keep it alive
        self.single_instance_lock = single_instance_lock

        # Use application directory for config files
        self.app_dir = self.get_app_directory()
        self.config_path = self.app_dir / "config.json"
        self.log_path = self.app_dir / "usage_log.json"
        self.heartbeat_path = self.app_dir / "monitor_heartbeat.json"

        # Initialize autostart manager
        self.autostart_manager = AutostartManager()

        # Initialize system tray if supported
        self.tray_manager = None
        self.tray_enabled = False
        if is_tray_supported():
            self.tray_manager = SystemTrayManager(self)
            self.tray_enabled = True

        self.monitoring_process = None
        self.is_monitoring = False

        self.load_config()
        self.logger = get_logger(
            "app_blocker.gui",
            self.app_dir,
            self.config.get("event_log_enabled", False),
        )
        self.create_widgets()
        self.update_status()

        # Setup tray if enabled
        self.setup_tray_if_enabled()

        # Restore monitoring state if it was enabled
        self.restore_monitoring_state()

    def get_app_directory(self):
        """Get application directory - works with both development and PyInstaller"""
        if getattr(sys, "frozen", False):
            # Running as compiled executable
            app_dir = Path(sys.executable).parent
        else:
            # Running as script
            app_dir = Path(__file__).parent

        # Ensure directory exists
        app_dir.mkdir(exist_ok=True)
        return app_dir

    def get_main_executable(self):
        """Get path to main.py or main.exe"""
        if getattr(sys, "frozen", False):
            # If we're compiled, look for app-blocker.exe in same directory
            main_path = self.app_dir / "app-blocker.exe"
            if main_path.exists():
                return str(main_path)
            # Alternative name
            main_path = self.app_dir / "main.exe"
            if main_path.exists():
                return str(main_path)
            # If neither exists, we have a problem
            raise FileNotFoundError(
                "Could not find monitoring executable (app-blocker.exe or main.exe)"
            )
        else:
            # Development mode - use Python script
            main_path = self.app_dir / "main.py"
            return [sys.executable, str(main_path)]

    def load_config(self):
        try:
            with open(self.config_path, "r") as f:
                self.config = json.load(f)
        except FileNotFoundError:
            # Try to load default config
            default_config_path = self.app_dir / "config.default.json"
            try:
                with open(default_config_path, "r") as f:
                    self.config = json.load(f)
                print(f"Loaded default configuration from {default_config_path}")
            except FileNotFoundError:
                # Fallback to hardcoded default
                self.config = {
                    "apps": {},
                    "check_interval": 30,
                    "enabled": False,
                    "autostart": False,
                    "minimize_to_tray": False,
                }
                print("Using hardcoded default configuration")

            # Save the config to create user's config file
            self.save_config()

        # Ensure required fields exist in config
        if "autostart" not in self.config:
            self.config["autostart"] = False
            self.save_config()

        if "minimize_to_tray" not in self.config:
            self.config["minimize_to_tray"] = False
            self.save_config()

        if "watchdog_enabled" not in self.config:
            self.config["watchdog_enabled"] = True
            self.save_config()

        if "watchdog_restart" not in self.config:
            self.config["watchdog_restart"] = True
            self.save_config()

        if "watchdog_check_interval" not in self.config:
            self.config["watchdog_check_interval"] = 5
            self.save_config()

        if "heartbeat_ttl_seconds" not in self.config:
            # Default to roughly 2 cycles of the monitoring interval plus buffer
            self.config["heartbeat_ttl_seconds"] = (
                self.config.get("check_interval", 30) * 2 + 10
            )
            self.save_config()

        if "event_log_enabled" not in self.config:
            self.config["event_log_enabled"] = True
            self.save_config()

    def save_config(self):
        with open(self.config_path, "w") as f:
            json.dump(self.config, f, indent=2)

    def create_widgets(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Status section
        status_frame = ttk.LabelFrame(main_frame, text="Status", padding="10")
        status_frame.grid(
            row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10)
        )

        self.status_label = ttk.Label(status_frame, text="", font=("Arial", 12, "bold"))
        self.status_label.grid(row=0, column=0, padx=(0, 10))

        self.toggle_btn = ttk.Button(
            status_frame, text="Start Monitoring", command=self.toggle_monitoring
        )
        self.toggle_btn.grid(row=0, column=1)

        # Apps section
        apps_frame = ttk.LabelFrame(main_frame, text="Applications", padding="10")
        apps_frame.grid(
            row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10)
        )

        # Apps list
        columns = ("App", "Time Limit (min)", "Used Today (min)")
        self.apps_tree = ttk.Treeview(
            apps_frame, columns=columns, show="headings", height=8
        )

        for col in columns:
            self.apps_tree.heading(col, text=col)
            self.apps_tree.column(col, width=150)

        scrollbar = ttk.Scrollbar(
            apps_frame, orient=tk.VERTICAL, command=self.apps_tree.yview
        )
        self.apps_tree.configure(yscrollcommand=scrollbar.set)

        self.apps_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

        # Buttons frame
        btn_frame = ttk.Frame(apps_frame)
        btn_frame.grid(row=1, column=0, columnspan=2, pady=(10, 0))

        ttk.Button(btn_frame, text="Add App", command=self.add_app).pack(
            side=tk.LEFT, padx=(0, 5)
        )
        ttk.Button(btn_frame, text="Edit App", command=self.edit_app).pack(
            side=tk.LEFT, padx=(0, 5)
        )
        ttk.Button(btn_frame, text="Remove App", command=self.remove_app).pack(
            side=tk.LEFT, padx=(0, 5)
        )

        # Settings section
        settings_frame = ttk.LabelFrame(main_frame, text="Settings", padding="10")
        settings_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E))

        # Check interval setting
        ttk.Label(settings_frame, text="Check Interval (seconds):").grid(
            row=0, column=0, sticky=tk.W
        )
        self.interval_var = tk.StringVar(
            value=str(self.config.get("check_interval", 30))
        )
        interval_entry = ttk.Entry(
            settings_frame, textvariable=self.interval_var, width=10
        )
        interval_entry.grid(row=0, column=1, padx=(10, 0))

        ttk.Button(
            settings_frame, text="Save Settings", command=self.save_settings
        ).grid(row=0, column=2, padx=(10, 0))

        # Autostart setting
        # Sync config with actual registry state
        actual_autostart = self.autostart_manager.is_autostart_enabled()
        if actual_autostart != self.config.get("autostart", False):
            self.config["autostart"] = actual_autostart
            self.save_config()

        self.autostart_var = tk.BooleanVar(value=self.config.get("autostart", False))
        autostart_checkbox = ttk.Checkbutton(
            settings_frame,
            text="Start with Windows (autostart)",
            variable=self.autostart_var,
            command=self.toggle_autostart,
        )
        autostart_checkbox.grid(
            row=1, column=0, columnspan=3, sticky=tk.W, pady=(10, 0)
        )

        # System tray setting (only if supported)
        if self.tray_enabled:
            self.tray_var = tk.BooleanVar(
                value=self.config.get("minimize_to_tray", False)
            )
            tray_checkbox = ttk.Checkbutton(
                settings_frame,
                text="Minimize to system tray",
                variable=self.tray_var,
                command=self.toggle_tray_setting,
            )
            tray_checkbox.grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=(5, 0))

        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        apps_frame.columnconfigure(0, weight=1)
        apps_frame.rowconfigure(0, weight=1)

        self.refresh_apps_list()

    def refresh_apps_list(self):
        # Clear existing items
        for item in self.apps_tree.get_children():
            self.apps_tree.delete(item)

        # Load usage log
        usage_today = self.get_today_usage()

        # Add apps to tree
        for app_name, time_limit in self.config["apps"].items():
            used_time = usage_today.get(app_name, 0)
            self.apps_tree.insert(
                "",
                tk.END,
                values=(
                    app_name,
                    time_limit // 60,  # Convert to minutes
                    used_time // 60,  # Convert to minutes
                ),
            )

    def get_today_usage(self):
        try:
            with open(self.log_path, "r") as f:
                usage_log = json.load(f)
            today = datetime.now().strftime("%Y-%m-%d")
            return usage_log.get(today, {})
        except FileNotFoundError:
            return {}

    def add_app(self):
        dialog = AppDialog(self.root, "Add Application")
        result = dialog.show()
        if result:
            app_name, time_limit = result
            try:
                self.config["apps"][app_name] = time_limit * 60  # Convert to seconds
                self.save_config()
                self.refresh_apps_list()
                print(f"Added application: {app_name} with limit {time_limit} minutes")
            except ValueError as e:
                messagebox.showerror("Error", f"Invalid input: {e}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to add application: {e}")
                print(f"Error adding application: {e}")

    def edit_app(self):
        selection = self.apps_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an application to edit.")
            return

        item = self.apps_tree.item(selection[0])
        app_name = item["values"][0]
        current_limit = self.config["apps"][app_name] // 60  # Convert to minutes

        dialog = AppDialog(self.root, "Edit Application", app_name, current_limit)
        result = dialog.show()
        if result:
            new_app_name, time_limit = result

            # Remove old entry if name changed
            if new_app_name != app_name:
                del self.config["apps"][app_name]

            self.config["apps"][new_app_name] = time_limit * 60  # Convert to seconds
            self.save_config()
            self.refresh_apps_list()

    def remove_app(self):
        selection = self.apps_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an application to remove.")
            return

        item = self.apps_tree.item(selection[0])
        app_name = item["values"][0]

        if messagebox.askyesno("Confirm", f"Remove {app_name} from monitoring?"):
            del self.config["apps"][app_name]
            self.save_config()
            self.refresh_apps_list()

    def save_settings(self):
        try:
            interval = int(self.interval_var.get())
            if interval < 5:
                raise ValueError("Interval must be at least 5 seconds")

            self.config["check_interval"] = interval
            self.save_config()
            messagebox.showinfo("Success", "Settings saved successfully!")
        except ValueError as e:
            messagebox.showerror("Error", f"Invalid interval: {e}")

    def toggle_autostart(self):
        """Handle autostart checkbox toggle"""
        try:
            enabled = self.autostart_var.get()

            # Update registry
            if self.autostart_manager.set_autostart(enabled):
                # Update config
                self.config["autostart"] = enabled
                self.save_config()
            else:
                # Revert checkbox if operation failed
                self.autostart_var.set(not enabled)

        except Exception:
            # Revert checkbox on error
            self.autostart_var.set(not self.autostart_var.get())

    def toggle_tray_setting(self):
        """Handle minimize to tray checkbox toggle"""
        try:
            enabled = self.tray_var.get()
            self.config["minimize_to_tray"] = enabled
            self.save_config()

            # Update autostart entry if autostart is enabled
            # This will update the registry entry to include/exclude --minimized flag
            if self.config.get("autostart", False):
                self.autostart_manager.enable_autostart()

            # Start or stop tray based on setting
            if enabled and self.tray_manager:
                if not self.tray_manager.is_running:
                    self.tray_manager.start_tray()
                    # Setup window close behavior
                    self.root.protocol("WM_DELETE_WINDOW", self.on_window_close)
            elif not enabled and self.tray_manager:
                self.tray_manager.stop_tray()
                # Restore normal close behavior
                self.root.protocol("WM_DELETE_WINDOW", self.on_window_close_quit)

        except Exception:
            # Revert checkbox on error
            self.tray_var.set(not self.tray_var.get())

    def toggle_monitoring(self):
        if self.is_monitoring:
            self.stop_monitoring()
        else:
            self.start_monitoring()

    def start_monitoring(self):
        if not self.config["apps"]:
            messagebox.showwarning(
                "Warning", "No applications configured for monitoring."
            )
            return

        try:
            # Get the correct executable path
            main_cmd = self.get_main_executable()
            print(f"Starting monitoring with command: {main_cmd}")

            # Start monitoring in subprocess
            if isinstance(main_cmd, list):
                self.monitoring_process = subprocess.Popen(
                    main_cmd,
                    cwd=str(self.app_dir),  # Set working directory
                    creationflags=(
                        subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                    ),
                )
            else:
                self.monitoring_process = subprocess.Popen(
                    main_cmd,
                    cwd=str(self.app_dir),
                    creationflags=(
                        subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                    ),
                )

            self.is_monitoring = True
            self.config["enabled"] = True
            self.save_config()
            self.update_status()

            if self.logger:
                self.logger.info("Monitor process started")

            # Update tray
            if self.tray_manager and self.tray_manager.is_running:
                self.tray_manager.update_menu()
                self.tray_manager.update_icon_color()

            # Start refresh timer
            self.refresh_timer()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start monitoring: {e}")

    def stop_monitoring(self):
        """Stop monitoring and update configuration"""
        self._terminate_monitoring_process()

        self.is_monitoring = False
        self.config["enabled"] = False
        self.save_config()
        self.update_status()

        if self.logger:
            self.logger.info("Monitor process stopped")

        # Update tray
        if self.tray_manager and self.tray_manager.is_running:
            self.tray_manager.update_menu()
            self.tray_manager.update_icon_color()

    def _terminate_monitoring_process(self):
        """Terminate monitoring process without changing configuration"""
        if self.monitoring_process:
            self.monitoring_process.terminate()
            self.monitoring_process = None

    def update_status(self):
        if self.is_monitoring:
            self.status_label.config(text="🟢 MONITORING ACTIVE", foreground="green")
            self.toggle_btn.config(text="Stop Monitoring")
        else:
            self.status_label.config(text="🔴 MONITORING STOPPED", foreground="red")
            self.toggle_btn.config(text="Start Monitoring")

    def refresh_timer(self):
        if self.is_monitoring:
            self.refresh_apps_list()
            self._check_monitor_health()
            if self.is_monitoring:
                interval_ms = max(
                    1000, int(self.config.get("watchdog_check_interval", 5) * 1000)
                )
                self.root.after(interval_ms, self.refresh_timer)

    def on_window_close(self):
        """Handle window close event - minimize to tray if enabled"""
        if (
            self.config.get("minimize_to_tray", False)
            and self.tray_manager
            and self.tray_manager.is_running
        ):
            # Minimize to tray instead of closing
            self.tray_manager.hide_window()
        else:
            # Normal quit behavior
            self.on_window_close_quit()

    def on_window_close_quit(self):
        """Handle window close event - quit application"""
        # Only terminate the process, preserve the enabled state for next startup
        self._terminate_monitoring_process()
        if self.tray_manager:
            self.tray_manager.stop_tray()
        self.root.quit()
        self.root.destroy()

    def setup_tray_if_enabled(self):
        """Setup tray on startup if enabled in config"""
        if self.config.get("minimize_to_tray", False) and self.tray_manager:
            if self.tray_manager.start_tray():
                self.root.protocol("WM_DELETE_WINDOW", self.on_window_close)
            else:
                # If tray failed to start, disable the setting
                self.config["minimize_to_tray"] = False
                self.save_config()
                if hasattr(self, "tray_var"):
                    self.tray_var.set(False)

    def restore_monitoring_state(self):
        """Restore monitoring state from config on startup"""
        if self.logger:
            self.logger.info("Restoring monitoring state from config...")
        if self.config.get("enabled", False):
            # Only restore if there are apps to monitor
            if self.config.get("apps", {}):
                if self.logger:
                    self.logger.info("Previous session had monitoring enabled; restoring")
                try:
                    self.start_monitoring()
                    if self.logger:
                        self.logger.info("Monitoring restored successfully")
                except Exception as e:
                    if self.logger:
                        self.logger.error("Failed to restore monitoring: %s", e)
                    # If restore fails, update config to reflect actual state
                    self.config["enabled"] = False
                    self.save_config()
            else:
                if self.logger:
                    self.logger.info(
                        "No apps configured while enabled=True; disabling flag"
                    )
                # If no apps configured, disable monitoring state
                self.config["enabled"] = False
                self.save_config()


        else:
            print("Monitoring was not enabled in previous session, skipping restore")

    def _read_heartbeat(self):
        try:
            with open(self.heartbeat_path, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            return None
        except Exception:
            return None

    def _compute_heartbeat_ttl(self):
        interval = self.config.get("check_interval", 30)
        return self.config.get("heartbeat_ttl_seconds", interval * 2 + 10)

    def _is_heartbeat_fresh(self):
        heartbeat = self._read_heartbeat()
        if not heartbeat:
            return False
        ts_str = heartbeat.get("timestamp")
        if not ts_str:
            return False
        try:
            ts = datetime.fromisoformat(ts_str)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=UTC)
        except Exception:
            return False
        age = (datetime.now(UTC) - ts).total_seconds()
        return age <= self._compute_heartbeat_ttl()

    def _check_monitor_health(self):
        watchdog_enabled = self.config.get("watchdog_enabled", True)

        process_alive = self.monitoring_process and self.monitoring_process.poll() is None
        heartbeat_fresh = self._is_heartbeat_fresh()

        if not watchdog_enabled:
            if self.monitoring_process and not process_alive:
                self.stop_monitoring()
            return

        if process_alive and heartbeat_fresh:
            return

        reason_parts = []
        if not process_alive:
            reason_parts.append("process not running")
        if not heartbeat_fresh:
            reason_parts.append("stale heartbeat")
        reason = ", ".join(reason_parts) or "unknown"

        if self.logger:
            self.logger.warning("Watchdog detected monitor issue: %s", reason)

        if self.config.get("watchdog_restart", True):
            try:
                if self.logger:
                    self.logger.info("Watchdog attempting to restart monitor")
                self._terminate_monitoring_process()
                self.is_monitoring = False
                self.start_monitoring()
                return
            except Exception as e:
                if self.logger:
                    self.logger.error("Watchdog restart failed: %s", e)

        # If restart disabled or failed, stop monitoring cleanly
        self.stop_monitoring()



class AppDialog:
    def __init__(self, parent, title, app_name="", time_limit=60):
        self.result = None

        # Create dialog window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("300x150")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # Center the dialog
        self.dialog.geometry(
            "+%d+%d" % (parent.winfo_rootx() + 50, parent.winfo_rooty() + 50)
        )

        # App name
        ttk.Label(self.dialog, text="Application name:").grid(
            row=0, column=0, sticky=tk.W, padx=10, pady=5
        )
        self.app_name_var = tk.StringVar(value=app_name)
        ttk.Entry(self.dialog, textvariable=self.app_name_var, width=20).grid(
            row=0, column=1, padx=10, pady=5
        )

        # Time limit
        ttk.Label(self.dialog, text="Time limit (minutes):").grid(
            row=1, column=0, sticky=tk.W, padx=10, pady=5
        )
        self.time_limit_var = tk.StringVar(value=str(time_limit))
        ttk.Entry(self.dialog, textvariable=self.time_limit_var, width=20).grid(
            row=1, column=1, padx=10, pady=5
        )

        # Buttons
        btn_frame = ttk.Frame(self.dialog)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=20)

        ttk.Button(btn_frame, text="OK", command=self.ok_clicked).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(btn_frame, text="Cancel", command=self.cancel_clicked).pack(
            side=tk.LEFT, padx=5
        )

        # Focus on app name entry
        self.dialog.focus_set()

    def show(self):
        """Show dialog and return result"""
        self.dialog.wait_window()
        return self.result

    def ok_clicked(self):
        try:
            app_name = self.app_name_var.get().strip()
            time_limit = int(self.time_limit_var.get())

            if not app_name:
                raise ValueError("Application name cannot be empty")
            if time_limit <= 0:
                raise ValueError("Time limit must be positive")

            self.result = (app_name, time_limit)
            self.dialog.destroy()
        except ValueError as e:
            messagebox.showerror("Error", str(e))

    def cancel_clicked(self):
        self.dialog.destroy()


def main():
    """Entry point for the app-blocker-gui command"""
    import argparse

    # Check for single instance - only one GUI instance allowed
    single_instance_lock = ensure_single_instance("AppBlocker_GUI")
    if single_instance_lock is None:
        # Another instance is already running
        try:
            # Try to show a message box if possible
            root = tk.Tk()
            root.withdraw()  # Hide the main window
            messagebox.showwarning(
                "App Blocker Already Running",
                "App Blocker is already running.\n\n"
                "Only one instance of the application can run at a time.\n"
                "Check your system tray or taskbar for the existing instance.",
            )
            root.destroy()
        except Exception:
            # If tkinter fails, just print to console
            print("App Blocker is already running. Only one instance allowed.")
        sys.exit(1)

    # Parse command line arguments
    parser = argparse.ArgumentParser(description="App Blocker GUI")
    parser.add_argument(
        "--minimized", action="store_true", help="Start minimized to system tray"
    )
    args = parser.parse_args()

    root = tk.Tk()
    app = AppBlockerGUI(root, single_instance_lock)

    # Set up appropriate close behavior based on tray settings
    if app.config.get("minimize_to_tray", False) and app.tray_manager:
        root.protocol("WM_DELETE_WINDOW", app.on_window_close)
    else:
        root.protocol("WM_DELETE_WINDOW", app.on_window_close_quit)

    # If started with --minimized flag and tray is enabled, start minimized
    if (
        args.minimized
        and app.config.get("minimize_to_tray", False)
        and app.tray_manager
    ):
        if app.tray_manager.is_running:
            # Hide window immediately after startup
            root.after(100, app.tray_manager.hide_window)
        else:
            print("Warning: --minimized flag used but tray is not available")

    root.mainloop()

    # Release the lock when application exits
    if single_instance_lock:
        single_instance_lock.release()


if __name__ == "__main__":
    main()
