import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
import subprocess
import sys
import time
from datetime import datetime, UTC, timedelta
from pathlib import Path

import psutil
from autostart import AutostartManager
from system_tray import SystemTrayManager, is_tray_supported
from single_instance import ensure_single_instance
from logger_utils import get_logger, parse_log_line
from security_manager import (
    SecurityManager,
    check_crypto_available,
    get_min_password_length,
)
from state_manager import StateEvent, create_state_manager
from notification_manager import validate_warning_thresholds
from common import get_app_directory, is_development_mode
from config_manager import create_config_manager
from time_utils import (
    validate_time_format, time_str_to_minutes, validate_blocked_hours
)


# === Password setup dialog ===
# Shown on first run to set up master password.

class MasterPasswordSetupDialog:
    """
    Dialog for initial master password setup.
    
    WHY: Users must set up encryption before using the app.
    Offers two modes: custom password or generated (hidden) password.
    """
    
    def __init__(self, parent):
        self.result = None
        self.generated_password = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("App Blocker - Security Setup")
        self.dialog.geometry("450x350")
        # Note: Don't use transient() when parent is hidden - causes dialog to be invisible
        self.dialog.grab_set()
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_cancel)
        
        # Center dialog on screen (parent may be hidden)
        self.dialog.update_idletasks()
        screen_width = self.dialog.winfo_screenwidth()
        screen_height = self.dialog.winfo_screenheight()
        x = (screen_width - 450) // 2
        y = (screen_height - 350) // 2
        self.dialog.geometry(f"450x350+{x}+{y}")
        
        # Title
        title_label = ttk.Label(
            self.dialog,
            text="Master Password Setup",
            font=("Arial", 14, "bold")
        )
        title_label.pack(pady=(20, 10))
        
        # Info text
        info_text = (
            "Set up a master password for Protected Mode.\n"
            "It's needed to deactivate Protected Mode."
        )
        info_label = ttk.Label(self.dialog, text=info_text, justify=tk.CENTER)
        info_label.pack(pady=(0, 20))
        
        # Password mode selection
        self.mode_var = tk.StringVar(value="custom")
        
        mode_frame = ttk.LabelFrame(self.dialog, text="Choose password type", padding=10)
        mode_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
        
        ttk.Radiobutton(
            mode_frame,
            text="Set my own password",
            variable=self.mode_var,
            value="custom",
            command=self._update_ui
        ).pack(anchor=tk.W)
        
        ttk.Radiobutton(
            mode_frame,
            text="Generate random password (I won't know it)",
            variable=self.mode_var,
            value="generated",
            command=self._update_ui
        ).pack(anchor=tk.W)
        
        # Password entry frame
        self.password_frame = ttk.Frame(self.dialog)
        self.password_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
        
        ttk.Label(self.password_frame, text="Password:").grid(
            row=0, column=0, sticky=tk.W, pady=5
        )
        self.password_var = tk.StringVar()
        self.password_entry = ttk.Entry(
            self.password_frame,
            textvariable=self.password_var,
            show="*",
            width=30
        )
        self.password_entry.grid(row=0, column=1, padx=(10, 0), pady=5)
        
        ttk.Label(self.password_frame, text="Confirm:").grid(
            row=1, column=0, sticky=tk.W, pady=5
        )
        self.confirm_var = tk.StringVar()
        self.confirm_entry = ttk.Entry(
            self.password_frame,
            textvariable=self.confirm_var,
            show="*",
            width=30
        )
        self.confirm_entry.grid(row=1, column=1, padx=(10, 0), pady=5)
        
        min_len = get_min_password_length()
        self.hint_label = ttk.Label(
            self.password_frame,
            text=f"Minimum {min_len} characters",
            foreground="gray"
        )
        self.hint_label.grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(0, 5))
        
        # Generated password warning
        self.generated_frame = ttk.Frame(self.dialog)
        
        warning_text = (
            "⚠️ WARNING: With generated password you will NOT be able\n"
            "to disable Protected Mode manually. The only way out\n"
            "will be waiting for it to expire."
        )
        ttk.Label(
            self.generated_frame,
            text=warning_text,
            foreground="red",
            justify=tk.CENTER
        ).pack()
        
        # Buttons
        btn_frame = ttk.Frame(self.dialog)
        btn_frame.pack(pady=20)
        
        ttk.Button(btn_frame, text="Setup", command=self._on_ok).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(btn_frame, text="Cancel", command=self._on_cancel).pack(
            side=tk.LEFT, padx=5
        )
        
        self._update_ui()
        
        # Ensure dialog is visible even when parent is hidden
        self.dialog.deiconify()
        self.dialog.lift()
        self.dialog.focus_force()
    
    def _update_ui(self):
        """Update UI based on selected mode."""
        if self.mode_var.get() == "custom":
            self.password_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
            self.generated_frame.pack_forget()
        else:
            self.password_frame.pack_forget()
            self.generated_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
    
    def _on_ok(self):
        if self.mode_var.get() == "custom":
            password = self.password_var.get()
            confirm = self.confirm_var.get()
            
            if password != confirm:
                messagebox.showerror("Error", "Passwords do not match")
                return
            
            min_len = get_min_password_length()
            if len(password) < min_len:
                messagebox.showerror(
                    "Error",
                    f"Password must be at least {min_len} characters"
                )
                return
            
            self.result = ("custom", password)
        else:
            # Confirm user understands they won't know the password
            if not messagebox.askyesno(
                "Confirm",
                "Are you sure you want to generate a random password?\n\n"
                "You will NOT be able to:\n"
                "- Manually disable Protected Mode\n"
                "- Recover the password if lost\n\n"
                "The only way to exit Protected Mode will be to wait\n"
                "for it to expire."
            ):
                return
            
            self.result = ("generated", None)
        
        self.dialog.destroy()
    
    def _on_cancel(self):
        self.result = None
        self.dialog.destroy()
    
    def show(self):
        """Show dialog and return result."""
        self.dialog.wait_window()
        return self.result


# === Password unlock dialog ===
# Shown when app starts to unlock encrypted config.

class UnlockDialog:
    """
    Dialog to unlock app with master password.
    
    WHY: User must authenticate before accessing encrypted config.
    """
    
    def __init__(self, parent, security_manager: SecurityManager):
        self.security_manager = security_manager
        self.result = False
        self.attempts = 0
        self.max_attempts = 5
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("App Blocker - Unlock")
        self.dialog.geometry("350x200")
        # Note: Don't use transient() when parent is hidden - causes dialog to be invisible
        self.dialog.grab_set()
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_cancel)
        
        # Center dialog on screen (parent may be hidden)
        self.dialog.update_idletasks()
        screen_width = self.dialog.winfo_screenwidth()
        screen_height = self.dialog.winfo_screenheight()
        x = (screen_width - 350) // 2
        y = (screen_height - 200) // 2
        self.dialog.geometry(f"350x200+{x}+{y}")
        
        # Lock icon and title
        title_label = ttk.Label(
            self.dialog,
            text="🔒 Enter Master Password",
            font=("Arial", 12, "bold")
        )
        title_label.pack(pady=(20, 15))
        
        # Password entry
        entry_frame = ttk.Frame(self.dialog)
        entry_frame.pack(pady=(0, 10))
        
        ttk.Label(entry_frame, text="Password:").grid(row=0, column=0, padx=5)
        self.password_var = tk.StringVar()
        self.password_entry = ttk.Entry(
            entry_frame,
            textvariable=self.password_var,
            show="*",
            width=25
        )
        self.password_entry.grid(row=0, column=1, padx=5)
        self.password_entry.bind("<Return>", lambda e: self._on_ok())
        
        # Attempts counter
        self.attempts_label = ttk.Label(
            self.dialog,
            text="",
            foreground="gray"
        )
        self.attempts_label.pack()
        
        # Buttons
        btn_frame = ttk.Frame(self.dialog)
        btn_frame.pack(pady=20)
        
        ttk.Button(btn_frame, text="Unlock", command=self._on_ok).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(btn_frame, text="Exit", command=self._on_cancel).pack(
            side=tk.LEFT, padx=5
        )
        
        # Ensure dialog is visible even when parent is hidden
        self.dialog.deiconify()
        self.dialog.lift()
        self.dialog.focus_force()
        
        self.password_entry.focus_set()
    
    def _on_ok(self):
        password = self.password_var.get()
        
        if self.security_manager.verify_password(password):
            self.result = True
            self.dialog.destroy()
        else:
            self.attempts += 1
            remaining = self.max_attempts - self.attempts
            
            if remaining <= 0:
                messagebox.showerror(
                    "Access Denied",
                    "Too many failed attempts. Application will exit."
                )
                self.result = False
                self.dialog.destroy()
            else:
                self.attempts_label.config(
                    text=f"Invalid password. {remaining} attempts remaining.",
                    foreground="red"
                )
                self.password_var.set("")
                self.password_entry.focus_set()
    
    def _on_cancel(self):
        self.result = False
        self.dialog.destroy()
    
    def show(self):
        """Show dialog and return result."""
        self.dialog.wait_window()
        return self.result


