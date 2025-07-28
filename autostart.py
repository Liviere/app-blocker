"""
Windows autostart functionality for App Blocker
Manages registry entries for automatic startup
"""

import winreg
import sys
import os
from pathlib import Path


class AutostartManager:
    """Manages Windows autostart functionality through registry"""
    
    REGISTRY_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
    APP_NAME = "AppBlocker"
    
    def __init__(self):
        self.app_dir = self.get_app_directory()
    
    def get_app_directory(self):
        """Get application directory - works with both development and PyInstaller"""
        if getattr(sys, "frozen", False):
            # Running as compiled executable
            return Path(sys.executable).parent
        else:
            # Running as script
            return Path(__file__).parent
    
    def get_gui_executable_path(self):
        """Get path to GUI executable for autostart"""
        if getattr(sys, "frozen", False):
            # Look for compiled GUI executable
            gui_path = self.app_dir / "app-blocker-gui.exe"
            if gui_path.exists():
                return str(gui_path)
            
            # Alternative name
            gui_path = self.app_dir / "gui.exe"
            if gui_path.exists():
                return str(gui_path)
            
            # If neither exists, use current executable if it's the GUI
            if "gui" in sys.executable.lower():
                return sys.executable
            
            raise FileNotFoundError("Could not find GUI executable for autostart")
        else:
            # Development mode - use Python script
            gui_path = self.app_dir / "gui.py"
            return f'"{sys.executable}" "{gui_path}"'
    
    def is_autostart_enabled(self):
        """Check if autostart is currently enabled"""
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.REGISTRY_KEY) as key:
                try:
                    winreg.QueryValueEx(key, self.APP_NAME)
                    return True
                except FileNotFoundError:
                    return False
        except Exception as e:
            print(f"Error checking autostart status: {e}")
            return False
    
    def enable_autostart(self):
        """Enable autostart by adding registry entry"""
        try:
            executable_path = self.get_gui_executable_path()
            
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.REGISTRY_KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, self.APP_NAME, 0, winreg.REG_SZ, executable_path)
            
            print(f"Autostart enabled: {executable_path}")
            return True
        except Exception as e:
            print(f"Error enabling autostart: {e}")
            return False
    
    def disable_autostart(self):
        """Disable autostart by removing registry entry"""
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.REGISTRY_KEY, 0, winreg.KEY_SET_VALUE) as key:
                try:
                    winreg.DeleteValue(key, self.APP_NAME)
                    print("Autostart disabled")
                    return True
                except FileNotFoundError:
                    # Entry doesn't exist, consider it successful
                    print("Autostart entry not found (already disabled)")
                    return True
        except Exception as e:
            print(f"Error disabling autostart: {e}")
            return False
    
    def set_autostart(self, enabled):
        """Enable or disable autostart based on boolean value"""
        if enabled:
            return self.enable_autostart()
        else:
            return self.disable_autostart()


# Convenience functions for easy import
def is_autostart_enabled():
    """Check if autostart is enabled"""
    manager = AutostartManager()
    return manager.is_autostart_enabled()


def set_autostart(enabled):
    """Set autostart state"""
    manager = AutostartManager()
    return manager.set_autostart(enabled)


if __name__ == "__main__":
    # Test functionality
    manager = AutostartManager()
    print(f"Autostart enabled: {manager.is_autostart_enabled()}")
    print(f"GUI executable path: {manager.get_gui_executable_path()}")
