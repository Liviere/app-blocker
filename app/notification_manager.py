"""
Notification manager for App Blocker.

WHY: Provides system notifications and non-blocking sound playback
to warn users before applications are forcefully closed.
"""

import pygame
import threading
from pathlib import Path
from typing import Optional
from datetime import datetime
from win10toast import ToastNotifier
from .logger_utils import get_logger
from .common import get_app_directory

# === Sound playback infrastructure ===
# Non-blocking sound playback using threading and pygame/winsound fallback.


def _play_sound_blocking(sound_path: Path) -> None:
    """
    Play sound file (blocking call - meant to run in thread).
    
    WHY: Actual playback implementation. Uses pygame if available,
    falls back to winsound for WAV or playsound for MP3.
    """
    if not sound_path.exists():
        return
    
    pygame.mixer.init()
    pygame.mixer.music.load(str(sound_path))
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        pygame.time.wait(100)


def play_sound_async(sound_path: Path) -> None:
    """
    Play sound file asynchronously (non-blocking).
    
    WHY: Main monitor loop must not wait for sound to finish.
    Spawns daemon thread so it won't prevent process exit.
    """
    if not sound_path.exists():
        logger = get_logger("app_blocker.monitor", get_app_directory(), True)
        logger.warning(f"Sound file not found: {sound_path}")
        return
    
    thread = threading.Thread(target=_play_sound_blocking, args=(sound_path,), daemon=True)
    thread.start()


# ===  Windows toast notifications ===
# System notifications using win10toast or fallback to winotify.


def _show_toast_notification(title: str, message: str, duration: int = 5) -> None:
    """
    Show Windows toast notification.
    
    WHY: Visual alert to user even when app is minimized/in background.
    Tries multiple libraries for compatibility.
    """
    toaster = ToastNotifier()
    toaster.show_toast(
        title,
        message,
        duration=duration,
        threaded=True  # Non-blocking
    )


def show_notification(title: str, message: str, duration: int = 5) -> None:
    """
    Show system notification (non-blocking wrapper).
    
    WHY: Public API for showing notifications. Ensures non-blocking behavior.
    """
    thread = threading.Thread(
        target=_show_toast_notification,
        args=(title, message, duration),
        daemon=True
    )
    thread.start()


# === Notification manager class ===
# Orchestrates notifications with deduplication and sound selection.


