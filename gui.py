import tkinter as tk
from tkinter import ttk, messagebox
import json
import subprocess
import sys
import os
from datetime import datetime
import psutil
from pathlib import Path

class AppBlockerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("App Blocker - Manager")
        self.root.geometry("600x500")
        
        # Use application directory for config files
        self.app_dir = self.get_app_directory()
        self.config_path = self.app_dir / "config.json"
        self.log_path = self.app_dir / "usage_log.json"
        
        self.monitoring_process = None
        self.is_monitoring = False
        
        self.load_config()
        self.create_widgets()
        self.update_status()
        
    def get_app_directory(self):
        """Get application directory - works with both development and PyInstaller"""
        if getattr(sys, 'frozen', False):
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
        if getattr(sys, 'frozen', False):
            # If we're compiled, look for main.exe in same directory
            main_path = self.app_dir / "main.exe"
            if main_path.exists():
                return str(main_path)
            # Fallback to current executable with main argument
            return [sys.executable, "main"]
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
                    "enabled": False
                }
                print("Using hardcoded default configuration")
            
            # Save the config to create user's config file
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
        status_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.status_label = ttk.Label(status_frame, text="", font=("Arial", 12, "bold"))
        self.status_label.grid(row=0, column=0, padx=(0, 10))
        
        self.toggle_btn = ttk.Button(status_frame, text="Start Monitoring", command=self.toggle_monitoring)
        self.toggle_btn.grid(row=0, column=1)
        
        # Apps section
        apps_frame = ttk.LabelFrame(main_frame, text="Applications", padding="10")
        apps_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        
        # Apps list
        columns = ("App", "Time Limit (min)", "Used Today (min)")
        self.apps_tree = ttk.Treeview(apps_frame, columns=columns, show="headings", height=8)
        
        for col in columns:
            self.apps_tree.heading(col, text=col)
            self.apps_tree.column(col, width=150)
        
        scrollbar = ttk.Scrollbar(apps_frame, orient=tk.VERTICAL, command=self.apps_tree.yview)
        self.apps_tree.configure(yscrollcommand=scrollbar.set)
        
        self.apps_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Buttons frame
        btn_frame = ttk.Frame(apps_frame)
        btn_frame.grid(row=1, column=0, columnspan=2, pady=(10, 0))
        
        ttk.Button(btn_frame, text="Add App", command=self.add_app).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_frame, text="Edit App", command=self.edit_app).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_frame, text="Remove App", command=self.remove_app).pack(side=tk.LEFT, padx=(0, 5))
        
        # Settings section
        settings_frame = ttk.LabelFrame(main_frame, text="Settings", padding="10")
        settings_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E))
        
        ttk.Label(settings_frame, text="Check Interval (seconds):").grid(row=0, column=0, sticky=tk.W)
        self.interval_var = tk.StringVar(value=str(self.config.get("check_interval", 30)))
        interval_entry = ttk.Entry(settings_frame, textvariable=self.interval_var, width=10)
        interval_entry.grid(row=0, column=1, padx=(10, 0))
        
        ttk.Button(settings_frame, text="Save Settings", command=self.save_settings).grid(row=0, column=2, padx=(10, 0))
        
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
            self.apps_tree.insert("", tk.END, values=(
                app_name,
                time_limit // 60,  # Convert to minutes
                used_time // 60    # Convert to minutes
            ))
    
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
        if dialog.result:
            app_name, time_limit = dialog.result
            self.config["apps"][app_name] = time_limit * 60  # Convert to seconds
            self.save_config()
            self.refresh_apps_list()
    
    def edit_app(self):
        selection = self.apps_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an application to edit.")
            return
        
        item = self.apps_tree.item(selection[0])
        app_name = item["values"][0]
        current_limit = self.config["apps"][app_name] // 60  # Convert to minutes
        
        dialog = AppDialog(self.root, "Edit Application", app_name, current_limit)
        if dialog.result:
            new_app_name, time_limit = dialog.result
            
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
    
    def toggle_monitoring(self):
        if self.is_monitoring:
            self.stop_monitoring()
        else:
            self.start_monitoring()
    
    def start_monitoring(self):
        if not self.config["apps"]:
            messagebox.showwarning("Warning", "No applications configured for monitoring.")
            return
        
        try:
            # Get the correct executable path
            main_cmd = self.get_main_executable()
            
            # Start monitoring in subprocess
            if isinstance(main_cmd, list):
                self.monitoring_process = subprocess.Popen(
                    main_cmd,
                    cwd=str(self.app_dir),  # Set working directory
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                )
            else:
                self.monitoring_process = subprocess.Popen(
                    main_cmd,
                    cwd=str(self.app_dir),
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                )
            
            self.is_monitoring = True
            self.config["enabled"] = True
            self.save_config()
            self.update_status()
            
            # Start refresh timer
            self.refresh_timer()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start monitoring: {e}")
    
    def stop_monitoring(self):
        if self.monitoring_process:
            self.monitoring_process.terminate()
            self.monitoring_process = None
        
        self.is_monitoring = False
        self.config["enabled"] = False
        self.save_config()
        self.update_status()
    
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
            # Check if monitoring process is still running
            if self.monitoring_process and self.monitoring_process.poll() is not None:
                self.stop_monitoring()
            else:
                self.root.after(5000, self.refresh_timer)  # Refresh every 5 seconds

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
        self.dialog.geometry("+%d+%d" % (parent.winfo_rootx() + 50, parent.winfo_rooty() + 50))
        
        # App name
        ttk.Label(self.dialog, text="Application name:").grid(row=0, column=0, sticky=tk.W, padx=10, pady=5)
        self.app_name_var = tk.StringVar(value=app_name)
        ttk.Entry(self.dialog, textvariable=self.app_name_var, width=20).grid(row=0, column=1, padx=10, pady=5)
        
        # Time limit
        ttk.Label(self.dialog, text="Time limit (minutes):").grid(row=1, column=0, sticky=tk.W, padx=10, pady=5)
        self.time_limit_var = tk.StringVar(value=str(time_limit))
        ttk.Entry(self.dialog, textvariable=self.time_limit_var, width=20).grid(row=1, column=1, padx=10, pady=5)
        
        # Buttons
        btn_frame = ttk.Frame(self.dialog)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=20)
        
        ttk.Button(btn_frame, text="OK", command=self.ok_clicked).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.cancel_clicked).pack(side=tk.LEFT, padx=5)
        
        # Focus on app name entry
        self.dialog.focus_set()
    
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
    root = tk.Tk()
    app = AppBlockerGUI(root)
    root.protocol("WM_DELETE_WINDOW", lambda: (app.stop_monitoring(), root.destroy()))
    root.mainloop()

if __name__ == "__main__":
    main()