# === Protected mode activation dialog ===
# Allows user to enable protected mode for specified duration.

class ProtectedModeDialog:
    """
    Dialog to activate or deactivate Protected Mode.
    
    WHY: Provides UI for time-based commitment to monitoring.
    """
    
    def __init__(self, parent, security_manager: SecurityManager, is_active: bool):
        self.security_manager = security_manager
        self.is_active = is_active
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("App Blocker - Protected Mode")
        self.dialog.geometry("400x300")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center dialog
        self.dialog.geometry(
            "+%d+%d" % (parent.winfo_rootx() + 100, parent.winfo_rooty() + 50)
        )
        
        if is_active:
            self._build_deactivate_ui()
        else:
            self._build_activate_ui()
    
    def _build_activate_ui(self):
        """Build UI for activating protected mode."""
        title_label = ttk.Label(
            self.dialog,
            text="🛡️ Activate Protected Mode",
            font=("Arial", 14, "bold")
        )
        title_label.pack(pady=(20, 10))
        
        info_text = (
            "Protected Mode will lock the following settings:\n\n"
            "✓ Monitoring will be always enabled\n"
            "✓ Autostart with Windows will be forced ON\n"
            "✓ Minimize to tray will be forced ON\n"
            "✓ Close button will be disabled\n"
            "✓ Stop Monitoring button will be disabled\n\n"
            "You can only exit by entering master password\n"
            "or waiting for the protection period to expire."
        )
        info_label = ttk.Label(self.dialog, text=info_text, justify=tk.LEFT)
        info_label.pack(pady=(0, 15), padx=20)
        
        # Duration selection
        duration_frame = ttk.Frame(self.dialog)
        duration_frame.pack(pady=(0, 15))
        
        ttk.Label(duration_frame, text="Protection period (days):").pack(side=tk.LEFT)
        self.days_var = tk.StringVar(value="7")
        days_spinbox = ttk.Spinbox(
            duration_frame,
            from_=1,
            to=365,
            textvariable=self.days_var,
            width=10
        )
        days_spinbox.pack(side=tk.LEFT, padx=(10, 0))
        
        # Buttons
        btn_frame = ttk.Frame(self.dialog)
        btn_frame.pack(pady=10)
        
        ttk.Button(
            btn_frame,
            text="Activate Protected Mode",
            command=self._on_activate
        ).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self._on_cancel).pack(
            side=tk.LEFT, padx=5
        )
    
    def _build_deactivate_ui(self):
        """Build UI for deactivating protected mode."""
        title_label = ttk.Label(
            self.dialog,
            text="🛡️ Protected Mode Active",
            font=("Arial", 14, "bold"),
            foreground="green"
        )
        title_label.pack(pady=(20, 10))
        
        expiry = self.security_manager.get_protected_mode_expiry()
        if expiry:
            remaining = expiry - datetime.now(UTC)
            days = remaining.days
            hours = remaining.seconds // 3600
            expiry_text = f"Expires in: {days} days, {hours} hours"
        else:
            expiry_text = "No expiration set"
        
        expiry_label = ttk.Label(
            self.dialog,
            text=expiry_text,
            font=("Arial", 11)
        )
        expiry_label.pack(pady=(0, 20))
        
        if self.security_manager.is_hidden_password_mode():
            # Cannot deactivate with hidden password
            warning_label = ttk.Label(
                self.dialog,
                text="⚠️ You chose a generated password.\n"
                     "Protected Mode cannot be manually disabled.\n"
                     "You must wait for it to expire.",
                foreground="red",
                justify=tk.CENTER
            )
            warning_label.pack(pady=20)
            
            ttk.Button(
                self.dialog,
                text="Close",
                command=self._on_cancel
            ).pack(pady=10)
        else:
            # Password entry for deactivation
            info_label = ttk.Label(
                self.dialog,
                text="Enter master password to deactivate:",
                justify=tk.CENTER
            )
            info_label.pack(pady=(0, 10))
            
            entry_frame = ttk.Frame(self.dialog)
            entry_frame.pack()
            
            self.password_var = tk.StringVar()
            self.password_entry = ttk.Entry(
                entry_frame,
                textvariable=self.password_var,
                show="*",
                width=25
            )
            self.password_entry.pack()
            self.password_entry.bind("<Return>", lambda e: self._on_deactivate())
            
            btn_frame = ttk.Frame(self.dialog)
            btn_frame.pack(pady=20)
            
            ttk.Button(
                btn_frame,
                text="Deactivate",
                command=self._on_deactivate
            ).pack(side=tk.LEFT, padx=5)
            ttk.Button(btn_frame, text="Cancel", command=self._on_cancel).pack(
                side=tk.LEFT, padx=5
            )
    
    def _on_activate(self):
        try:
            days = int(self.days_var.get())
            if days < 1:
                raise ValueError("Days must be positive")
        except ValueError as e:
            messagebox.showerror("Error", f"Invalid duration: {e}")
            return
        
        if not messagebox.askyesno(
            "Confirm",
            f"Activate Protected Mode for {days} days?\n\n"
            "You will not be able to disable monitoring\n"
            "or close the app without the master password."
        ):
            return
        
        self.result = ("activate", days)
        self.dialog.destroy()
    
    def _on_deactivate(self):
        password = self.password_var.get()
        
        if self.security_manager.deactivate_protected_mode(password):
            self.result = ("deactivate", None)
            self.dialog.destroy()
        else:
            messagebox.showerror("Error", "Invalid password")
            self.password_var.set("")
            self.password_entry.focus_set()
    
    def _on_cancel(self):
        self.result = None
        self.dialog.destroy()
    
    def show(self):
        """Show dialog and return result."""
        self.dialog.wait_window()
        return self.result


# === Blocked hours validation and dialog classes ===
# These classes handle UI for configuring blocked time ranges.




