"""
Base dialog class for App Blocker GUI dialogs.

WHY: Eliminates boilerplate code for dialog setup, positioning, and lifecycle.
All dialogs share common patterns: window creation, centering, grab_set, and cancel handling.
"""
import tkinter as tk
from typing import Any, Optional


class BaseDialog:
    """
    Base class for modal dialogs.
    
    WHY: Provides common functionality for all dialogs:
    - Window creation and configuration
    - Positioning (center on screen or parent)
    - Modal behavior (grab_set, protocol handling)
    - Standard cancel behavior
    
    USAGE:
        class MyDialog(BaseDialog):
            def __init__(self, parent):
                super().__init__(parent, "My Dialog", width=400, height=300)
                self._build_ui()
    """
    
    def __init__(
        self,
        parent: tk.Tk,
        title: str,
        width: int = 300,
        height: int = 200,
        center_on_screen: bool = True
    ):
        """
        Initialize base dialog.
        
        Args:
            parent: Parent window (may be hidden, so we center on screen by default)
            title: Dialog window title
            width: Dialog width in pixels
            height: Dialog height in pixels
            center_on_screen: If True, center on screen; if False, center on parent
        
        WHY: Setting up modal dialog requires multiple steps that are identical
        for all dialogs. This centralizes that setup.
        """
        self.result = None
        
        # Create toplevel window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry(f"{width}x{height}")
        
        # Make modal
        # Note: Don't use transient() when parent is hidden - causes dialog to be invisible
        self.dialog.grab_set()
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_cancel)
        
        # Position dialog
        if center_on_screen:
            self._center_on_screen(width, height)
        else:
            self._center_on_parent(parent, width, height)
    
    def _center_on_screen(self, width: int, height: int) -> None:
        """
        Center dialog on screen.
        
        WHY: Parent window may be hidden (especially during startup),
        so we position relative to screen center instead.
        """
        self.dialog.update_idletasks()
        screen_width = self.dialog.winfo_screenwidth()
        screen_height = self.dialog.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        self.dialog.geometry(f"{width}x{height}+{x}+{y}")
    
    def _center_on_parent(self, parent: tk.Tk, width: int, height: int) -> None:
        """
        Center dialog on parent window.
        
        WHY: For dialogs shown when parent is visible (e.g., settings dialogs),
        centering on parent provides better UX.
        """
        self.dialog.update_idletasks()
        parent_x = parent.winfo_x()
        parent_y = parent.winfo_y()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()
        
        x = parent_x + (parent_width - width) // 2
        y = parent_y + (parent_height - height) // 2
        self.dialog.geometry(f"{width}x{height}+{x}+{y}")
    
    def _on_cancel(self) -> None:
        """
        Handle dialog cancel/close.
        
        WHY: Standard behavior for all dialogs - set result to None/False
        and close dialog.
        """
        self.result = None
        self.dialog.destroy()
    
    def show(self) -> Any:
        """
        Show dialog and wait for result.
        
        WHY: Provides consistent API for all dialogs - call show() and get result.
        Blocks until dialog is closed.
        
        Returns:
            Dialog result (type depends on specific dialog implementation)
        """
        self.dialog.wait_window()
        return self.result