class NotificationManager:
    """
    Manages warning notifications for App Blocker.
    
    WHY: Centralizes notification logic, prevents duplicate notifications
    for the same warning threshold, and handles sound file selection.
    """
    
    def __init__(self, app_dir: Optional[Path] = None):
        """
        Initialize notification manager.
        
        WHY: Set up paths and tracking state.
        """
        self.app_dir = app_dir or get_app_directory()
        self.assets_dir = self.app_dir / "assets"
        
        # Sound file paths
        self.alarm_sound = self.assets_dir / "alarm.mp3"
        self.final_alarm_sound = self.assets_dir / "final_alarm.mp3"
        
        # Track which notifications were already sent this session
        # Key: (notification_type, app_name_or_context, threshold_minutes)
        # This prevents repeated notifications for the same threshold
        self._sent_notifications: set = set()
        
        # Track the current day to reset notifications at midnight
        self._current_day: str = datetime.now().strftime("%Y-%m-%d")

        self.logger = get_logger("app_blocker.monitor", self.app_dir, True)
    
    def _reset_if_new_day(self) -> None:
        """
        Reset sent notifications tracker on day change.
        
        WHY: Users should get fresh notifications each day.
        """
        today = datetime.now().strftime("%Y-%m-%d")
        if today != self._current_day:
            self._sent_notifications.clear()
            self._current_day = today
    
    def _make_notification_key(
        self,
        notification_type: str,
        context: str,
        threshold_minutes: int
    ) -> tuple:
        """
        Create unique key for deduplication.
        
        WHY: Ensures we don't spam the same notification repeatedly.
        """
        return (notification_type, context, threshold_minutes)
    
    def _was_notification_sent(self, key: tuple) -> bool:
        """Check if notification was already sent."""
        return key in self._sent_notifications
    
    def _mark_notification_sent(self, key: tuple) -> None:
        """Mark notification as sent."""
        self._sent_notifications.add(key)
    
    def _select_sound(self, threshold_minutes: int) -> Path:
        """
        Select appropriate sound file based on threshold.
        
        WHY: 1-minute warning gets special "final" alarm sound.
        """
        if threshold_minutes == 1:
            return self.final_alarm_sound
        return self.alarm_sound
    
    def _play_notification_sound(self, threshold_minutes: int) -> None:
        """
        Play appropriate alarm sound.
        
        WHY: Audio alert even if user doesn't see visual notification.
        """
        sound_path = self._select_sound(threshold_minutes)
        play_sound_async(sound_path)
    
    # === Public notification methods ===
    # Methods for each notification scenario: dedicated limit, overall limit, blocked hours.
    
    def notify_dedicated_limit(
        self,
        app_name: str,
        remaining_seconds: int,
        warning_thresholds: list[int]
    ) -> None:
        """
        Check and send notification for dedicated app time limit.
        
        WHY: Warn user when specific app is approaching its time limit.
        warning_thresholds: list of minutes before limit (e.g., [5, 3, 1])
        """
        self._reset_if_new_day()
        
        remaining_minutes = remaining_seconds / 60
        
        for threshold in warning_thresholds:
            if remaining_minutes <= threshold:
                key = self._make_notification_key("dedicated", app_name, threshold)
                
                if not self._was_notification_sent(key):
                    self._mark_notification_sent(key)

                    self.logger.info(
                        f"Sending dedicated limit notification for {app_name}: "
                        f"threshold={threshold}, remaining_minutes={remaining_minutes}"
                    )
                    
                    if threshold == 1:
                        title = f"⚠️ FINAL WARNING: {app_name}"
                        message = f"{app_name} will be closed in less than 1 minute!"
                    else:
                        title = f"⏰ Time Warning: {app_name}"
                        message = f"{app_name} will be closed in {threshold} minutes"
                    
                    show_notification(title, message)
                    try:
                        self._play_notification_sound(threshold)
                    except Exception as e:
                        self.logger.error(f"Failed to play notification sound: {e}")
                    # Only trigger one notification per check (the most urgent one)
                    break
    
    def notify_overall_limit(
        self,
        remaining_seconds: int,
        warning_thresholds: list[int]
    ) -> None:
        """
        Check and send notification for overall time limit.
        
        WHY: Warn user when total usage across all apps approaches overall limit.
        """
        self._reset_if_new_day()
        
        remaining_minutes = remaining_seconds / 60
        
        for threshold in warning_thresholds:
            if remaining_minutes <= threshold:
                key = self._make_notification_key("overall", "all_apps", threshold)
                
                if not self._was_notification_sent(key):
                    self._mark_notification_sent(key)

                    self.logger.info(
                        f"Sending overall limit notification: "
                        f"threshold={threshold}, remaining_minutes={remaining_minutes}"
                    )
                    
                    if threshold == 1:
                        title = "⚠️ FINAL WARNING: Overall Limit"
                        message = "All monitored apps will be closed in less than 1 minute!"
                    else:
                        title = "⏰ Overall Time Warning"
                        message = f"All monitored apps will be closed in {threshold} minutes"
                    
                    show_notification(title, message)
                    try:
                        self._play_notification_sound(threshold)
                    except Exception as e:
                        self.logger.error(f"Failed to play notification sound: {e}")
                    break
    
    def notify_blocked_hours_approaching(
        self,
        minutes_until_block: int,
        blocked_start_time: str,
        warning_thresholds: list[int]
    ) -> None:
        """
        Check and send notification for approaching blocked hours.
        
        WHY: Warn user before blocked hours period begins.
        """
        self._reset_if_new_day()
        
        for threshold in warning_thresholds:
            if minutes_until_block <= threshold:
                key = self._make_notification_key("blocked_hours", blocked_start_time, threshold)
                
                if not self._was_notification_sent(key):
                    self._mark_notification_sent(key)

                    self.logger.info(
                        f"Sending blocked hours notification: "
                        f"threshold={threshold}, minutes_until_block={minutes_until_block}"
                    )
                    
                    if threshold == 1:
                        title = "⚠️ FINAL WARNING: Blocked Hours"
                        message = f"Blocked hours start in less than 1 minute ({blocked_start_time})!"
                    else:
                        title = "⏰ Blocked Hours Warning"
                        message = f"Blocked hours start in {threshold} minutes ({blocked_start_time})"
                    
                    show_notification(title, message)
                    try:
                        self._play_notification_sound(threshold)
                    except Exception as e:
                        self.logger.error(f"Failed to play notification sound: {e}")
                    break
    
    def clear_notifications_for_app(self, app_name: str) -> None:
        """
        Clear sent notification tracking for specific app.
        
        WHY: When app is closed/removed, reset its notification state.
        """
        keys_to_remove = [
            key for key in self._sent_notifications
            if key[1] == app_name
        ]
        for key in keys_to_remove:
            self._sent_notifications.discard(key)


# === Configuration parsing helpers ===
# Functions to parse and validate notification configuration.


def parse_warning_thresholds(config_value: str) -> list[int]:
    """
    Parse comma-separated warning thresholds string to sorted list.
    
    WHY: Config stores thresholds as string "5,3,1" for easy editing.
    Returns sorted descending list so most urgent threshold is checked last.
    
    Validates that all values are positive integers.
    Value of 1 is allowed (for final warning) but values <= 0 are rejected.
    """
    if not config_value or not isinstance(config_value, str):
        return [5, 3, 1]  # Default thresholds
    
    thresholds = []
    for part in config_value.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            value = int(part)
            if value >= 1:  # Must be at least 1 minute
                thresholds.append(value)
        except ValueError:
            continue
    
    if not thresholds:
        return [5, 3, 1]  # Default if parsing failed
    
    # Sort descending so we check largest threshold first
    return sorted(set(thresholds), reverse=True)


def validate_warning_thresholds(thresholds_str: str) -> tuple[bool, str]:
    """
    Validate warning thresholds configuration string.
    
    WHY: GUI needs to validate user input before saving.
    Returns (is_valid, error_message).
    """
    if not thresholds_str or not thresholds_str.strip():
        return False, "Warning thresholds cannot be empty"
    
    parts = thresholds_str.split(",")
    values = []
    
    for part in parts:
        part = part.strip()
        if not part:
            continue
        
        try:
            value = int(part)
        except ValueError:
            return False, f"Invalid value: '{part}' is not a number"
        
        if value < 1:
            return False, f"Invalid value: {value} must be at least 1"
        
        values.append(value)
    
    if not values:
        return False, "At least one warning threshold is required"
    
    return True, ""