class TimeRangeDialog:
    """
    Dialog for adding or editing a single blocked time range.
    
    WHY: Provides UI for entering start/end times with validation.
    """
    
    def __init__(self, parent, title: str, start: str = "", end: str = ""):
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("300x180")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center dialog
        self.dialog.geometry(
            "+%d+%d" % (parent.winfo_rootx() + 50, parent.winfo_rooty() + 50)
        )
        
        # Info label
        info_text = (
            "Enter time range in 24h format (HH:MM).\n"
            "If start > end, range spans midnight."
        )
        ttk.Label(self.dialog, text=info_text, justify=tk.CENTER).grid(
            row=0, column=0, columnspan=2, padx=10, pady=10
        )
        
        # Start time
        ttk.Label(self.dialog, text="Start time:").grid(
            row=1, column=0, sticky=tk.W, padx=10, pady=5
        )
        self.start_var = tk.StringVar(value=start)
        self.start_entry = ttk.Entry(self.dialog, textvariable=self.start_var, width=10)
        self.start_entry.grid(row=1, column=1, padx=10, pady=5, sticky=tk.W)
        
        # End time
        ttk.Label(self.dialog, text="End time:").grid(
            row=2, column=0, sticky=tk.W, padx=10, pady=5
        )
        self.end_var = tk.StringVar(value=end)
        self.end_entry = ttk.Entry(self.dialog, textvariable=self.end_var, width=10)
        self.end_entry.grid(row=2, column=1, padx=10, pady=5, sticky=tk.W)
        
        # Example label
        ttk.Label(
            self.dialog,
            text="Example: 23:00 to 06:00 (overnight)",
            foreground="gray"
        ).grid(row=3, column=0, columnspan=2, padx=10)
        
        # Buttons
        btn_frame = ttk.Frame(self.dialog)
        btn_frame.grid(row=4, column=0, columnspan=2, pady=15)
        
        ttk.Button(btn_frame, text="OK", command=self._on_ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self._on_cancel).pack(side=tk.LEFT, padx=5)
        
        self.start_entry.focus_set()
    
    def _on_ok(self):
        start = self.start_var.get().strip()
        end = self.end_var.get().strip()
        
        if not validate_time_format(start):
            messagebox.showerror("Error", "Invalid start time format. Use HH:MM (24h).")
            return
        
        if not validate_time_format(end):
            messagebox.showerror("Error", "Invalid end time format. Use HH:MM (24h).")
            return
        
        if start == end:
            messagebox.showerror("Error", "Start and end time cannot be the same.")
            return
        
        self.result = {"start": start, "end": end}
        self.dialog.destroy()
    
    def _on_cancel(self):
        self.dialog.destroy()
    
    def show(self):
        """Show dialog and return result."""
        self.dialog.wait_window()
        return self.result


class BlockedHoursDialog:
    """
    Dialog for managing list of blocked time ranges.
    
    WHY: Main interface for viewing, adding, editing, and removing blocked hours.
    """
    
    def __init__(self, parent, blocked_hours: list):
        self.parent = parent
        self.blocked_hours = [r.copy() for r in blocked_hours]  # Work on a copy
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Blocked Hours Configuration")
        self.dialog.geometry("450x350")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center dialog
        self.dialog.geometry(
            "+%d+%d" % (parent.winfo_rootx() + 50, parent.winfo_rooty() + 50)
        )
        
        # Title and info
        ttk.Label(
            self.dialog,
            text="Blocked Hours",
            font=("Arial", 12, "bold")
        ).pack(pady=(15, 5))
        
        ttk.Label(
            self.dialog,
            text="Applications will be closed during these time ranges,\n"
                 "regardless of time limits.",
            justify=tk.CENTER
        ).pack(pady=(0, 10))
        
        # List frame
        list_frame = ttk.Frame(self.dialog)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)
        
        # Treeview for ranges
        columns = ("Start", "End", "Type")
        self.ranges_tree = ttk.Treeview(
            list_frame, columns=columns, show="headings", height=8
        )
        
        self.ranges_tree.heading("Start", text="Start Time")
        self.ranges_tree.heading("End", text="End Time")
        self.ranges_tree.heading("Type", text="Type")
        
        self.ranges_tree.column("Start", width=100)
        self.ranges_tree.column("End", width=100)
        self.ranges_tree.column("Type", width=120)
        
        scrollbar = ttk.Scrollbar(
            list_frame, orient=tk.VERTICAL, command=self.ranges_tree.yview
        )
        self.ranges_tree.configure(yscrollcommand=scrollbar.set)
        
        self.ranges_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Action buttons
        action_frame = ttk.Frame(self.dialog)
        action_frame.pack(pady=10)
        
        ttk.Button(action_frame, text="Add", command=self._add_range).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(action_frame, text="Edit", command=self._edit_range).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(action_frame, text="Remove", command=self._remove_range).pack(
            side=tk.LEFT, padx=5
        )
        
        # OK/Cancel buttons
        btn_frame = ttk.Frame(self.dialog)
        btn_frame.pack(pady=(5, 15))
        
        ttk.Button(btn_frame, text="Save", command=self._on_save).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(btn_frame, text="Cancel", command=self._on_cancel).pack(
            side=tk.LEFT, padx=5
        )
        
        self._refresh_list()
    
    def _get_range_type(self, start: str, end: str) -> str:
        """Determine if range is normal or overnight."""
        start_mins = time_str_to_minutes(start)
        end_mins = time_str_to_minutes(end)
        return "Overnight" if start_mins > end_mins else "Same day"
    
    def _refresh_list(self):
        """Refresh the treeview with current ranges."""
        for item in self.ranges_tree.get_children():
            self.ranges_tree.delete(item)
        
        for i, r in enumerate(self.blocked_hours):
            range_type = self._get_range_type(r["start"], r["end"])
            self.ranges_tree.insert("", tk.END, iid=str(i), values=(
                r["start"], r["end"], range_type
            ))
    
    def _add_range(self):
        dialog = TimeRangeDialog(self.dialog, "Add Blocked Time Range")
        result = dialog.show()
        
        if result:
            # Check for overlaps with existing ranges
            test_list = self.blocked_hours + [result]
            is_valid, error = validate_blocked_hours(test_list)
            
            if not is_valid:
                messagebox.showerror("Error", f"Cannot add range: {error}")
                return
            
            self.blocked_hours.append(result)
            self._refresh_list()
    
    def _edit_range(self):
        selection = self.ranges_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a range to edit.")
            return
        
        index = int(selection[0])
        current = self.blocked_hours[index]
        
        dialog = TimeRangeDialog(
            self.dialog,
            "Edit Blocked Time Range",
            start=current["start"],
            end=current["end"]
        )
        result = dialog.show()
        
        if result:
            # Check for overlaps, excluding current range
            test_list = self.blocked_hours.copy()
            test_list[index] = result
            is_valid, error = validate_blocked_hours(test_list)
            
            if not is_valid:
                messagebox.showerror("Error", f"Cannot update range: {error}")
                return
            
            self.blocked_hours[index] = result
            self._refresh_list()
    
    def _remove_range(self):
        selection = self.ranges_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a range to remove.")
            return
        
        index = int(selection[0])
        
        if messagebox.askyesno(
            "Confirm",
            f"Remove blocked time range {self.blocked_hours[index]['start']} - "
            f"{self.blocked_hours[index]['end']}?"
        ):
            del self.blocked_hours[index]
            self._refresh_list()
    
    def _on_save(self):
        self.result = self.blocked_hours
        self.dialog.destroy()
    
    def _on_cancel(self):
        self.dialog.destroy()
    
    def show(self):
        """Show dialog and return result."""
        self.dialog.wait_window()
        return self.result


