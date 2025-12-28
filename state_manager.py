"""
Centralized state management for App Blocker.

This module provides a single source of truth for application state
across all components (GUI, system tray, monitor process). Uses Observer
pattern to notify listeners when state changes.

WHY THIS EXISTS:
- GUI, system tray, and monitor process need synchronized state
- Previously state was scattered across local variables, config files, and heartbeat
- Observer pattern allows automatic UI updates when state changes
- Prevents mismatch between what GUI shows and actual application state
"""

import json
import threading
from datetime import datetime, UTC
from pathlib import Path
from typing import Optional, Callable, Dict, Any, Set
from enum import Enum, auto
import psutil


# === State event types ===
# Defines all possible state changes that can be observed.

class StateEvent(Enum):
    """
    Events that can trigger state change notifications.
    
    WHY: Typed events allow listeners to subscribe to specific changes
    instead of receiving all notifications.
    """
    MONITORING_CHANGED = auto()      # is_monitoring state changed
    PROTECTED_MODE_CHANGED = auto()  # protected mode activated/deactivated/expired
    CONFIG_CHANGED = auto()          # configuration was reloaded
    HEARTBEAT_STATUS_CHANGED = auto() # heartbeat freshness changed
    MONITOR_HEALTH_CHANGED = auto()  # monitor process health status changed


# === StateManager class ===
# Central state store with observer notification system.

