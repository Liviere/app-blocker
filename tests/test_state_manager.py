"""
Tests for state_manager module.

This module tests centralized state management functionality
including Observer pattern, state synchronization, and
monitoring state detection.
"""

import json
import os
import tempfile
import threading
import time
from datetime import datetime, UTC, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.state_manager import (
    StateManager,
    StateEvent,
    create_state_manager,
)


# === Test fixtures ===
# Provide isolated test environment with temp files.


@pytest.fixture
def temp_app_dir():
    """
    Create a temporary directory with mock config and heartbeat files.
    
    WHY: Tests need isolated environment to avoid affecting real config.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        app_dir = Path(tmpdir)
        
        # Create default config
        config = {
            "time_limits": {"overall": 0, "dedicated": {"notepad.exe": 60}},
            "check_interval": 30,
            "enabled": False,
            "heartbeat_ttl_seconds": 70,
        }
        with open(app_dir / "config.json", "w") as f:
            json.dump(config, f)
        
        yield app_dir


@pytest.fixture
def state_manager(temp_app_dir):
    """Create a StateManager instance for testing."""
    return StateManager(temp_app_dir)


# === Basic state management tests ===
# Test core getter/setter functionality.


class TestStateManagerBasics:
    """Test basic state management operations."""
    
    def test_initial_state(self, state_manager):
        """Test initial state values are False."""
        assert state_manager.is_monitoring is False
        assert state_manager.is_protected_mode is False
        assert state_manager.heartbeat_fresh is False
        assert state_manager.monitor_process_alive is False
    
    def test_set_monitoring(self, state_manager):
        """Test setting monitoring state."""
        state_manager.set_monitoring(True)
        assert state_manager.is_monitoring is True
        
        state_manager.set_monitoring(False)
        assert state_manager.is_monitoring is False
    
    def test_set_protected_mode(self, state_manager):
        """Test setting protected mode state."""
        expiry = datetime.now(UTC) + timedelta(days=7)
        state_manager.set_protected_mode(True, expiry)
        
        assert state_manager.is_protected_mode is True
        assert state_manager.protected_mode_expiry == expiry
        
        state_manager.set_protected_mode(False)
        assert state_manager.is_protected_mode is False
    
    def test_set_heartbeat_fresh(self, state_manager):
        """Test setting heartbeat freshness."""
        state_manager.set_heartbeat_fresh(True)
        assert state_manager.heartbeat_fresh is True
        
        state_manager.set_heartbeat_fresh(False)
        assert state_manager.heartbeat_fresh is False
    
    def test_update_config(self, state_manager):
        """Test updating stored configuration."""
        new_config = {"check_interval": 60, "enabled": True}
        state_manager.update_config(new_config)
        
        config = state_manager.config
        assert config["check_interval"] == 60
        assert config["enabled"] is True
    
    def test_config_returns_copy(self, state_manager):
        """Test that config property returns a copy."""
        config1 = state_manager.config
        config1["test_key"] = "test_value"
        
        config2 = state_manager.config
        assert "test_key" not in config2


# === Observer pattern tests ===
# Test listener registration and notification.


class TestObserverPattern:
    """Test Observer pattern implementation."""
    
    def test_add_listener(self, state_manager):
        """Test adding a listener."""
        callback = MagicMock()
        state_manager.add_listener(StateEvent.MONITORING_CHANGED, callback)
        
        state_manager.set_monitoring(True)
        callback.assert_called_once()
    
    def test_remove_listener(self, state_manager):
        """Test removing a listener."""
        callback = MagicMock()
        state_manager.add_listener(StateEvent.MONITORING_CHANGED, callback)
        state_manager.remove_listener(StateEvent.MONITORING_CHANGED, callback)
        
        state_manager.set_monitoring(True)
        callback.assert_not_called()
    
    def test_multiple_listeners(self, state_manager):
        """Test multiple listeners for same event."""
        callback1 = MagicMock()
        callback2 = MagicMock()
        
        state_manager.add_listener(StateEvent.MONITORING_CHANGED, callback1)
        state_manager.add_listener(StateEvent.MONITORING_CHANGED, callback2)
        
        state_manager.set_monitoring(True)
        
        callback1.assert_called_once()
        callback2.assert_called_once()
    
    def test_listener_receives_state_data(self, state_manager):
        """Test that listener receives state snapshot."""
        received_data = {}
        
        def callback(event, data):
            received_data.update(data)
        
        state_manager.add_listener(StateEvent.MONITORING_CHANGED, callback)
        state_manager.set_monitoring(True)
        
        assert "is_monitoring" in received_data
        assert received_data["is_monitoring"] is True
    
    def test_no_notification_when_value_unchanged(self, state_manager):
        """Test that listener is not called when value doesn't change."""
        callback = MagicMock()
        state_manager.add_listener(StateEvent.MONITORING_CHANGED, callback)
        
        # Set to True (should notify)
        state_manager.set_monitoring(True)
        assert callback.call_count == 1
        
        # Set to True again (should not notify)
        state_manager.set_monitoring(True)
        assert callback.call_count == 1
    
    def test_listener_error_does_not_break_others(self, state_manager):
        """Test that one listener error doesn't prevent other listeners."""
        def bad_callback(event, data):
            raise ValueError("Test error")
        
        good_callback = MagicMock()
        
        state_manager.add_listener(StateEvent.MONITORING_CHANGED, bad_callback)
        state_manager.add_listener(StateEvent.MONITORING_CHANGED, good_callback)
        
        # Should not raise and should call good callback
        state_manager.set_monitoring(True)
        good_callback.assert_called_once()
    
    def test_protected_mode_notification(self, state_manager):
        """Test protected mode change notification."""
        callback = MagicMock()
        state_manager.add_listener(StateEvent.PROTECTED_MODE_CHANGED, callback)
        
        expiry = datetime.now(UTC) + timedelta(days=7)
        state_manager.set_protected_mode(True, expiry)
        
        callback.assert_called_once()
        args = callback.call_args
        event, data = args[0]
        assert event == StateEvent.PROTECTED_MODE_CHANGED
        assert data["is_protected_mode"] is True


