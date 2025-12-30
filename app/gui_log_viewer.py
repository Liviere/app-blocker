"""
Log viewer window for App Blocker.

WHY: Separates log viewing UI from main GUI logic.
Provides filterable view of application logs.
"""
import tkinter as tk
from tkinter import ttk
from pathlib import Path

from .logger_utils import parse_log_line


# === Log Viewer Window ===
# Standalone window for viewing and filtering application logs.


class LogViewerWindow:
    """
    Window for viewing and filtering application logs.
    
    WHY: Provides searchable, filterable interface to debug logs.
    Shows timestamp, level, logger name, and message for each entry.
    """
    
    LEVELS = ["ALL", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

    def __init__(self, master, log_path: Path, on_close=None):
        self.master = master
        self.log_path = Path(log_path)
        self.on_close = on_close

        self.window = tk.Toplevel(master)
        self.window.title("App Blocker Logs")
        self.window.geometry("800x450")
        self.window.protocol("WM_DELETE_WINDOW", self._handle_close)

        # === Filter bar ===
        # Level dropdown and search box for filtering entries.
        
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

        # === Log entries tree ===
        # Treeview showing timestamp, level, name, message columns.
        
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

        # Auto-refresh on filter change
        self.level_var.trace_add("write", lambda *args: self.refresh_entries())
        self.search_var.trace_add("write", lambda *args: self.refresh_entries())

        self.refresh_entries()

    def _handle_close(self):
        """Handle window close - call callback if provided."""
        if callable(self.on_close):
            self.on_close()
        self.window.destroy()

    def winfo_exists(self):
        """Check if window still exists."""
        return bool(self.window and self.window.winfo_exists())

    def focus(self):
        """Bring window to front."""
        if self.window:
            self.window.deiconify()
            self.window.lift()
            self.window.focus_force()

    def _clear_filters(self):
        """Reset filters to default (show all)."""
        self.level_var.set("ALL")
        self.search_var.set("")

    def refresh_entries(self):
        """
        Reload and filter log entries.
        
        WHY: Applies current level and search filters to log file.
        Called on filter change or manual refresh.
        """
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
        """
        Load all log entries from file.
        
        WHY: Reads log file and parses each line using logger_utils.
        Returns list of dicts with timestamp, level, name, message.
        """
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
