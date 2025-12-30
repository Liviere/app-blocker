"""
Tests for autostart functionality
"""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys
import os

from app.autostart import AutostartManager, is_autostart_enabled, set_autostart


class TestAutostartManager:
    """Test AutostartManager functionality"""

    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.manager = AutostartManager()

    def test_get_app_directory_script_mode(self):
        """Test getting app directory in script mode"""
        with patch('sys.frozen', False, create=True):
            with patch('app.autostart.__file__', '/test/path/autostart.py'):
                manager = AutostartManager()
                expected_path = Path('C:/test')
                assert manager.app_dir == expected_path

    def test_get_app_directory_frozen_mode(self):
        """Test getting app directory in frozen mode"""
        with patch('sys.frozen', True, create=True):
            with patch('sys.executable', '/test/path/app.exe'):
                manager = AutostartManager()
                expected_path = Path('/test/path')
                assert manager.app_dir == expected_path

    @patch('winreg.OpenKey')
    @patch('winreg.QueryValueEx')
    def test_is_autostart_enabled_true(self, mock_query, mock_open):
        """Test checking autostart when enabled"""
        mock_key = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_key
        mock_query.return_value = ('some_path', 'some_type')
        
        result = self.manager.is_autostart_enabled()
        assert result is True

    @patch('winreg.OpenKey')
    @patch('winreg.QueryValueEx')
    def test_is_autostart_enabled_false(self, mock_query, mock_open):
        """Test checking autostart when disabled"""
        mock_key = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_key
        mock_query.side_effect = FileNotFoundError()
        
        result = self.manager.is_autostart_enabled()
        assert result is False

    @patch('winreg.OpenKey')
    @patch('winreg.SetValueEx')
    def test_enable_autostart_success(self, mock_set, mock_open):
        """Test enabling autostart successfully"""
        mock_key = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_key
        
        with patch.object(self.manager, 'get_gui_executable_path', return_value='test_path.exe'):
            result = self.manager.enable_autostart()
            assert result is True
            mock_set.assert_called_once()

    @patch('winreg.OpenKey')
    @patch('winreg.DeleteValue')
    def test_disable_autostart_success(self, mock_delete, mock_open):
        """Test disabling autostart successfully"""
        mock_key = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_key
        
        result = self.manager.disable_autostart()
        assert result is True
        mock_delete.assert_called_once_with(mock_key, 'AppBlocker')

    @patch('winreg.OpenKey')
    @patch('winreg.DeleteValue')
    def test_disable_autostart_not_exists(self, mock_delete, mock_open):
        """Test disabling autostart when entry doesn't exist"""
        mock_key = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_key
        mock_delete.side_effect = FileNotFoundError()
        
        result = self.manager.disable_autostart()
        assert result is True  # Should still return True

    def test_get_gui_executable_path_frozen_mode(self):
        """Test getting GUI executable path in frozen mode"""
        with patch('sys.frozen', True, create=True):
            test_dir = Path(self.temp_dir)
            gui_exe = test_dir / "app-blocker-gui.exe"
            gui_exe.touch()  # Create the file
            
            with patch.object(self.manager, 'app_dir', test_dir):
                result = self.manager.get_gui_executable_path()
                expected = f'"{gui_exe}"'
                assert result == expected

    def test_get_gui_executable_path_script_mode(self):
        """Test getting GUI executable path in script mode"""
        with patch('sys.frozen', False, create=True):
            test_dir = Path(self.temp_dir)
            gui_py = test_dir / "gui.py"
            gui_py.touch()  # Create the file
            
            with patch.object(self.manager, 'app_dir', test_dir):
                with patch('sys.executable', 'python.exe'):
                    result = self.manager.get_gui_executable_path()
                    expected = f'"python.exe" "{gui_py}"'
                    assert result == expected

    def test_set_autostart_enable(self):
        """Test setting autostart to enabled"""
        with patch.object(self.manager, 'enable_autostart', return_value=True) as mock_enable:
            result = self.manager.set_autostart(True)
            assert result is True
            mock_enable.assert_called_once()

    def test_set_autostart_disable(self):
        """Test setting autostart to disabled"""
        with patch.object(self.manager, 'disable_autostart', return_value=True) as mock_disable:
            result = self.manager.set_autostart(False)
            assert result is True
            mock_disable.assert_called_once()

    def test_get_gui_executable_path_with_args_frozen(self):
        """Test getting GUI executable path with extra arguments in frozen mode"""
        with patch('sys.frozen', True, create=True):
            test_dir = Path(self.temp_dir)
            gui_exe = test_dir / "app-blocker-gui.exe"
            gui_exe.touch()
            
            with patch.object(self.manager, 'app_dir', test_dir):
                result = self.manager.get_gui_executable_path("--minimized")
                expected = f'"{gui_exe}" --minimized'
                assert result == expected

    def test_get_gui_executable_path_with_args_script(self):
        """Test getting GUI executable path with extra arguments in script mode"""
        with patch('sys.frozen', False, create=True):
            test_dir = Path(self.temp_dir)
            gui_py = test_dir / "gui.py"
            gui_py.touch()
            
            with patch.object(self.manager, 'app_dir', test_dir):
                with patch('sys.executable', 'python.exe'):
                    result = self.manager.get_gui_executable_path("--minimized")
                    expected = f'"python.exe" "{gui_py}" --minimized'
                    assert result == expected

    def test_should_start_minimized_true(self):
        """Test should_start_minimized when tray is enabled"""
        config_data = {"minimize_to_tray": True}
        config_path = Path(self.temp_dir) / "config.json"
        
        with open(config_path, "w") as f:
            json.dump(config_data, f)
        
        with patch.object(self.manager, 'app_dir', Path(self.temp_dir)):
            result = self.manager.should_start_minimized()
            assert result is True

    def test_should_start_minimized_false(self):
        """Test should_start_minimized when tray is disabled"""
        config_data = {"minimize_to_tray": False}
        config_path = Path(self.temp_dir) / "config.json"
        
        with open(config_path, "w") as f:
            json.dump(config_data, f)
        
        with patch.object(self.manager, 'app_dir', Path(self.temp_dir)):
            result = self.manager.should_start_minimized()
            assert result is False

    def test_should_start_minimized_no_config(self):
        """Test should_start_minimized when config doesn't exist"""
        with patch.object(self.manager, 'app_dir', Path(self.temp_dir)):
            result = self.manager.should_start_minimized()
            assert result is False


class TestConvenienceFunctions:
    """Test convenience functions"""

    @patch('app.autostart.AutostartManager')
    def test_is_autostart_enabled_function(self, mock_manager_class):
        """Test is_autostart_enabled convenience function"""
        mock_manager = MagicMock()
        mock_manager.is_autostart_enabled.return_value = True
        mock_manager_class.return_value = mock_manager
        
        result = is_autostart_enabled()
        assert result is True

    @patch('app.autostart.AutostartManager')
    def test_set_autostart_function(self, mock_manager_class):
        """Test set_autostart convenience function"""
        mock_manager = MagicMock()
        mock_manager.set_autostart.return_value = True
        mock_manager_class.return_value = mock_manager
        
        result = set_autostart(True)
        assert result is True
        mock_manager.set_autostart.assert_called_once_with(True)


if __name__ == "__main__":
    pytest.main([__file__])
