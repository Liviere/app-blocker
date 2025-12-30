"""
Tests for system tray functionality
"""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, MagicMock, patch
import sys
import os

# Add the project root to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.system_tray import SystemTrayManager, is_tray_supported


class MockStateManager:
    """Mock StateManager for testing"""
    def __init__(self):
        self.is_monitoring = False
        self.is_protected_mode = False


class MockGUIApp:
    """Mock GUI application for testing"""
    
    def __init__(self):
        self.app_dir = Path(tempfile.mkdtemp())
        self.is_monitoring = False
        self.root = MagicMock()
        # Add mock state_manager since system_tray now depends on it
        self.state_manager = MockStateManager()
    
    def toggle_monitoring(self):
        self.is_monitoring = not self.is_monitoring
        # Also update state_manager to keep in sync
        self.state_manager.is_monitoring = self.is_monitoring
    
    def stop_monitoring(self):
        self.is_monitoring = False
        self.state_manager.is_monitoring = False


class TestSystemTrayManager:
    """Test SystemTrayManager functionality"""

    def setup_method(self):
        """Setup test environment"""
        self.mock_app = MockGUIApp()
        self.tray_manager = SystemTrayManager(self.mock_app)

    def test_create_icon_image(self):
        """Test icon image creation"""
        # This test will only pass if PIL is available
        try:
            from PIL import Image
            image = self.tray_manager.create_icon_image()
            assert image is not None
            assert image.size == (64, 64)
            
            # Test different colors
            blue_image = self.tray_manager.create_icon_image("blue")
            green_image = self.tray_manager.create_icon_image("green")
            assert blue_image is not None
            assert green_image is not None
        except ImportError:
            pytest.skip("PIL not available")

    def test_get_icon_from_file_fallback(self):
        """Test icon loading with fallback to generated icon"""
        # Should fallback to generated icon when file doesn't exist
        icon = self.tray_manager.get_icon_from_file()
        assert icon is not None

    def test_get_icon_from_file_success(self):
        """Test successful icon loading from file"""
        try:
            from PIL import Image
            
            # Create a test icon file
            assets_dir = self.mock_app.app_dir / "assets"
            assets_dir.mkdir()
            icon_path = assets_dir / "icon.ico"
            
            # Create a simple test image
            test_image = Image.new('RGBA', (32, 32), (255, 0, 0, 255))
            test_image.save(icon_path, 'ICO')
            
            icon = self.tray_manager.get_icon_from_file()
            assert icon is not None
        except ImportError:
            pytest.skip("PIL not available")

    def test_show_window(self):
        """Test showing the main window"""
        self.tray_manager.show_window()
        
        # Verify that the root window methods were called
        self.mock_app.root.deiconify.assert_called_once()
        self.mock_app.root.lift.assert_called_once()
        self.mock_app.root.focus_force.assert_called_once()

    def test_hide_window(self):
        """Test hiding the main window"""
        self.tray_manager.hide_window()
        
        # Verify that the root window was hidden
        self.mock_app.root.withdraw.assert_called_once()

    def test_toggle_monitoring(self):
        """Test toggling monitoring from tray"""
        initial_state = self.mock_app.is_monitoring
        self.tray_manager.toggle_monitoring()
        assert self.mock_app.is_monitoring != initial_state

    def test_quit_application(self):
        """Test quitting application from tray"""
        with patch.object(self.tray_manager, 'stop_tray') as mock_stop:
            self.tray_manager.quit_application()
            
            mock_stop.assert_called_once()
            assert self.mock_app.is_monitoring is False
            self.mock_app.root.quit.assert_called_once()
            self.mock_app.root.destroy.assert_called_once()

    def test_get_menu_items_monitoring_stopped(self):
        """Test menu items when monitoring is stopped"""
        self.mock_app.state_manager.is_monitoring = False
        
        with patch('app.system_tray.pystray') as mock_pystray:
            mock_pystray.MenuItem = MagicMock()
            mock_pystray.Menu = MagicMock()
            
            items = self.tray_manager.get_menu_items()
            
            # Should have 4 items (Show, Start Monitoring, Separator, Quit)
            assert len(items) == 4

    def test_get_menu_items_monitoring_active(self):
        """Test menu items when monitoring is active"""
        self.mock_app.state_manager.is_monitoring = True
        
        with patch('app.system_tray.pystray') as mock_pystray:
            mock_pystray.MenuItem = MagicMock()
            mock_pystray.Menu = MagicMock()
            
            items = self.tray_manager.get_menu_items()
            
            # Should have 4 items (Show, Stop Monitoring, Separator, Quit)
            assert len(items) == 4

    @patch('app.system_tray.pystray')
    @patch('threading.Thread')
    def test_start_tray_success(self, mock_thread, mock_pystray):
        """Test successful tray startup"""
        mock_icon = MagicMock()
        mock_pystray.Icon.return_value = mock_icon
        mock_pystray.Menu.return_value = MagicMock()
        
        result = self.tray_manager.start_tray()
        
        assert result is True
        assert self.tray_manager.is_running is True
        assert self.tray_manager.icon is mock_icon
        mock_thread.assert_called_once()

    @patch('app.system_tray.pystray')
    def test_start_tray_failure(self, mock_pystray):
        """Test tray startup failure"""
        mock_pystray.Icon.side_effect = Exception("Tray not available")
        
        result = self.tray_manager.start_tray()
        
        assert result is False
        assert self.tray_manager.is_running is False

    def test_start_tray_already_running(self):
        """Test starting tray when already running"""
        self.tray_manager.is_running = True
        
        result = self.tray_manager.start_tray()
        
        # Should return without doing anything
        assert result is None

    def test_stop_tray(self):
        """Test stopping tray"""
        mock_icon = MagicMock()
        self.tray_manager.icon = mock_icon
        self.tray_manager.is_running = True
        
        self.tray_manager.stop_tray()
        
        mock_icon.stop.assert_called_once()
        assert self.tray_manager.is_running is False

    def test_stop_tray_not_running(self):
        """Test stopping tray when not running"""
        self.tray_manager.icon = None
        self.tray_manager.is_running = False
        
        # Should not raise any exceptions
        self.tray_manager.stop_tray()

    def test_update_menu(self):
        """Test updating tray menu when state changes"""
        mock_icon = MagicMock()
        self.tray_manager.icon = mock_icon
        
        # Set initial cached state to different values to trigger update
        self.tray_manager._cached_is_monitoring = False
        self.tray_manager._cached_is_protected = False
        
        # Set current state to different value
        self.mock_app.state_manager.is_monitoring = True  # Different from cached
        
        with patch.object(self.tray_manager, 'get_menu_items', return_value=[]) as mock_get_items:
            with patch('app.system_tray.pystray') as mock_pystray:
                mock_pystray.Menu.return_value = MagicMock()
                
                self.tray_manager.update_menu()
                
                mock_get_items.assert_called_once()
                mock_pystray.Menu.assert_called_once()
    
    def test_update_menu_no_change(self):
        """Test that menu is not updated when state hasn't changed"""
        mock_icon = MagicMock()
        self.tray_manager.icon = mock_icon
        
        # Set cached state same as current state
        self.tray_manager._cached_is_monitoring = False
        self.tray_manager._cached_is_protected = False
        self.mock_app.state_manager.is_monitoring = False
        
        with patch.object(self.tray_manager, 'get_menu_items', return_value=[]) as mock_get_items:
            with patch('app.system_tray.pystray') as mock_pystray:
                mock_pystray.Menu.return_value = MagicMock()
                
                self.tray_manager.update_menu()
                
                # Should not be called because state hasn't changed
                mock_get_items.assert_not_called()

    def test_update_icon_color_monitoring(self):
        """Test updating icon color when monitoring"""
        mock_icon = MagicMock()
        self.tray_manager.icon = mock_icon
        self.mock_app.state_manager.is_monitoring = True
        
        with patch.object(self.tray_manager, 'create_icon_image') as mock_create:
            self.tray_manager.update_icon_color()
            mock_create.assert_called_once_with("green")

    def test_update_icon_color_not_monitoring(self):
        """Test updating icon color when not monitoring"""
        mock_icon = MagicMock()
        self.tray_manager.icon = mock_icon
        self.mock_app.state_manager.is_monitoring = False
        
        with patch.object(self.tray_manager, 'create_icon_image') as mock_create:
            self.tray_manager.update_icon_color()
            mock_create.assert_called_once_with("blue")

    def test_is_tray_available_true(self):
        """Test checking tray availability when available"""
        result = self.tray_manager.is_tray_available()
        # Since pystray is installed, this should be True
        assert result is True

    @patch('app.system_tray._check_pystray_import')
    def test_is_tray_available_mock_false(self, mock_check):
        """Test checking tray availability when mocked as unavailable"""
        mock_check.return_value = False
        result = self.tray_manager.is_tray_available()
        assert result is False


class TestTraySupport:
    """Test tray support functions"""

    def test_is_tray_supported_true(self):
        """Test tray support detection when supported"""
        result = is_tray_supported()
        # Since pystray is installed, this should be True
        assert result is True

    @patch('app.system_tray._check_pystray_import')
    def test_is_tray_supported_mock_false(self, mock_check):
        """Test tray support detection when mocked as not supported"""
        mock_check.return_value = False
        result = is_tray_supported()
        assert result is False


if __name__ == "__main__":
    pytest.main([__file__])
