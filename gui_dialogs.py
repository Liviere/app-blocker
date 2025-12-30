"""
Dialog classes for App Blocker GUI.

WHY: Separates dialog UI from main GUI logic for better maintainability.
Contains all modal dialogs used in the application.
"""
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, UTC

from dialog_base import BaseDialog
from security_manager import SecurityManager, get_min_password_length
from time_utils import validate_time_format, time_str_to_minutes, validate_blocked_hours


# === Password Setup Dialog ===
# Dialog for initial master password configuration.


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


# === Unlock Dialog ===
# Password entry for unlocking encrypted configuration.


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


# === Protected Mode Dialog ===
# Activation and deactivation of protected mode.


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


# === Time Range Dialog ===
# Single time range entry with validation.


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


# === 5: Blocked Hours Dialog ===
# List management for blocked time ranges.


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


# === CHECKPOINT 6: App Configuration Dialog ===
# Entry for application name and time limit.


class AppDialog:
    """
    Dialog for adding or editing an application time limit.
    
    WHY: Provides simple form for app name + time limit configuration.
    """
    
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
        """Show dialog and return result."""
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