class AppBlockerGUI:
    """
    Main GUI application for App Blocker.
    
    Note: is_monitoring property delegates to state_manager for single source of truth.
    """
    
    # === Property delegates to state_manager ===
    # Avoids duplicating state between gui and state_manager.
    
    @property
    def is_monitoring(self) -> bool:
        """Get monitoring state from state manager."""
        if hasattr(self, 'state_manager') and self.state_manager:
            return self.state_manager.is_monitoring
        return False
    
    def __init__(self, root, single_instance_lock=None, security_manager=None):
        self.root = root
        self.root.title("App Blocker - Manager")
        self.root.geometry("600x550")

        # Store single instance lock to keep it alive
        self.single_instance_lock = single_instance_lock

        # Use application directory for config files
        self.app_dir = get_app_directory()
        # Ensure directory exists
        self.app_dir.mkdir(exist_ok=True)
        
        # Initialize config manager
        self.config_manager = create_config_manager(self.app_dir)
        self.config_path = self.app_dir / "config.json"
        self.log_path = self.app_dir / "usage_log.json"
        self.app_log_path = self.app_dir / "app_blocker.log"
        self.heartbeat_path = self.app_dir / "monitor_heartbeat.json"
        self.session_state_path = self.app_dir / "gui_session.json"
        self.pending_updates_path = self.app_dir / "pending_time_limit_updates.json"

        # === Security manager integration ===
        # Security manager handles encryption and protected mode.
        self.security_manager = security_manager

        # Initialize autostart manager
        self.autostart_manager = AutostartManager()

        # Initialize system tray if supported
        self.tray_manager = None
        self.tray_enabled = False
        if is_tray_supported():
            self.tray_manager = SystemTrayManager(self)
            self.tray_enabled = True

        self.monitoring_process = None
        # Note: is_monitoring is now a property delegating to state_manager
        self._watchdog_restart_running = False
        self._watchdog_grace_deadline = None
        self.log_viewer_window = None
        self._shutdown_in_progress = False
        self._shutdown_cleanup_scheduled = False
        self._old_wndproc = None
        self._wndproc_ref = None
        self._console_ctrl_handler = None
        self._current_session_state = None
        
        # === State manager initialization ===
        # Centralized state management with observer pattern.
        self.state_manager = create_state_manager(self.app_dir, security_manager)
        self._register_state_listeners()

        self.load_config()
        self.logger = get_logger(
            "app_blocker.gui",
            self.app_dir,
            self.config.get("event_log_enabled", False),
        )
        self._check_previous_session_state()
        self._mark_session_start()
        self._log_boot_proximity("GUI startup")
        self.create_widgets()
        self.update_status()

        # Apply protected mode restrictions if active
        self._apply_protected_mode_restrictions()

        # Setup tray if enabled
        self.setup_tray_if_enabled()

        # Restore monitoring state if it was enabled
        self.restore_monitoring_state()
        
        # Start periodic state synchronization timer
        self._start_state_sync_timer()
        
        if sys.platform == "win32":
            self._install_console_shutdown_handler()

    def _register_state_listeners(self):
        """
        Register callbacks for state change events.
        
        WHY: Allows automatic UI updates when state changes
        from any source (tray, monitor process, protected mode expiry).
        """
        self.state_manager.add_listener(
            StateEvent.MONITORING_CHANGED, self._on_monitoring_state_changed
        )
        self.state_manager.add_listener(
            StateEvent.PROTECTED_MODE_CHANGED, self._on_protected_mode_changed
        )
    
    def _on_monitoring_state_changed(self, event: StateEvent, state_data: dict):
        """
        Handle monitoring state change event.
        
        WHY: Update tray menu when monitoring state changes from any source.
        """
        # Update tray menu and icon on monitoring state change
        if self.tray_manager and self.tray_manager.is_running:
            # Schedule update on main thread (called from state_manager)
            self.root.after(0, self._update_tray_state)
    
    def _on_protected_mode_changed(self, event: StateEvent, state_data: dict):
        """
        Handle protected mode state change event.
        
        WHY: Update tray menu and UI when protected mode changes.
        Tray buttons need to be disabled/enabled based on protected mode.
        """
        # Schedule updates on main thread
        self.root.after(0, self._update_tray_state)
        self.root.after(0, self._update_protected_mode_status)
        
        is_protected = state_data.get("is_protected_mode", False)
        if is_protected:
            self.root.after(100, self._enforce_protected_mode_ui)
        else:
            self.root.after(0, self._disable_protected_mode_ui)
    
    def _update_tray_state(self):
        """
        Update system tray menu and icon.
        
        WHY: Called when any state changes to ensure tray reflects current state.
        """
        if self.tray_manager and self.tray_manager.is_running:
            self.tray_manager.update_menu()
            self.tray_manager.update_icon_color()
    
    def _start_state_sync_timer(self):
        """
        Start periodic timer to synchronize state.
        
        WHY: Ensures state stays synchronized even if events are missed.
        Checks for protected mode expiry, heartbeat freshness, etc.
        """
        self._do_state_sync()
    
    def _do_state_sync(self):
        """
        Perform periodic state synchronization.
        
        WHY: Acts as safety net to catch any state drift.
        Runs every few seconds to keep UI in sync with reality.
        """
        try:
            # Sync protected mode state (may have expired)
            self.state_manager.sync_protected_mode_state()
            
            # Update tray periodically to catch any missed updates
            if self.tray_manager and self.tray_manager.is_running:
                self.tray_manager.update_menu()
        except Exception as e:
            if self.logger:
                self.logger.warning("State sync error: %s", e)
        
        # Schedule next sync (every 5 seconds)
        self.root.after(5000, self._do_state_sync)

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
        # === Config loading with integrity check ===
        # Config remains in plaintext for monitor compatibility.
        # Security manager verifies integrity to detect manual edits.
        
        self.config = self.config_manager.load_config()
        if self.config is None:
            # Fallback to hardcoded default if config_manager fails
            self.config = {
                "time_limits": {"overall": 0, "dedicated": {}},
                "check_interval": 30,
                "enabled": False,
                "autostart": False,
                "minimize_to_tray": False,
            }
            print("Using fallback hardcoded default configuration")
        
        # Verify config integrity if security manager is set up
        if self.security_manager and self.security_manager.is_password_set():
            if not self.security_manager.verify_config_integrity(self.config):
                # Config was modified manually - log warning
                # In protected mode this is more serious
                print("WARNING: Config file was modified outside of the application")
    
    def _ensure_config_defaults(self):
        """Ensure all required config fields have default values."""
        changed = False
        
        # Ensure required fields exist in config
        if "autostart" not in self.config:
            self.config["autostart"] = False
            changed = True

        if "minimize_to_tray" not in self.config:
            self.config["minimize_to_tray"] = False
            changed = True

        if "watchdog_enabled" not in self.config:
            self.config["watchdog_enabled"] = True
            changed = True

        if "watchdog_restart" not in self.config:
            self.config["watchdog_restart"] = True
            changed = True

        if "watchdog_check_interval" not in self.config:
            self.config["watchdog_check_interval"] = 5
            changed = True

        if "heartbeat_ttl_seconds" not in self.config:
            # Default to roughly 2 cycles of the monitoring interval plus buffer
            self.config["heartbeat_ttl_seconds"] = (
                self.config.get("check_interval", 30) * 2 + 10
            )
            changed = True

        if "event_log_enabled" not in self.config:
            self.config["event_log_enabled"] = True
            changed = True

        if "boot_start_window_seconds" not in self.config:
            self.config["boot_start_window_seconds"] = 300
            changed = True

        if "time_limit_update_delay_hours" not in self.config:
            self.config["time_limit_update_delay_hours"] = 2
            changed = True

        try:
            delay_hours = int(self.config.get("time_limit_update_delay_hours", 2))
        except Exception:
            delay_hours = 2
        if delay_hours < 2:
            delay_hours = 2
        if self.config["time_limit_update_delay_hours"] != delay_hours:
            self.config["time_limit_update_delay_hours"] = delay_hours
            changed = True

        # ===  Notification settings defaults ===
        # Ensure notification configuration exists with sensible defaults.
        if "notifications_enabled" not in self.config:
            self.config["notifications_enabled"] = True
            changed = True
        
        if "notification_warning_minutes" not in self.config:
            self.config["notification_warning_minutes"] = "5,3,1"
            changed = True
        
        if changed:
            self.save_config()

    def _get_overall_minutes(self):
        """Expose overall cap in minutes for settings UI"""
        overall_seconds = self.config.get("time_limits", {}).get("overall", 0)
        try:
            return int(overall_seconds) // 60
        except Exception:
            return 0

    # === CHECKPOINT: Removed duplicate _load_pending_updates method ===
    # Now using config_manager.load_pending_updates() instead

    # === CHECKPOINT: Removed duplicate _save_pending_updates method ===
    # Now using config_manager.save_pending_updates() instead

    def _schedule_time_limit_update(self, update):
        """Queue a time limit update to apply after configured delay"""
        # === Immediate apply in development mode ===
        # In dev mode, apply changes immediately instead of scheduling.
        if is_development_mode():
            # Apply immediately - modify config directly
            limits = self.config.get("time_limits", {})
            dedicated = limits.get("dedicated", {})
            
            update_type = update.get("type")
            if update_type == "set_limit":
                app = update.get("app")
                limit = update.get("limit")
                if app and limit is not None:
                    dedicated[app] = limit
            elif update_type == "set_overall":
                limit = update.get("limit")
                if limit is not None:
                    limits["overall"] = limit
            elif update_type == "remove_app":
                app = update.get("app")
                if app and app in dedicated:
                    dedicated.pop(app, None)
            elif update_type == "replace_app":
                old_app = update.get("old_app")
                new_app = update.get("new_app")
                limit = update.get("limit")
                if new_app and limit is not None:
                    if old_app:
                        dedicated.pop(old_app, None)
                    dedicated[new_app] = limit
            
            limits["dedicated"] = dedicated
            self.config["time_limits"] = limits
            self.save_config()
            
            # Return current time to indicate immediate application
            return datetime.now(UTC)
        
        # Production mode - schedule for later
        try:
            delay_hours = int(self.config.get("time_limit_update_delay_hours", 2))
        except Exception:
            delay_hours = 2
        if delay_hours < 2:
            delay_hours = 2

        apply_at = datetime.now(UTC) + timedelta(hours=delay_hours)
        update["apply_at"] = apply_at.isoformat()

        updates = self.config_manager.load_pending_updates()
        updates.append(update)
        self.config_manager.save_pending_updates(updates)
        return apply_at

    def _create_time_limit_delay_field(self, settings_frame, start_row):
        """Expose time limit update delay input so users can tune deferred application timing."""
        delay_value = self.config.get("time_limit_update_delay_hours", 2)
        try:
            delay_value = int(float(delay_value))
        except Exception:
            delay_value = 2
        self.delay_var = tk.StringVar(value=str(delay_value))
        ttk.Label(
            settings_frame,
            text="Time limit update delay (hours, min 2):",
        ).grid(row=start_row, column=0, sticky=tk.W, pady=(5, 0))
        ttk.Entry(settings_frame, textvariable=self.delay_var, width=10).grid(
            row=start_row, column=1, padx=(10, 0), pady=(5, 0)
        )
        return start_row + 1

    def save_config(self):
        # === Config saving with integrity update ===
        self.config_manager.save_config(self.config)
        
        # Update config hash for integrity verification
        if self.security_manager:
            self.security_manager.update_config_hash(self.config)

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

        self.logs_btn = ttk.Button(
            status_frame, text="View Logs", command=self.open_log_viewer
        )
        self.logs_btn.grid(row=0, column=2, padx=(10, 0))

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
        
        # === Blocked Hours button in GUI ===
        # Button to open blocked hours configuration dialog.
        ttk.Button(
            btn_frame, text="Blocked Hours", command=self.open_blocked_hours_dialog
        ).pack(side=tk.LEFT, padx=(15, 0))

        # Settings section
        settings_frame = ttk.LabelFrame(main_frame, text="Settings", padding="10")
        settings_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E))

        next_row = 0

        ttk.Label(settings_frame, text="Check Interval (seconds):").grid(
            row=next_row, column=0, sticky=tk.W
        )
        self.interval_var = tk.StringVar(
            value=str(self.config.get("check_interval", 30))
        )
        interval_entry = ttk.Entry(
            settings_frame, textvariable=self.interval_var, width=10
        )
        interval_entry.grid(row=next_row, column=1, padx=(10, 0))
        next_row += 1

        ttk.Label(settings_frame, text="Overall Limit (minutes, 0=off):").grid(
            row=next_row, column=0, sticky=tk.W, pady=(5, 0)
        )
        self.overall_limit_var = tk.StringVar(
            value=str(self._get_overall_minutes())
        )
        overall_entry = ttk.Entry(
            settings_frame, textvariable=self.overall_limit_var, width=10
        )
        overall_entry.grid(row=next_row, column=1, padx=(10, 0), pady=(5, 0))
        next_row += 1

        next_row = self._create_time_limit_delay_field(settings_frame, next_row)

        # === Notification settings UI ===
        # UI controls for configuring warning notifications before app closure.
        
        self.notifications_enabled_var = tk.BooleanVar(
            value=self.config.get("notifications_enabled", True)
        )
        ttk.Checkbutton(
            settings_frame,
            text="Enable shutdown warnings",
            variable=self.notifications_enabled_var,
        ).grid(row=next_row, column=0, columnspan=2, sticky=tk.W, pady=(5, 0))
        next_row += 1
        
        ttk.Label(settings_frame, text="Warning times (min, comma-sep):").grid(
            row=next_row, column=0, sticky=tk.W, pady=(5, 0)
        )
        self.notification_warnings_var = tk.StringVar(
            value=self.config.get("notification_warning_minutes", "5,3,1")
        )
        notification_entry = ttk.Entry(
            settings_frame, textvariable=self.notification_warnings_var, width=10
        )
        notification_entry.grid(row=next_row, column=1, padx=(10, 0), pady=(5, 0))
        next_row += 1

        ttk.Button(
            settings_frame, text="Save Settings", command=self.save_settings
        ).grid(row=0, column=2, rowspan=next_row, padx=(10, 0), pady=(0, 0), sticky=tk.N)

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
            row=next_row, column=0, columnspan=3, sticky=tk.W, pady=(10, 0)
        )

        next_row += 1

        # System tray setting (only if supported)
        if self.tray_enabled:
            self.tray_var = tk.BooleanVar(
                value=self.config.get("minimize_to_tray", False)
            )
            self.tray_checkbox = ttk.Checkbutton(
                settings_frame,
                text="Minimize to system tray",
                variable=self.tray_var,
                command=self.toggle_tray_setting,
            )
            self.tray_checkbox.grid(
                row=next_row, column=0, columnspan=3, sticky=tk.W, pady=(5, 0)
            )
            next_row += 1

        # Store reference to autostart checkbox for protected mode
        self.autostart_checkbox = autostart_checkbox

        # === Protected Mode UI section ===
        # Add protected mode button if security manager is available.
        if self.security_manager:
            protected_frame = ttk.LabelFrame(main_frame, text="Protected Mode", padding="10")
            protected_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))
            
            self.protected_status_label = ttk.Label(
                protected_frame,
                text="",
                font=("Arial", 10)
            )
            self.protected_status_label.grid(row=0, column=0, padx=(0, 10))
            
            self.protected_btn = ttk.Button(
                protected_frame,
                text="Configure Protected Mode",
                command=self.open_protected_mode_dialog
            )
            self.protected_btn.grid(row=0, column=1)
            
            self._update_protected_mode_status()

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
        dedicated = self.config.get("time_limits", {}).get("dedicated", {})
        for app_name, time_limit in dedicated.items():
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
            update = {
                "type": "set_limit",
                "app": app_name,
                "limit": time_limit * 60,
            }
            apply_at = self._schedule_time_limit_update(update)
            if is_development_mode():
                messagebox.showinfo(
                    "Application Added",
                    f"Application '{app_name}' added with limit {time_limit}min.\n"
                    f"Change applied immediately (development mode).",
                )
            else:
                messagebox.showinfo(
                    "Application Added",
                    f"Application '{app_name}' will be added with limit {time_limit}min.\n"
                    f"This change will take effect at: {apply_at.strftime('%Y-%m-%d %H:%M:%S UTC')}",
                )
            self.refresh_apps_list()

    def edit_app(self):
        selection = self.apps_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an application to edit.")
            return

        item = self.apps_tree.item(selection[0])
        app_name = item["values"][0]
        current_limit = (
            self.config["time_limits"]["dedicated"][app_name] // 60
        )  # Convert to minutes

        dialog = AppDialog(self.root, "Edit Application", app_name, current_limit)
        result = dialog.show()
        if result:
            new_app_name, time_limit = result
            update = {
                "type": "replace_app" if new_app_name != app_name else "set_limit",
                "old_app": app_name if new_app_name != app_name else None,
                "new_app": new_app_name,
                "app": new_app_name,
                "limit": time_limit * 60,
            }
            apply_at = self._schedule_time_limit_update(update)
            if is_development_mode():
                messagebox.showinfo(
                    "Application Updated",
                    f"Application updated to '{new_app_name}' with limit {time_limit}min.\n"
                    f"Change applied immediately (development mode).",
                )
            else:
                messagebox.showinfo(
                    "Scheduled",
                    f"Change scheduled for {apply_at.strftime('%Y-%m-%d %H:%M UTC')} (min 2h delay)",
                )
            self.refresh_apps_list()

    def remove_app(self):
        selection = self.apps_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an application to remove.")
            return

        item = self.apps_tree.item(selection[0])
        app_name = item["values"][0]

        if messagebox.askyesno("Confirm", f"Remove {app_name} from monitoring?"):
            update = {"type": "remove_app", "app": app_name}
            apply_at = self._schedule_time_limit_update(update)
            if is_development_mode():
                messagebox.showinfo(
                    "Application Removed",
                    f"Application '{app_name}' removed.\n"
                    f"Change applied immediately (development mode).",
                )
            else:
                messagebox.showinfo(
                    "Scheduled",
                    f"Removal scheduled for {apply_at.strftime('%Y-%m-%d %H:%M UTC')} (min 2h delay)",
                )
            self.refresh_apps_list()

    # === Blocked hours dialog handler ===
    # Opens the blocked hours configuration dialog and saves changes.
    
    def open_blocked_hours_dialog(self):
        """Open dialog to configure blocked time ranges."""
        current_blocked = self.config.get("blocked_hours", [])
        
        dialog = BlockedHoursDialog(self.root, current_blocked)
        result = dialog.show()
        
        if result is not None:
            self.config["blocked_hours"] = result
            self.save_config()
            
            count = len(result)
            if count == 0:
                messagebox.showinfo("Blocked Hours", "All blocked time ranges removed.")
            else:
                messagebox.showinfo(
                    "Blocked Hours",
                    f"Saved {count} blocked time range(s).\n"
                    "Changes take effect immediately."
                )

    def save_settings(self):        
        try:
            interval = int(self.interval_var.get())
            if interval < 5:
                raise ValueError("Interval must be at least 5 seconds")

            delay_hours = int(self.delay_var.get())
            if delay_hours < 2:
                raise ValueError("Time limit update delay must be at least 2 hours")

            overall_minutes = int(self.overall_limit_var.get())
            if overall_minutes < 0:
                raise ValueError("Overall limit cannot be negative")

            # === Validate notification settings ===
            # Ensure warning thresholds are valid before saving.
            notification_warnings = self.notification_warnings_var.get()
            is_valid, error_msg = validate_warning_thresholds(notification_warnings)
            if not is_valid:
                raise ValueError(f"Invalid warning times: {error_msg}")

            self.config["check_interval"] = interval
            self.config["time_limit_update_delay_hours"] = delay_hours
            
            # Save notification settings
            self.config["notifications_enabled"] = self.notifications_enabled_var.get()
            self.config["notification_warning_minutes"] = notification_warnings
            
            current_overall_minutes = self._get_overall_minutes()

            if overall_minutes != current_overall_minutes:
                update = {"type": "set_overall", "limit": overall_minutes * 60}
                apply_at = self._schedule_time_limit_update(update)
                if is_development_mode():
                    messagebox.showinfo(
                        "Settings Saved",
                        f"Overall time limit updated to {overall_minutes}min.\n"
                        f"Change applied immediately (development mode).",
                    )
                else:
                    messagebox.showinfo(
                        "Scheduled",
                        f"Overall limit change scheduled for {apply_at.strftime('%Y-%m-%d %H:%M UTC')} (min 2h delay)",
                    )
            else:
                self.save_config()
                messagebox.showinfo("Success", "Settings saved successfully!")
        except ValueError as e:
            messagebox.showerror("Error", f"Invalid setting: {e}")

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
        # === Protected mode check before stopping ===
        if self.is_monitoring:
            if self._is_protected_mode_active():
                messagebox.showwarning(
                    "Protected Mode",
                    "Cannot stop monitoring while Protected Mode is active.\n"
                    "Use the Protected Mode button to deactivate."
                )
                return
            self.stop_monitoring()
        else:
            self.start_monitoring()

    # === Protected Mode methods ===
    # These methods handle protected mode UI and logic.

    def _is_protected_mode_active(self) -> bool:
        """Check if protected mode is currently active."""
        if not self.security_manager:
            return False
        return self.security_manager.is_protected_mode_active()

    def _update_protected_mode_status(self):
        """
        Update protected mode status label and sync with state manager.
        
        WHY: Keeps UI and state manager in sync for protected mode status.
        """
        if not hasattr(self, 'protected_status_label'):
            return
        
        is_active = self._is_protected_mode_active()
        expiry = self.security_manager.get_protected_mode_expiry() if self.security_manager else None
        
        # Sync with state manager
        self.state_manager.set_protected_mode(is_active, expiry)
        
        if is_active:
            if expiry:
                remaining = expiry - datetime.now(UTC)
                days = remaining.days
                hours = remaining.seconds // 3600
                text = f"🛡️ ACTIVE - Expires in {days}d {hours}h"
            else:
                text = "🛡️ ACTIVE - No expiration"
            self.protected_status_label.config(text=text, foreground="green")
            self.protected_btn.config(text="Manage Protected Mode")
        else:
            self.protected_status_label.config(text="🔓 Inactive", foreground="gray")
            self.protected_btn.config(text="Activate Protected Mode")

    def _apply_protected_mode_restrictions(self):
        """Apply UI restrictions when protected mode is active."""
        if not self._is_protected_mode_active():
            return
        
        # Force enable settings
        if not self.config.get("autostart", False):
            self.config["autostart"] = True
            self.autostart_manager.set_autostart(True)
            self.save_config()
        
        if not self.config.get("minimize_to_tray", False) and self.tray_enabled:
            self.config["minimize_to_tray"] = True
            self.save_config()
        
        # Start monitoring if not already
        if not self.is_monitoring and self.config.get("time_limits", {}).get("dedicated"):
            self.config["enabled"] = True
            self.save_config()
        
        # Disable UI elements - will be applied after widgets are created
        self.root.after(100, self._enforce_protected_mode_ui)

    def _enforce_protected_mode_ui(self):
        """Disable UI elements in protected mode."""
        if not self._is_protected_mode_active():
            return
        
        # Disable stop monitoring button
        if hasattr(self, 'toggle_btn'):
            if self.is_monitoring:
                self.toggle_btn.config(state=tk.DISABLED)
        
        # Disable autostart checkbox (forced on)
        if hasattr(self, 'autostart_checkbox'):
            self.autostart_checkbox.config(state=tk.DISABLED)
            self.autostart_var.set(True)
        
        # Disable tray checkbox (forced on)
        if hasattr(self, 'tray_checkbox') and self.tray_enabled:
            self.tray_checkbox.config(state=tk.DISABLED)
            self.tray_var.set(True)
        
        # Override close behavior
        self.root.protocol("WM_DELETE_WINDOW", self._on_close_protected)

    def _on_close_protected(self):
        """Handle close button in protected mode - minimize to tray instead."""
        if self.tray_manager and self.tray_manager.is_running:
            self.tray_manager.hide_window()
        else:
            messagebox.showwarning(
                "Protected Mode",
                "Cannot close application while Protected Mode is active.\n"
                "The application will be minimized instead."
            )
            self.root.iconify()

    def open_protected_mode_dialog(self):
        """Open protected mode configuration dialog."""
        if not self.security_manager:
            return
        
        is_active = self._is_protected_mode_active()
        dialog = ProtectedModeDialog(self.root, self.security_manager, is_active)
        result = dialog.show()
        
        if result:
            action, value = result
            
            if action == "activate":
                if self.security_manager.activate_protected_mode(value):
                    if self.logger:
                        self.logger.info("Protected mode activated for %d days", value)
                    
                    # Apply restrictions immediately
                    self._apply_protected_mode_restrictions()
                    self._update_protected_mode_status()
                    
                    # Start monitoring if not already
                    if not self.is_monitoring:
                        self.start_monitoring()
                    
                    messagebox.showinfo(
                        "Protected Mode",
                        f"Protected Mode activated for {value} days.\n\n"
                        "Monitoring will remain active and the application\n"
                        "cannot be closed until the period expires."
                    )
            
            elif action == "deactivate":
                if self.logger:
                    self.logger.info("Protected mode deactivated by user")
                
                # Re-enable UI elements
                self._disable_protected_mode_ui()
                self._update_protected_mode_status()
                
                messagebox.showinfo(
                    "Protected Mode",
                    "Protected Mode has been deactivated.\n"
                    "You can now stop monitoring and close the application."
                )

    def _disable_protected_mode_ui(self):
        """Re-enable UI elements after protected mode deactivation."""
        # Re-enable toggle button
        if hasattr(self, 'toggle_btn'):
            self.toggle_btn.config(state=tk.NORMAL)
        
        # Re-enable checkboxes
        if hasattr(self, 'autostart_checkbox'):
            self.autostart_checkbox.config(state=tk.NORMAL)
        
        if hasattr(self, 'tray_checkbox') and self.tray_enabled:
            self.tray_checkbox.config(state=tk.NORMAL)
        
        # Restore close behavior
        if self.config.get("minimize_to_tray", False) and self.tray_manager:
            self.root.protocol("WM_DELETE_WINDOW", self.on_window_close)
        else:
            self.root.protocol("WM_DELETE_WINDOW", self.on_window_close_quit)

    def open_log_viewer(self):
        if self.log_viewer_window and self.log_viewer_window.winfo_exists():
            self.log_viewer_window.focus()
            return

        self.log_viewer_window = LogViewerWindow(
            self.root, self.app_log_path, on_close=self._log_viewer_closed
        )

    def _log_viewer_closed(self):
        self.log_viewer_window = None

    def _check_previous_session_state(self):
        try:
            with open(self.session_state_path, "r", encoding="utf-8") as f:
                state = json.load(f)
        except FileNotFoundError:
            return
        except json.JSONDecodeError:
            if self.logger:
                self.logger.warning("GUI session state file was corrupted; ignoring")
            return

        if not state.get("clean_exit", True):
            recovered = self._classify_shutdown_via_eventlog(state)
            if not recovered and self.logger:
                self.logger.warning(
                    "Previous GUI session ended unexpectedly (pid=%s, started=%s, reason=%s)",
                    state.get("pid"),
                    state.get("started_at"),
                    state.get("reason", "unknown"),
                )

    def _mark_session_start(self):
        self._current_session_state = {
            "pid": os.getpid(),
            "started_at": datetime.now(UTC).isoformat(),
            "clean_exit": False,
        }
        self._write_session_state(self._current_session_state)

    def _mark_session_end(self, reason):
        if not self._current_session_state:
            return
        self._current_session_state.update(
            {
                "clean_exit": True,
                "ended_at": datetime.now(UTC).isoformat(),
                "reason": reason,
            }
        )
        self._write_session_state(self._current_session_state)

    def _write_session_state(self, state):
        try:
            with open(self.session_state_path, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
        except Exception:
            if self.logger:
                self.logger.error("Failed to write GUI session state")

    def _log_boot_proximity(self, context):
        threshold = self.config.get("boot_start_window_seconds", 0)
        if threshold <= 0:
            return
        try:
            uptime = time.time() - psutil.boot_time()
        except Exception:
            return
        if uptime <= threshold and self.logger:
            self.logger.warning(
                "%s occurred %.0fs after system boot (threshold=%ss)",
                context,
                uptime,
                threshold,
            )

    def _classify_shutdown_via_eventlog(self, state):
        """Try to reclassify an unclean session as system shutdown using Windows event log."""
        if sys.platform != "win32":
            return False
        try:
            import win32evtlog
        except Exception:
            return False

        started_at = state.get("started_at")
        if not started_at:
            return False
        try:
            started_dt = datetime.fromisoformat(started_at)
        except Exception:
            return False

        window_seconds = 3600  # look back up to 1h from session start
        shutdown_event_ids = {6005, 6006, 6008}  # system startup, clean shutdown, unexpected, planned

        handle = None
        try:
            handle = win32evtlog.OpenEventLog(None, "System")
            flags = win32evtlog.EVENTLOG_BACKWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ
            matched_ts = None

            while True:
                records = win32evtlog.ReadEventLog(handle, flags, 0)
                if not records:
                    break
                for event in records:
                    event_id = event.EventID & 0xFFFF
                    if event_id not in shutdown_event_ids:
                        continue
                    ts = event.TimeGenerated
                    try:
                        ts = datetime.fromtimestamp(ts.timestamp(), tz=UTC)
                    except Exception:
                        continue
                    # Consider shutdown valid if it happened after session start and within window
                    if ts >= started_dt.astimezone(UTC) and (ts - started_dt.astimezone(UTC)).total_seconds() <= window_seconds:
                        matched_ts = ts
                        break
                if matched_ts:
                    break

            if matched_ts:
                state.update(
                    {
                        "clean_exit": True,
                        "ended_at": matched_ts.isoformat(),
                        "reason": "system-shutdown-eventlog",
                    }
                )
                self._write_session_state(state)
                if self.logger:
                    self.logger.info(
                        "Reclassified previous session as system shutdown via EventLog (ts=%s)",
                        matched_ts.isoformat(),
                    )
                return True
        finally:
            if handle:
                try:
                    win32evtlog.CloseEventLog(handle)
                except Exception:
                    pass
        return False

    def _handle_system_shutdown_signal(self, source):
        """Handle Windows shutdown notifications (WM/CTRL/SERVICE signals)."""
        if self._shutdown_cleanup_scheduled:
            return
        self._shutdown_cleanup_scheduled = True
        self._shutdown_in_progress = True
        if self.logger:
            self.logger.info(
                "Windows shutdown control signal received (%s / SERVICE_CONTROL_SHUTDOWN)",
                source,
            )
        # Mark session end immediately in case the process gets terminated forcefully
        self._mark_session_end("system-shutdown")

        def _shutdown_callback():
            try:
                self.on_window_close_quit(reason="system-shutdown")
            except Exception:
                # If the UI is already torn down, ignore failures
                pass

        try:
            self.root.after(0, _shutdown_callback)
        except tk.TclError:
            _shutdown_callback()

    def _install_console_shutdown_handler(self):
        """Map console CTRL events to SERVICE_CONTROL_SHUTDOWN semantics."""
        if sys.platform != "win32":
            return
        try:
            import ctypes
        except Exception:
            return

        kernel32 = ctypes.windll.kernel32
        HANDLER_ROUTINE = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_uint)

        @HANDLER_ROUTINE
        def console_handler(ctrl_type):
            # CTRL_LOGOFF_EVENT (5) and CTRL_SHUTDOWN_EVENT (6) mirror SERVICE_CONTROL_SHUTDOWN
            if ctrl_type in (2, 5, 6):  # close/logoff/shutdown
                self._handle_system_shutdown_signal(f"CTRL_EVENT_{ctrl_type}")
                return True
            return False

        try:
            if kernel32.SetConsoleCtrlHandler(console_handler, True):
                self._console_ctrl_handler = console_handler
        except Exception:
            if self.logger:
                self.logger.warning("Failed to install console shutdown handler")


    def start_monitoring(self):
        if not self.config.get("time_limits", {}).get("dedicated"):
            messagebox.showwarning(
                "Warning", "No applications configured for monitoring."
            )
            return

        try:
            self._log_boot_proximity("Monitor start requested")
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

            self.state_manager.set_monitoring(True)
            self.config["enabled"] = True
            self.save_config()
            self.update_status()

            grace_seconds = self._compute_heartbeat_ttl()
            self._watchdog_grace_deadline = datetime.now(UTC) + timedelta(
                seconds=grace_seconds
            )

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

        self.state_manager.set_monitoring(False)
        self.config["enabled"] = False
        self.save_config()
        self.update_status()
        self._watchdog_grace_deadline = None

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
        """Update UI status display based on state manager."""
        if self.is_monitoring:
            self.status_label.config(text="🟢 MONITORING ACTIVE", foreground="green")
            self.toggle_btn.config(text="Stop Monitoring")
        else:
            self.status_label.config(text="🔴 MONITORING STOPPED", foreground="red")
            self.toggle_btn.config(text="Start Monitoring")

    def refresh_timer(self):
        if self.is_monitoring:
            self.refresh_apps_list()
            if self.monitoring_process and self.monitoring_process.poll() is not None:
                exit_code = self.monitoring_process.poll()
                if self.logger:
                    self.logger.error(
                        "Monitor process exited unexpectedly (code=%s)", exit_code
                    )
                self.stop_monitoring()
                return
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

    def on_window_close_quit(self, reason=None):
        """Handle window close event - quit application"""
        # Only terminate the process, preserve the enabled state for next startup
        if self._shutdown_in_progress:
            final_reason = "system-shutdown"
        else:
            final_reason = reason or "user-quit"
        if self.logger:
            self.logger.info("GUI exiting (%s)", final_reason)
        self._mark_session_end(final_reason)
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
        """
        Restore monitoring state from config on startup.
        
        WHY: On startup, we need to determine if monitoring should be active.
        This method now uses StateManager to detect actual running monitor
        process (e.g., started by autostart) vs just reading config flag.
        """
        if self.logger:
            self.logger.info("Restoring monitoring state from config...")
        
        # First check if monitor is actually already running (e.g., from autostart)
        actual_monitoring = self.state_manager.detect_actual_monitoring_state()
        existing_pid = self.state_manager.get_running_monitor_pid()
        
        if actual_monitoring and existing_pid:
            # Monitor is already running - attach to it instead of starting new
            if self.logger:
                self.logger.info("Monitor already running (PID=%s); attaching to existing process", existing_pid)
            self.state_manager.set_monitoring(True)
            self.update_status()
            self.refresh_timer()
            return
        
        if self.config.get("enabled", False):
            # Only restore if there are apps to monitor
            if self.config.get("time_limits", {}).get("dedicated"):
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
            if self.logger:
                self.logger.info("Monitoring was not enabled in previous session, skipping restore")

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

    def _within_watchdog_grace(self):
        if not self._watchdog_grace_deadline:
            return False
        return datetime.now(UTC) <= self._watchdog_grace_deadline

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
        if heartbeat_fresh and self._watchdog_grace_deadline:
            self._watchdog_grace_deadline = None
        elif not heartbeat_fresh and self._within_watchdog_grace():
            heartbeat_fresh = True

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
                self.logger.error("Watchdog detected monitor issue: %s", reason)

        if self.config.get("watchdog_restart", True):
            if self._watchdog_restart_running:
                return
            try:
                if self.logger:
                    self.logger.info("Watchdog attempting to restart monitor")
                self._watchdog_restart_running = True
                self._terminate_monitoring_process()
                self.state_manager.set_monitoring(False, notify=False)
                self.start_monitoring()
                return
            except Exception as e:
                if self.logger:
                    self.logger.error("Watchdog restart failed: %s", e)
            finally:
                self._watchdog_restart_running = False

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