# === State synchronization tests ===
# Test syncing state from files and processes.


class TestStateSynchronization:
    """Test state synchronization from external sources."""
    
    def test_sync_config_from_file(self, temp_app_dir, state_manager):
        """Test syncing configuration from file."""
        # Modify config file
        new_config = {"check_interval": 120, "enabled": True}
        with open(temp_app_dir / "config.json", "w") as f:
            json.dump(new_config, f)
        
        state_manager.sync_monitoring_from_config()
        
        config = state_manager.config
        assert config["check_interval"] == 120
    
    def test_sync_heartbeat_fresh(self, temp_app_dir, state_manager):
        """Test heartbeat freshness detection."""
        # Create fresh heartbeat
        heartbeat = {
            "status": "running",
            "pid": os.getpid(),
            "timestamp": datetime.now(UTC).isoformat(),
        }
        with open(temp_app_dir / "monitor_heartbeat.json", "w") as f:
            json.dump(heartbeat, f)
        
        # Update config for TTL calculation
        state_manager.update_config({"check_interval": 30, "heartbeat_ttl_seconds": 70})
        
        state_manager.sync_heartbeat_state()
        
        assert state_manager.heartbeat_fresh is True
    
    def test_sync_heartbeat_stale(self, temp_app_dir, state_manager):
        """Test stale heartbeat detection."""
        # Create old heartbeat
        old_time = datetime.now(UTC) - timedelta(minutes=10)
        heartbeat = {
            "status": "running",
            "pid": os.getpid(),
            "timestamp": old_time.isoformat(),
        }
        with open(temp_app_dir / "monitor_heartbeat.json", "w") as f:
            json.dump(heartbeat, f)
        
        state_manager.update_config({"check_interval": 30, "heartbeat_ttl_seconds": 70})
        state_manager.sync_heartbeat_state()
        
        assert state_manager.heartbeat_fresh is False
    
    def test_sync_heartbeat_missing(self, state_manager):
        """Test heartbeat sync when file is missing."""
        state_manager.sync_heartbeat_state()
        assert state_manager.heartbeat_fresh is False
    
    def test_sync_protected_mode_with_security_manager(self, state_manager):
        """Test protected mode sync with security manager."""
        mock_security = MagicMock()
        mock_security.is_protected_mode_active.return_value = True
        mock_security.get_protected_mode_expiry.return_value = datetime.now(UTC) + timedelta(days=5)
        
        state_manager.set_security_manager(mock_security)
        state_manager.sync_protected_mode_state()
        
        assert state_manager.is_protected_mode is True
    
    def test_sync_all_state(self, temp_app_dir, state_manager):
        """Test syncing all state at once."""
        # Setup config
        config = {"check_interval": 45, "enabled": True, "heartbeat_ttl_seconds": 100}
        with open(temp_app_dir / "config.json", "w") as f:
            json.dump(config, f)
        
        # Setup heartbeat
        heartbeat = {
            "status": "running",
            "pid": 99999,  # Non-existent PID
            "timestamp": datetime.now(UTC).isoformat(),
        }
        with open(temp_app_dir / "monitor_heartbeat.json", "w") as f:
            json.dump(heartbeat, f)
        
        state_manager.sync_all_state()
        
        assert state_manager.config["check_interval"] == 45