class StateManager:
    """
    Centralized state management with Observer pattern.
    
    WHY THIS CLASS EXISTS:
    - Single source of truth for application state
    - Automatic notification to all UI components when state changes
    - Thread-safe state access and modification
    - Eliminates state mismatch between GUI and tray
    
    USAGE:
        state_mgr = StateManager(app_dir)
        state_mgr.add_listener(StateEvent.MONITORING_CHANGED, on_monitoring_change)
        state_mgr.set_monitoring(True)  # triggers notification
    """
    
    def __init__(self, app_dir: Path):
        self.app_dir = Path(app_dir)
        self.config_path = self.app_dir / "config.json"
        self.heartbeat_path = self.app_dir / "monitor_heartbeat.json"
        
        # State storage - protected by lock for thread safety
        self._lock = threading.RLock()
        self._is_monitoring: bool = False
        self._is_protected_mode: bool = False
        self._protected_mode_expiry: Optional[datetime] = None
        self._heartbeat_fresh: bool = False
        self._monitor_process_alive: bool = False
        self._config: Dict[str, Any] = {}
        
        # Observer pattern: event -> list of callbacks
        self._listeners: Dict[StateEvent, Set[Callable]] = {
            event: set() for event in StateEvent
        }
        
        # Reference to security manager (set externally)
        self._security_manager = None
        
        # Reference to monitoring process (set externally)
        self._monitoring_process = None
    
    # --- Observer pattern methods ---
    
    def add_listener(self, event: StateEvent, callback: Callable):
        """
        Register a callback for a specific state event.
        
        WHY: Allows UI components to react to state changes automatically
        without polling or manual refresh calls.
        
        Args:
            event: The type of state change to listen for
            callback: Function to call when event occurs. Receives (event, state_data) args.
        """
        with self._lock:
            self._listeners[event].add(callback)
    
    def remove_listener(self, event: StateEvent, callback: Callable):
        """Remove a previously registered callback."""
        with self._lock:
            self._listeners[event].discard(callback)
    
    def _notify_listeners(self, event: StateEvent, data: Optional[Dict] = None):
        """
        Notify all registered listeners of a state change.
        
        WHY: Decouples state changes from UI updates.
        Listeners handle their own update logic.
        
        Note: Callbacks are called outside lock to prevent deadlocks.
        """
        with self._lock:
            callbacks = list(self._listeners[event])
        
        state_data = data or self._get_state_snapshot()
        for callback in callbacks:
            try:
                callback(event, state_data)
            except Exception as e:
                # Don't let one listener failure break others
                print(f"StateManager: listener error for {event}: {e}")
    
    def _get_state_snapshot(self) -> Dict[str, Any]:
        """Get current state as dictionary for listeners."""
        with self._lock:
            return {
                "is_monitoring": self._is_monitoring,
                "is_protected_mode": self._is_protected_mode,
                "protected_mode_expiry": self._protected_mode_expiry,
                "heartbeat_fresh": self._heartbeat_fresh,
                "monitor_process_alive": self._monitor_process_alive,
            }
    
    # --- State property accessors ---
    
    @property
    def is_monitoring(self) -> bool:
        """Get current monitoring state."""
        with self._lock:
            return self._is_monitoring
    
    @property
    def is_protected_mode(self) -> bool:
        """Get current protected mode state."""
        with self._lock:
            return self._is_protected_mode
    
    @property
    def protected_mode_expiry(self) -> Optional[datetime]:
        """Get protected mode expiry datetime."""
        with self._lock:
            return self._protected_mode_expiry
    
    @property
    def heartbeat_fresh(self) -> bool:
        """Get heartbeat freshness status."""
        with self._lock:
            return self._heartbeat_fresh
    
    @property
    def monitor_process_alive(self) -> bool:
        """Get monitor process status."""
        with self._lock:
            return self._monitor_process_alive
    
    @property
    def config(self) -> Dict[str, Any]:
        """Get current configuration (copy)."""
        with self._lock:
            return self._config.copy()
    
    # --- State setters with notification ---
    
    def set_monitoring(self, value: bool, notify: bool = True):
        """
        Set monitoring state and optionally notify listeners.
        
        WHY: Central point for all monitoring state changes.
        Ensures UI is always updated when state changes.
        """
        changed = False
        with self._lock:
            if self._is_monitoring != value:
                self._is_monitoring = value
                changed = True
        
        if changed and notify:
            self._notify_listeners(StateEvent.MONITORING_CHANGED)
    
    def set_protected_mode(self, active: bool, expiry: Optional[datetime] = None, notify: bool = True):
        """
        Set protected mode state and optionally notify listeners.
        
        WHY: Central point for protected mode state changes.
        Tray menu needs to update when protected mode changes.
        """
        changed = False
        with self._lock:
            if self._is_protected_mode != active or self._protected_mode_expiry != expiry:
                self._is_protected_mode = active
                self._protected_mode_expiry = expiry
                changed = True
        
        if changed and notify:
            self._notify_listeners(StateEvent.PROTECTED_MODE_CHANGED)
    
    def set_heartbeat_fresh(self, value: bool, notify: bool = True):
        """Set heartbeat freshness status."""
        changed = False
        with self._lock:
            if self._heartbeat_fresh != value:
                self._heartbeat_fresh = value
                changed = True
        
        if changed and notify:
            self._notify_listeners(StateEvent.HEARTBEAT_STATUS_CHANGED)
    
    def set_monitor_process_alive(self, value: bool, notify: bool = True):
        """Set monitor process alive status."""
        changed = False
        with self._lock:
            if self._monitor_process_alive != value:
                self._monitor_process_alive = value
                changed = True
        
        if changed and notify:
            self._notify_listeners(StateEvent.MONITOR_HEALTH_CHANGED)
    
    def update_config(self, config: Dict[str, Any], notify: bool = True):
        """Update stored configuration."""
        with self._lock:
            self._config = config.copy()
        
        if notify:
            self._notify_listeners(StateEvent.CONFIG_CHANGED)
    
    # --- External reference setters ---
    
    def set_security_manager(self, security_manager):
        """Set reference to security manager for protected mode checks."""
        self._security_manager = security_manager
    
    def set_monitoring_process(self, process):
        """Set reference to monitoring subprocess."""
        self._monitoring_process = process
    
    # === State synchronization methods ===
    # These methods read actual state from files/processes and update internal state.
    
    def sync_protected_mode_state(self):
        """
        Synchronize protected mode state from security manager.
        
        WHY: Protected mode can expire while app is running.
        This method checks current state and notifies if changed.
        """
        if not self._security_manager:
            return
        
        try:
            is_active = self._security_manager.is_protected_mode_active()
            expiry = self._security_manager.get_protected_mode_expiry()
            self.set_protected_mode(is_active, expiry)
        except Exception as e:
            print(f"StateManager: failed to sync protected mode: {e}")
    
    def sync_monitoring_from_config(self):
        """
        Synchronize monitoring state from config file.
        
        WHY: Config file is shared between GUI and monitor process.
        Reading it gives us ground truth for enabled state.
        """
        try:
            with open(self.config_path, "r") as f:
                config = json.load(f)
            
            self.update_config(config, notify=False)
            
            # Note: We don't auto-set is_monitoring from config.enabled
            # because we also need to verify the process is actually running
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"StateManager: failed to sync config: {e}")
    
    def sync_heartbeat_state(self):
        """
        Check heartbeat file freshness and update state.
        
        WHY: Heartbeat tells us if monitor process is actually working,
        not just if it was started.
        """
        try:
            heartbeat = self._read_heartbeat()
            if not heartbeat:
                self.set_heartbeat_fresh(False)
                return
            
            ts_str = heartbeat.get("timestamp")
            if not ts_str:
                self.set_heartbeat_fresh(False)
                return
            
            ts = datetime.fromisoformat(ts_str)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=UTC)
            
            ttl = self._compute_heartbeat_ttl()
            age = (datetime.now(UTC) - ts).total_seconds()
            
            self.set_heartbeat_fresh(age <= ttl)
        except Exception as e:
            print(f"StateManager: failed to sync heartbeat: {e}")
            self.set_heartbeat_fresh(False)
    
    def sync_monitor_process_state(self):
        """
        Check if monitor process is running and update state.
        
        WHY: Process can die unexpectedly. This gives us actual status.
        """
        if self._monitoring_process:
            alive = self._monitoring_process.poll() is None
            self.set_monitor_process_alive(alive)
        else:
            # Try to detect monitor process by checking heartbeat PID
            heartbeat = self._read_heartbeat()
            if heartbeat:
                pid = heartbeat.get("pid")
                if pid:
                    try:
                        proc = psutil.Process(pid)
                        alive = proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
                        self.set_monitor_process_alive(alive)
                        return
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
            self.set_monitor_process_alive(False)
    
    def sync_all_state(self):
        """
        Synchronize all state from external sources.
        
        WHY: Called periodically to ensure UI reflects reality.
        Order matters: config first, then process/heartbeat, then protected mode.
        """
        self.sync_monitoring_from_config()
        self.sync_monitor_process_state()
        self.sync_heartbeat_state()
        self.sync_protected_mode_state()
    
    # --- Helper methods ---
    
    def _read_heartbeat(self) -> Optional[Dict]:
        """Read heartbeat file and return contents."""
        try:
            with open(self.heartbeat_path, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            return None
        except Exception:
            return None
    
    def _compute_heartbeat_ttl(self) -> float:
        """Compute heartbeat TTL from config."""
        with self._lock:
            interval = self._config.get("check_interval", 30)
            return self._config.get("heartbeat_ttl_seconds", interval * 2 + 10)
    
    # === Monitoring state detection ===
    # Methods to detect actual monitoring state on startup.
    
    def detect_actual_monitoring_state(self) -> bool:
        """
        Detect if monitoring is actually running (not just what config says).
        
        WHY: On GUI startup, we need to know if monitor is already running
        (e.g., from autostart or previous session). This checks:
        1. Config says enabled
        2. Heartbeat is fresh
        3. Monitor process is alive (by PID from heartbeat)
        
        Returns True if monitoring appears to be active.
        """
        self.sync_monitoring_from_config()
        
        # Check config says enabled
        with self._lock:
            config_enabled = self._config.get("enabled", False)
        
        if not config_enabled:
            return False
        
        # Check heartbeat
        heartbeat = self._read_heartbeat()
        if not heartbeat:
            return False
        
        # Check heartbeat freshness
        ts_str = heartbeat.get("timestamp")
        if ts_str:
            try:
                ts = datetime.fromisoformat(ts_str)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=UTC)
                
                ttl = self._compute_heartbeat_ttl()
                age = (datetime.now(UTC) - ts).total_seconds()
                
                if age > ttl:
                    # Heartbeat is stale - monitoring not really active
                    return False
            except Exception:
                return False
        else:
            return False
        
        # Check process is alive
        pid = heartbeat.get("pid")
        if pid:
            try:
                proc = psutil.Process(pid)
                if proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        return False
    
    def get_running_monitor_pid(self) -> Optional[int]:
        """
        Get PID of running monitor process if any.
        
        WHY: GUI may need to attach to existing monitor process
        started by autostart instead of launching new one.
        """
        heartbeat = self._read_heartbeat()
        if not heartbeat:
            return None
        
        pid = heartbeat.get("pid")
        if not pid:
            return None
        
        try:
            proc = psutil.Process(pid)
            if proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE:
                return pid
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        
        return None


# === Factory function ===
# Provides convenient way to create configured StateManager.

def create_state_manager(app_dir: Path, security_manager=None) -> StateManager:
    """
    Create and initialize a StateManager instance.
    
    WHY: Encapsulates initialization logic and initial state sync.
    
    Args:
        app_dir: Application directory containing config files
        security_manager: Optional SecurityManager for protected mode checks
    
    Returns:
        Configured StateManager with initial state synced
    """
    state_mgr = StateManager(app_dir)
    
    if security_manager:
        state_mgr.set_security_manager(security_manager)
    
    # Perform initial state synchronization
    state_mgr.sync_all_state()
    
    return state_mgr