class LogViewerWindow:
    LEVELS = ["ALL", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

    def __init__(self, master, log_path: Path, on_close=None):
        self.master = master
        self.log_path = Path(log_path)
        self.on_close = on_close

        self.window = tk.Toplevel(master)
        self.window.title("App Blocker Logs")
        self.window.geometry("800x450")
        self.window.protocol("WM_DELETE_WINDOW", self._handle_close)

        filter_frame = ttk.Frame(self.window, padding="10 10 10 0")
        filter_frame.pack(fill=tk.X)

        ttk.Label(filter_frame, text="Level:").pack(side=tk.LEFT)
        self.level_var = tk.StringVar(value="ALL")
        self.level_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.level_var,
            values=self.LEVELS,
            state="readonly",
            width=10,
        )
        self.level_combo.pack(side=tk.LEFT, padx=(5, 15))

        ttk.Label(filter_frame, text="Search:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(filter_frame, textvariable=self.search_var, width=30)
        search_entry.pack(side=tk.LEFT, padx=(5, 10))

        ttk.Button(filter_frame, text="Refresh", command=self.refresh_entries).pack(
            side=tk.LEFT
        )
        ttk.Button(filter_frame, text="Clear", command=self._clear_filters).pack(
            side=tk.LEFT, padx=(5, 0)
        )

        tree_frame = ttk.Frame(self.window, padding=10)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("timestamp", "level", "name", "message")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings")
        for col in columns:
            self.tree.heading(col, text=col.title())

        self.tree.column("timestamp", width=150, anchor=tk.W)
        self.tree.column("level", width=80, anchor=tk.W)
        self.tree.column("name", width=200, anchor=tk.W)
        self.tree.column("message", width=350, anchor=tk.W)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.level_var.trace_add("write", lambda *args: self.refresh_entries())
        self.search_var.trace_add("write", lambda *args: self.refresh_entries())

        self.refresh_entries()

    def _handle_close(self):
        if callable(self.on_close):
            self.on_close()
        self.window.destroy()

    def winfo_exists(self):
        return bool(self.window and self.window.winfo_exists())

    def focus(self):
        if self.window:
            self.window.deiconify()
            self.window.lift()
            self.window.focus_force()

    def _clear_filters(self):
        self.level_var.set("ALL")
        self.search_var.set("")

    def refresh_entries(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        entries = self._load_entries()
        level_filter = self.level_var.get()
        query = self.search_var.get().strip().lower()

        for entry in entries:
            if level_filter != "ALL" and entry["level"].upper() != level_filter:
                continue
            if query and query not in entry["message"].lower() and query not in entry["name"].lower():
                continue
            self.tree.insert(
                "",
                tk.END,
                values=(
                    entry["timestamp"],
                    entry["level"],
                    entry["name"],
                    entry["message"],
                ),
            )

    def _load_entries(self):
        entries = []
        if not self.log_path.exists():
            return entries

        try:
            with open(self.log_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    parsed = parse_log_line(line)
                    if parsed:
                        entries.append(parsed)
        except Exception:
            pass

        return entries


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

    # === Security manager initialization ===
    # Handle password setup or unlock before showing main GUI.
    
    root = tk.Tk()
    root.withdraw()  # Hide main window during security setup
    
    # Check if cryptography is available
    if not check_crypto_available():
        messagebox.showerror(
            "Missing Dependency",
            "The 'cryptography' package is required for encryption.\n\n"
            "Please install it with:\n"
            "pip install cryptography\n\n"
            "Or using Poetry:\n"
            "poetry install"
        )
        root.destroy()
        sys.exit(1)
    
    # Get app directory for security manager
    if getattr(sys, "frozen", False):
        app_dir = Path(sys.executable).parent
    else:
        app_dir = Path(__file__).parent
    
    security_manager = SecurityManager(app_dir)
    
    if not security_manager.is_password_set():
        # First run - show password setup dialog
        setup_dialog = MasterPasswordSetupDialog(root)
        result = setup_dialog.show()
        
        if result is None:
            # User cancelled - exit
            root.destroy()
            sys.exit(0)
        
        mode, password = result
        
        if mode == "custom":
            if not security_manager.setup_password(password):
                messagebox.showerror(
                    "Error",
                    f"Password must be at least {get_min_password_length()} characters."
                )
                root.destroy()
                sys.exit(1)
        else:
            # Generated password - user explicitly doesn't want to know it
            success, _ = security_manager.setup_generated_password()
            if not success:
                messagebox.showerror("Error", "Failed to generate password.")
                root.destroy()
                sys.exit(1)

    # Show main window
    root.deiconify()
    
    app = AppBlockerGUI(root, single_instance_lock, security_manager)

    # Set up appropriate close behavior based on tray settings and protected mode
    if app._is_protected_mode_active():
        root.protocol("WM_DELETE_WINDOW", app._on_close_protected)
    elif app.config.get("minimize_to_tray", False) and app.tray_manager:
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
