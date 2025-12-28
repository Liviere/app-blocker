"""
Tests for notification_manager.py module.

WHY: Verify notification configuration parsing, deduplication logic,
and warning threshold calculations work correctly.
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from notification_manager import (
    NotificationManager,
    parse_warning_thresholds,
    validate_warning_thresholds,
)
from main import get_minutes_until_blocked_hours


# === Warning threshold parsing tests ===
# Test parsing of comma-separated minute values from config.


class TestParseWarningThresholds:
    """Tests for parse_warning_thresholds function."""
    
    def test_valid_single_value(self):
        """Single value should return single-item list."""
        result = parse_warning_thresholds("5")
        assert result == [5]
    
    def test_valid_multiple_values(self):
        """Multiple values should be sorted descending."""
        result = parse_warning_thresholds("3,5,1")
        assert result == [5, 3, 1]
    
    def test_values_with_spaces(self):
        """Whitespace should be trimmed."""
        result = parse_warning_thresholds(" 5 , 3 , 1 ")
        assert result == [5, 3, 1]
    
    def test_duplicates_removed(self):
        """Duplicate values should be removed."""
        result = parse_warning_thresholds("5,5,3,1,1")
        assert result == [5, 3, 1]
    
    def test_empty_string_returns_default(self):
        """Empty string should return default thresholds."""
        result = parse_warning_thresholds("")
        assert result == [5, 3, 1]
    
    def test_none_returns_default(self):
        """None should return default thresholds."""
        result = parse_warning_thresholds(None)
        assert result == [5, 3, 1]
    
    def test_invalid_values_skipped(self):
        """Non-numeric values should be skipped."""
        result = parse_warning_thresholds("5,abc,3,!@#,1")
        assert result == [5, 3, 1]
    
    def test_zero_and_negative_values_skipped(self):
        """Values < 1 should be skipped."""
        result = parse_warning_thresholds("5,0,3,-1,1")
        assert result == [5, 3, 1]
    
    def test_all_invalid_returns_default(self):
        """If all values invalid, return default."""
        result = parse_warning_thresholds("abc,xyz,!")
        assert result == [5, 3, 1]
    
    def test_one_minute_allowed(self):
        """Value of 1 should be allowed (for final warning)."""
        result = parse_warning_thresholds("1")
        assert result == [1]


# === Warning threshold validation tests ===
# Test validation for GUI input.


class TestValidateWarningThresholds:
    """Tests for validate_warning_thresholds function."""
    
    def test_valid_input(self):
        """Valid input should pass validation."""
        is_valid, error = validate_warning_thresholds("5,3,1")
        assert is_valid is True
        assert error == ""
    
    def test_empty_string_invalid(self):
        """Empty string should fail validation."""
        is_valid, error = validate_warning_thresholds("")
        assert is_valid is False
        assert "empty" in error.lower()
    
    def test_non_numeric_invalid(self):
        """Non-numeric values should fail validation."""
        is_valid, error = validate_warning_thresholds("5,abc,1")
        assert is_valid is False
        assert "abc" in error
    
    def test_zero_invalid(self):
        """Zero should fail validation."""
        is_valid, error = validate_warning_thresholds("5,0,1")
        assert is_valid is False
        assert "0" in error
    
    def test_negative_invalid(self):
        """Negative values should fail validation."""
        is_valid, error = validate_warning_thresholds("5,-1,1")
        assert is_valid is False
        assert "-1" in error
    
    def test_single_valid_value(self):
        """Single valid value should pass."""
        is_valid, error = validate_warning_thresholds("5")
        assert is_valid is True


# === NotificationManager deduplication tests ===
# Test that notifications are not sent repeatedly for same threshold.


class TestNotificationManagerDeduplication:
    """Tests for notification deduplication logic."""
    
    def test_notification_sent_once_per_threshold(self):
        """Same threshold should only trigger notification once."""
        manager = NotificationManager(Path("."))
        
        with patch.object(manager, '_play_notification_sound'):
            with patch('notification_manager.show_notification') as mock_notify:
                # 4.5 minutes remaining (270 seconds) - triggers 5-minute threshold
                manager.notify_dedicated_limit("app.exe", 270, [5, 3, 1])
                assert mock_notify.call_count == 1
                
                # 4 minutes remaining - still at 5-minute threshold, already sent
                manager.notify_dedicated_limit("app.exe", 240, [5, 3, 1])
                assert mock_notify.call_count == 1
    
    def test_different_apps_get_separate_notifications(self):
        """Different apps should each get their own notifications."""
        manager = NotificationManager(Path("."))
        
        with patch.object(manager, '_play_notification_sound'):
            with patch('notification_manager.show_notification') as mock_notify:
                manager.notify_dedicated_limit("app1.exe", 270, [5, 3, 1])
                manager.notify_dedicated_limit("app2.exe", 270, [5, 3, 1])
                
                assert mock_notify.call_count == 2
    
    def test_clear_notifications_for_app(self):
        """Clearing notifications should allow re-notification."""
        manager = NotificationManager(Path("."))
        
        with patch.object(manager, '_play_notification_sound'):
            with patch('notification_manager.show_notification') as mock_notify:
                manager.notify_dedicated_limit("app.exe", 270, [5, 3, 1])
                assert mock_notify.call_count == 1
                
                manager.clear_notifications_for_app("app.exe")
                
                manager.notify_dedicated_limit("app.exe", 270, [5, 3, 1])
                assert mock_notify.call_count == 2
    
    def test_day_change_resets_notifications(self):
        """Notifications should reset on new day."""
        manager = NotificationManager(Path("."))
        manager._current_day = "2025-01-01"  # Set to old day
        
        with patch.object(manager, '_play_notification_sound'):
            with patch('notification_manager.show_notification') as mock_notify:
                # Should reset and notify because "day changed"
                manager.notify_dedicated_limit("app.exe", 270, [5, 3, 1])
                assert mock_notify.call_count == 1
    
    def test_different_thresholds_notify_separately(self):
        """Different thresholds should each trigger their own notification."""
        manager = NotificationManager(Path("."))
        
        with patch.object(manager, '_play_notification_sound'):
            with patch('notification_manager.show_notification') as mock_notify:
                # First: 4 minutes remaining - triggers 5-minute threshold
                manager.notify_dedicated_limit("app.exe", 240, [5, 3, 1])
                assert mock_notify.call_count == 1
                
                # Later: 2 minutes remaining - triggers 3-minute threshold (new)
                manager.notify_dedicated_limit("app.exe", 120, [5, 3, 1])
                assert mock_notify.call_count == 2
                
                # Even later: 30 seconds remaining - triggers 1-minute threshold (new)
                manager.notify_dedicated_limit("app.exe", 30, [5, 3, 1])
                assert mock_notify.call_count == 3


# === Sound selection tests ===
# Test correct sound file is selected based on threshold.


class TestSoundSelection:
    """Tests for sound file selection logic."""
    
    def test_final_alarm_for_one_minute(self):
        """1-minute threshold should use final alarm."""
        manager = NotificationManager(Path("."))
        sound = manager._select_sound(1)
        assert "final_alarm" in sound.name
    
    def test_regular_alarm_for_other_thresholds(self):
        """Non-1-minute thresholds should use regular alarm."""
        manager = NotificationManager(Path("."))
        
        for threshold in [5, 3, 2, 10]:
            sound = manager._select_sound(threshold)
            assert "alarm.mp3" in sound.name
            assert "final" not in sound.name


# === Blocked hours approaching calculation tests ===
# Test calculation of minutes until blocked hours start.


class TestGetMinutesUntilBlockedHours:
    """Tests for get_minutes_until_blocked_hours function."""
    
    def test_empty_blocked_hours(self):
        """Empty list should return -1."""
        now = datetime(2025, 1, 1, 12, 0)
        minutes, start_time = get_minutes_until_blocked_hours(now, [])
        assert minutes == -1
        assert start_time == ""
    
    def test_currently_in_blocked_hours(self):
        """If currently blocked, return -1."""
        now = datetime(2025, 1, 1, 22, 0)  # 22:00
        blocked = [{"start": "21:00", "end": "23:00"}]
        
        minutes, start_time = get_minutes_until_blocked_hours(now, blocked)
        assert minutes == -1
    
    def test_same_day_upcoming_block(self):
        """Calculate minutes to upcoming block same day."""
        now = datetime(2025, 1, 1, 20, 0)  # 20:00
        blocked = [{"start": "21:00", "end": "23:00"}]
        
        minutes, start_time = get_minutes_until_blocked_hours(now, blocked)
        assert minutes == 60  # 1 hour until 21:00
        assert start_time == "21:00"
    
    def test_next_day_block(self):
        """Calculate minutes to block starting next day."""
        now = datetime(2025, 1, 1, 23, 30)  # 23:30
        blocked = [{"start": "09:00", "end": "17:00"}]
        
        minutes, start_time = get_minutes_until_blocked_hours(now, blocked)
        # 23:30 to midnight = 30 min, midnight to 09:00 = 540 min = 570 total
        assert minutes == 570
        assert start_time == "09:00"
    
    def test_multiple_blocked_ranges_nearest(self):
        """Should return the nearest upcoming block."""
        now = datetime(2025, 1, 1, 18, 0)  # 18:00
        blocked = [
            {"start": "21:00", "end": "23:00"},  # 3 hours away
            {"start": "19:00", "end": "20:00"},  # 1 hour away - nearest
        ]
        
        minutes, start_time = get_minutes_until_blocked_hours(now, blocked)
        assert minutes == 60  # 1 hour to 19:00
        assert start_time == "19:00"
    
    def test_overnight_block_handling(self):
        """Handle overnight ranges correctly."""
        now = datetime(2025, 1, 1, 12, 0)  # Noon
        blocked = [{"start": "23:00", "end": "02:00"}]  # Overnight block
        
        minutes, start_time = get_minutes_until_blocked_hours(now, blocked)
        assert minutes == 660  # 11 hours = 660 minutes to 23:00
        assert start_time == "23:00"
    
    def test_invalid_range_skipped(self):
        """Invalid ranges should be skipped."""
        now = datetime(2025, 1, 1, 12, 0)
        blocked = [
            {"start": "", "end": "17:00"},  # Invalid - empty start
            {"start": "21:00", "end": "23:00"},  # Valid
        ]
        
        minutes, start_time = get_minutes_until_blocked_hours(now, blocked)
        assert minutes == 540  # 9 hours to 21:00
        assert start_time == "21:00"


# === Notification triggering tests ===
# Test that notifications trigger at correct thresholds.


class TestNotificationTriggering:
    """Tests for notification triggering at thresholds."""
    
    def test_notification_at_exact_threshold(self):
        """Notification should trigger at exact threshold boundary."""
        manager = NotificationManager(Path("."))
        
        with patch.object(manager, '_play_notification_sound'):
            with patch('notification_manager.show_notification') as mock_notify:
                # 5 minutes remaining (300 seconds) with 5-minute threshold
                manager.notify_dedicated_limit("app.exe", 300, [5, 3, 1])
                assert mock_notify.call_count == 1
    
    def test_notification_below_threshold(self):
        """Notification should trigger when below threshold."""
        manager = NotificationManager(Path("."))
        
        with patch.object(manager, '_play_notification_sound'):
            with patch('notification_manager.show_notification') as mock_notify:
                # 4 minutes remaining (240 seconds) with 5-minute threshold
                manager.notify_dedicated_limit("app.exe", 240, [5, 3, 1])
                assert mock_notify.call_count == 1
    
    def test_no_notification_above_all_thresholds(self):
        """No notification when remaining time is above all thresholds."""
        manager = NotificationManager(Path("."))
        
        with patch.object(manager, '_play_notification_sound'):
            with patch('notification_manager.show_notification') as mock_notify:
                # 10 minutes remaining (600 seconds) with thresholds 5,3,1
                manager.notify_dedicated_limit("app.exe", 600, [5, 3, 1])
                assert mock_notify.call_count == 0
    
    def test_overall_limit_notification(self):
        """Overall limit should trigger notification."""
        manager = NotificationManager(Path("."))
        
        with patch.object(manager, '_play_notification_sound'):
            with patch('notification_manager.show_notification') as mock_notify:
                manager.notify_overall_limit(180, [5, 3, 1])
                assert mock_notify.call_count == 1
                assert "Overall" in str(mock_notify.call_args)
    
    def test_blocked_hours_notification(self):
        """Blocked hours approaching should trigger notification."""
        manager = NotificationManager(Path("."))
        
        with patch.object(manager, '_play_notification_sound'):
            with patch('notification_manager.show_notification') as mock_notify:
                manager.notify_blocked_hours_approaching(3, "21:00", [5, 3, 1])
                assert mock_notify.call_count == 1
                assert "Blocked" in str(mock_notify.call_args)


# === Final warning special handling tests ===
# Test 1-minute final warning gets special treatment.


class TestFinalWarning:
    """Tests for final warning (1-minute) special handling."""
    
    def test_final_warning_message_different(self):
        """Final warning should have distinct message."""
        manager = NotificationManager(Path("."))
        
        with patch.object(manager, '_play_notification_sound'):
            with patch('notification_manager.show_notification') as mock_notify:
                # 30 seconds remaining - only triggers 1-minute threshold
                # Use threshold list with only 1-minute warning
                manager.notify_dedicated_limit("app.exe", 30, [1])
                
                call_args = str(mock_notify.call_args)
                assert "FINAL" in call_args or "final" in call_args.lower()
    
    def test_final_warning_plays_special_sound(self):
        """Final warning should play final_alarm sound."""
        manager = NotificationManager(Path("."))
        
        with patch('notification_manager.show_notification'):
            with patch.object(manager, '_play_notification_sound') as mock_sound:
                # Only 1-minute threshold - triggers final alarm
                manager.notify_dedicated_limit("app.exe", 30, [1])
                
                mock_sound.assert_called_once_with(1)
    
    def test_regular_warning_before_final(self):
        """Regular warning at higher threshold should use regular message."""
        manager = NotificationManager(Path("."))
        
        with patch.object(manager, '_play_notification_sound') as mock_sound:
            with patch('notification_manager.show_notification') as mock_notify:
                # 4 minutes remaining - triggers 5-minute threshold
                manager.notify_dedicated_limit("app.exe", 240, [5, 3, 1])
                
                call_args = str(mock_notify.call_args)
                assert "FINAL" not in call_args
                mock_sound.assert_called_once_with(5)