# === Monitoring state detection tests ===
# Test detecting actual monitoring state on startup.


class TestMonitoringStateDetection:
    """Test actual monitoring state detection."""
    
    def test_detect_monitoring_disabled_in_config(self, temp_app_dir, state_manager):
        """Test detection when config says disabled."""
        config = {"enabled": False}
        with open(temp_app_dir / "config.json", "w") as f:
            json.dump(config, f)
        
        result = state_manager.detect_actual_monitoring_state()
        
        assert result is False
    
    def test_detect_monitoring_no_heartbeat(self, temp_app_dir, state_manager):
        """Test detection when no heartbeat file exists."""
        config = {"enabled": True}
        with open(temp_app_dir / "config.json", "w") as f:
            json.dump(config, f)
        
        # Remove heartbeat if exists
        heartbeat_path = temp_app_dir / "monitor_heartbeat.json"
        if heartbeat_path.exists():
            heartbeat_path.unlink()
        
        result = state_manager.detect_actual_monitoring_state()
        
        assert result is False
    
    def test_detect_monitoring_stale_heartbeat(self, temp_app_dir, state_manager):
        """Test detection with stale heartbeat."""
        config = {"enabled": True, "check_interval": 30, "heartbeat_ttl_seconds": 70}
        with open(temp_app_dir / "config.json", "w") as f:
            json.dump(config, f)
        
        old_time = datetime.now(UTC) - timedelta(minutes=10)
        heartbeat = {"pid": os.getpid(), "timestamp": old_time.isoformat()}
        with open(temp_app_dir / "monitor_heartbeat.json", "w") as f:
            json.dump(heartbeat, f)
        
        result = state_manager.detect_actual_monitoring_state()
        
        assert result is False
    
    def test_get_running_monitor_pid_no_heartbeat(self, state_manager):
        """Test getting monitor PID when no heartbeat."""
        result = state_manager.get_running_monitor_pid()
        assert result is None
    
    def test_get_running_monitor_pid_dead_process(self, temp_app_dir, state_manager):
        """Test getting monitor PID when process is dead."""
        heartbeat = {"pid": 99999, "timestamp": datetime.now(UTC).isoformat()}
        with open(temp_app_dir / "monitor_heartbeat.json", "w") as f:
            json.dump(heartbeat, f)
        
        result = state_manager.get_running_monitor_pid()
        
        # Should return None because PID 99999 doesn't exist
        assert result is None


