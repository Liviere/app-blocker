"""
System tray functionality for App Blocker
Provides system tray icon with context menu
"""

import pystray
import tkinter as tk
from PIL import Image, ImageDraw
import threading
import sys
from pathlib import Path


class SystemTrayManager:
    """Manages system tray icon and functionality"""
    
    def __init__(self, gui_app):
        self.gui_app = gui_app
        self.icon = None
        self.tray_thread = None
        self.is_running = False
        
    def create_icon_image(self, color="blue"):
        """Create a simple icon image for the tray"""
        # Create a simple circular icon
        width = 64
        height = 64
        image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        
        # Draw a circle
        margin = 8
        draw.ellipse([margin, margin, width-margin, height-margin], 
                    fill=color, outline='white', width=2)
        
        # Draw "AB" text for App Blocker
        try:
            # Try to draw text (may not work without specific fonts)
            text_x = width // 2 - 8
            text_y = height // 2 - 8
            draw.text((text_x, text_y), "AB", fill='white')
        except:
            # If text fails, draw a simple pattern
            center_x, center_y = width // 2, height // 2
            draw.rectangle([center_x-8, center_y-2, center_x+8, center_y+2], fill='white')
            draw.rectangle([center_x-2, center_y-8, center_x+2, center_y+8], fill='white')
        
        return image
    
    def get_icon_from_file(self):
        """Try to load icon from assets directory"""
        try:
            icon_path = self.gui_app.app_dir / "assets" / "icon.ico"
            if icon_path.exists():
                return Image.open(icon_path)
        except Exception as e:
            print(f"Could not load icon from file: {e}")
        
        # Fallback to generated icon
        return self.create_icon_image()
    
    def show_window(self, icon=None, item=None):
        """Show the main window"""
        self.gui_app.root.deiconify()
        self.gui_app.root.lift()
        self.gui_app.root.focus_force()
    
    def hide_window(self):
        """Hide the main window to tray"""
        self.gui_app.root.withdraw()
    
    def toggle_monitoring(self, icon=None, item=None):
        """Toggle monitoring from tray"""
        self.gui_app.toggle_monitoring()
    
    def quit_application(self, icon=None, item=None):
        """Quit the application completely"""
        quit_handler = getattr(self.gui_app, "on_window_close_quit", None)
        if callable(quit_handler):
            quit_handler(reason="tray-quit")
        else:
            # Fallback to legacy behavior if handler missing
            self.stop_tray()
            self.gui_app.stop_monitoring()
            self.gui_app.root.quit()
            self.gui_app.root.destroy()
    
    def get_menu_items(self):
        """Create context menu items"""
        monitoring_text = "Stop Monitoring" if self.gui_app.is_monitoring else "Start Monitoring"
        
        # Check if protected mode is active
        is_protected = False
        if hasattr(self.gui_app, '_is_protected_mode_active'):
            is_protected = self.gui_app._is_protected_mode_active()
        
        # Disable monitoring toggle and quit during protected mode
        return (
            pystray.MenuItem("Show App Blocker", self.show_window, default=True),
            pystray.MenuItem(monitoring_text, self.toggle_monitoring, enabled=not is_protected),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self.quit_application, enabled=not is_protected)
        )
    
    def update_menu(self):
        """Update the tray menu (called when monitoring state changes)"""
        if self.icon:
            self.icon.menu = pystray.Menu(*self.get_menu_items())
    
    def update_icon_color(self):
        """Update icon color based on monitoring state"""
        if self.icon:
            color = "green" if self.gui_app.is_monitoring else "blue"
            self.icon.icon = self.create_icon_image(color)
    
    def start_tray(self):
        """Start the system tray icon"""
        if self.is_running:
            return
        
        try:
            # Create the icon
            image = self.get_icon_from_file()
            menu = pystray.Menu(*self.get_menu_items())
            
            self.icon = pystray.Icon(
                "AppBlocker",
                image,
                "App Blocker",
                menu
            )
            
            self.is_running = True
            
            # Run in separate thread
            self.tray_thread = threading.Thread(target=self._run_tray, daemon=True)
            self.tray_thread.start()
            
            print("System tray started")
            return True
            
        except Exception as e:
            print(f"Failed to start system tray: {e}")
            return False
    
    def _run_tray(self):
        """Run the tray icon (called in thread)"""
        try:
            self.icon.run()
        except Exception as e:
            print(f"Tray icon error: {e}")
        finally:
            self.is_running = False
    
    def stop_tray(self):
        """Stop the system tray icon"""
        if self.icon and self.is_running:
            try:
                self.icon.stop()
                self.is_running = False
                print("System tray stopped")
            except Exception as e:
                print(f"Error stopping tray: {e}")
    
    def is_tray_available(self):
        """Check if system tray is available"""
        return _check_pystray_import()


def _check_pystray_import():
    """Helper function to check if pystray can be imported - useful for testing"""
    try:
        import pystray
        return True
    except ImportError:
        return False


def is_tray_supported():
    """Check if system tray is supported on this system"""
    return _check_pystray_import()


if __name__ == "__main__":
    # Test tray functionality
    if is_tray_supported():
        print("System tray is supported")
        
        # Create a simple test
        root = tk.Tk()
        root.title("Test App")
        
        class TestApp:
            def __init__(self, root):
                self.root = root
                self.app_dir = Path(__file__).parent
                self.is_monitoring = False
            
            def toggle_monitoring(self):
                self.is_monitoring = not self.is_monitoring
                print(f"Monitoring: {self.is_monitoring}")
            
            def stop_monitoring(self):
                self.is_monitoring = False
                print("Monitoring stopped")
        
        app = TestApp(root)
        tray = SystemTrayManager(app)
        
        if tray.start_tray():
            print("Test tray started successfully")
        
        root.mainloop()
    else:
        print("System tray is not supported")