# === Thread safety tests ===
# Test that state operations are thread-safe.


class TestThreadSafety:
    """Test thread safety of state operations."""
    
    def test_concurrent_state_updates(self, state_manager):
        """Test concurrent state updates don't cause race conditions."""
        errors = []
        
        def toggle_monitoring():
            try:
                for _ in range(100):
                    state_manager.set_monitoring(True)
                    state_manager.set_monitoring(False)
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=toggle_monitoring) for _ in range(5)]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0
    
    def test_concurrent_listener_notifications(self, state_manager):
        """Test concurrent listener notifications."""
        call_count = [0]
        lock = threading.Lock()
        
        def callback(event, data):
            with lock:
                call_count[0] += 1
        
        state_manager.add_listener(StateEvent.MONITORING_CHANGED, callback)
        
        def toggle():
            for _ in range(10):
                state_manager.set_monitoring(True)
                state_manager.set_monitoring(False)
        
        threads = [threading.Thread(target=toggle) for _ in range(3)]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Should have some notifications (exact count depends on timing)
        assert call_count[0] > 0


# === Factory function tests ===
# Test create_state_manager helper.


class TestFactoryFunction:
    """Test create_state_manager factory function."""
    
    def test_create_state_manager_basic(self, temp_app_dir):
        """Test basic state manager creation."""
        state_mgr = create_state_manager(temp_app_dir)
        
        assert state_mgr is not None
        assert state_mgr.app_dir == temp_app_dir
    
    def test_create_state_manager_with_security(self, temp_app_dir):
        """Test state manager creation with security manager."""
        mock_security = MagicMock()
        mock_security.is_protected_mode_active.return_value = False
        mock_security.get_protected_mode_expiry.return_value = None
        
        state_mgr = create_state_manager(temp_app_dir, mock_security)
        
        assert state_mgr._security_manager == mock_security
    
    def test_create_state_manager_syncs_config(self, temp_app_dir):
        """Test that factory syncs config on creation."""
        config = {"check_interval": 99}
        with open(temp_app_dir / "config.json", "w") as f:
            json.dump(config, f)
        
        state_mgr = create_state_manager(temp_app_dir)
        
        assert state_mgr.config["check_interval"] == 99


# === Edge cases ===
# Test edge cases and error handling.


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_heartbeat_without_timestamp(self, temp_app_dir, state_manager):
        """Test handling heartbeat without timestamp."""
        heartbeat = {"pid": os.getpid()}  # No timestamp
        with open(temp_app_dir / "monitor_heartbeat.json", "w") as f:
            json.dump(heartbeat, f)
        
        state_manager.sync_heartbeat_state()
        
        assert state_manager.heartbeat_fresh is False
    
    def test_invalid_heartbeat_json(self, temp_app_dir, state_manager):
        """Test handling invalid heartbeat JSON."""
        with open(temp_app_dir / "monitor_heartbeat.json", "w") as f:
            f.write("invalid json {{{")
        
        state_manager.sync_heartbeat_state()
        
        assert state_manager.heartbeat_fresh is False
    
    def test_sync_protected_mode_without_security_manager(self, state_manager):
        """Test protected mode sync without security manager set."""
        # Should not raise
        state_manager.sync_protected_mode_state()
        
        assert state_manager.is_protected_mode is False
    
    def test_notify_disabled(self, state_manager):
        """Test that notify=False skips listeners."""
        callback = MagicMock()
        state_manager.add_listener(StateEvent.MONITORING_CHANGED, callback)
        
        state_manager.set_monitoring(True, notify=False)
        
        callback.assert_not_called()
        assert state_manager.is_monitoring is True
