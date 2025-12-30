"""
Tests for blocked hours functionality.

WHY: Ensures time range validation, overlap detection, and monitor enforcement work correctly.
"""
import unittest
import sys
from pathlib import Path

# Add parent directory to path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from time_utils import (
    parse_time_str,
    time_to_minutes,
    is_time_in_range,
    validate_time_format,
    ranges_overlap,
    validate_blocked_hours,
    is_within_blocked_hours,
)


# === Tests for blocked hours logic ===
# Comprehensive tests for time parsing, range checking, and validation.


class TestTimeParsingMain(unittest.TestCase):
    """Test time parsing functions in main.py"""

    def test_parse_time_str_valid(self):
        """Test parsing valid time strings"""
        self.assertEqual(parse_time_str("00:00"), (0, 0))
        self.assertEqual(parse_time_str("12:30"), (12, 30))
        self.assertEqual(parse_time_str("23:59"), (23, 59))
        self.assertEqual(parse_time_str("09:05"), (9, 5))

    def test_parse_time_str_with_whitespace(self):
        """Test parsing time strings with whitespace"""
        self.assertEqual(parse_time_str("  12:30  "), (12, 30))

    def test_time_to_minutes(self):
        """Test conversion to minutes since midnight"""
        self.assertEqual(time_to_minutes(0, 0), 0)
        self.assertEqual(time_to_minutes(1, 0), 60)
        self.assertEqual(time_to_minutes(12, 30), 750)
        self.assertEqual(time_to_minutes(23, 59), 1439)


class TestTimeRangeChecking(unittest.TestCase):
    """Test time range checking logic"""

    def test_is_time_in_range_normal(self):
        """Test normal (same-day) time ranges"""
        # 09:00 - 17:00
        start = time_to_minutes(9, 0)
        end = time_to_minutes(17, 0)

        # Inside range
        self.assertTrue(is_time_in_range(time_to_minutes(9, 0), start, end))
        self.assertTrue(is_time_in_range(time_to_minutes(12, 0), start, end))
        self.assertTrue(is_time_in_range(time_to_minutes(16, 59), start, end))

        # Outside range
        self.assertFalse(is_time_in_range(time_to_minutes(8, 59), start, end))
        self.assertFalse(is_time_in_range(time_to_minutes(17, 0), start, end))
        self.assertFalse(is_time_in_range(time_to_minutes(23, 0), start, end))

    def test_is_time_in_range_overnight(self):
        """Test overnight time ranges (crossing midnight)"""
        # 23:00 - 06:00 (overnight)
        start = time_to_minutes(23, 0)
        end = time_to_minutes(6, 0)

        # Inside range (evening side)
        self.assertTrue(is_time_in_range(time_to_minutes(23, 0), start, end))
        self.assertTrue(is_time_in_range(time_to_minutes(23, 30), start, end))

        # Inside range (morning side)
        self.assertTrue(is_time_in_range(time_to_minutes(0, 0), start, end))
        self.assertTrue(is_time_in_range(time_to_minutes(3, 0), start, end))
        self.assertTrue(is_time_in_range(time_to_minutes(5, 59), start, end))

        # Outside range
        self.assertFalse(is_time_in_range(time_to_minutes(6, 0), start, end))
        self.assertFalse(is_time_in_range(time_to_minutes(12, 0), start, end))
        self.assertFalse(is_time_in_range(time_to_minutes(22, 59), start, end))


class TestIsWithinBlockedHours(unittest.TestCase):
    """Test the main blocked hours checking function"""

    def test_empty_blocked_hours(self):
        """Test with no blocked hours configured"""
        self.assertFalse(is_within_blocked_hours(12, 0, []))
        self.assertFalse(is_within_blocked_hours(12, 0, None))

    def test_single_range_inside(self):
        """Test when current time is inside a blocked range"""
        blocked = [{"start": "09:00", "end": "17:00"}]
        self.assertTrue(is_within_blocked_hours(12, 0, blocked))

    def test_single_range_outside(self):
        """Test when current time is outside a blocked range"""
        blocked = [{"start": "09:00", "end": "17:00"}]
        self.assertFalse(is_within_blocked_hours(20, 0, blocked))

    def test_multiple_ranges(self):
        """Test with multiple blocked ranges"""
        blocked = [
            {"start": "09:00", "end": "12:00"},
            {"start": "14:00", "end": "18:00"},
        ]

        # In first range
        self.assertTrue(is_within_blocked_hours(10, 0, blocked))

        # In second range
        self.assertTrue(is_within_blocked_hours(15, 0, blocked))

        # Between ranges
        self.assertFalse(is_within_blocked_hours(13, 0, blocked))

    def test_overnight_range(self):
        """Test overnight blocked range"""
        blocked = [{"start": "23:00", "end": "06:00"}]

        # Before midnight
        self.assertTrue(is_within_blocked_hours(23, 30, blocked))

        # After midnight
        self.assertTrue(is_within_blocked_hours(3, 0, blocked))

        # Outside range
        self.assertFalse(is_within_blocked_hours(12, 0, blocked))

    def test_invalid_range_format(self):
        """Test handling of invalid range formats"""
        blocked = [
            {"start": "invalid", "end": "12:00"},
            {"start": "09:00", "end": ""},
            {},
        ]
        # Should not crash, just skip invalid ranges
        self.assertFalse(is_within_blocked_hours(10, 0, blocked))


class TestValidateTimeFormat(unittest.TestCase):
    """Test time format validation in gui.py"""

    def test_valid_formats(self):
        """Test valid time formats"""
        self.assertTrue(validate_time_format("00:00"))
        self.assertTrue(validate_time_format("12:30"))
        self.assertTrue(validate_time_format("23:59"))
        self.assertTrue(validate_time_format("09:05"))

    def test_invalid_formats(self):
        """Test invalid time formats"""
        self.assertFalse(validate_time_format(""))
        self.assertFalse(validate_time_format("12"))
        self.assertFalse(validate_time_format("12:"))
        self.assertFalse(validate_time_format(":30"))
        self.assertFalse(validate_time_format("24:00"))
        self.assertFalse(validate_time_format("12:60"))
        self.assertFalse(validate_time_format("-1:00"))
        self.assertFalse(validate_time_format("abc"))
        self.assertFalse(validate_time_format("12:30:00"))


class TestRangesOverlap(unittest.TestCase):
    """Test overlap detection between time ranges"""

    def test_no_overlap_same_day(self):
        """Test non-overlapping same-day ranges"""
        r1 = {"start": "09:00", "end": "12:00"}
        r2 = {"start": "14:00", "end": "18:00"}
        self.assertFalse(ranges_overlap(r1, r2))

    def test_overlap_same_day(self):
        """Test overlapping same-day ranges"""
        r1 = {"start": "09:00", "end": "14:00"}
        r2 = {"start": "12:00", "end": "18:00"}
        self.assertTrue(ranges_overlap(r1, r2))

    def test_contained_range(self):
        """Test when one range contains another"""
        r1 = {"start": "08:00", "end": "20:00"}
        r2 = {"start": "10:00", "end": "12:00"}
        self.assertTrue(ranges_overlap(r1, r2))

    def test_adjacent_ranges(self):
        """Test adjacent (non-overlapping) ranges"""
        r1 = {"start": "09:00", "end": "12:00"}
        r2 = {"start": "12:00", "end": "15:00"}
        self.assertFalse(ranges_overlap(r1, r2))

    def test_overnight_overlap_with_morning(self):
        """Test overnight range overlapping with morning range"""
        r1 = {"start": "23:00", "end": "06:00"}  # Overnight
        r2 = {"start": "05:00", "end": "08:00"}  # Morning
        self.assertTrue(ranges_overlap(r1, r2))

    def test_overnight_no_overlap_with_afternoon(self):
        """Test overnight range not overlapping with afternoon"""
        r1 = {"start": "23:00", "end": "06:00"}  # Overnight
        r2 = {"start": "12:00", "end": "18:00"}  # Afternoon
        self.assertFalse(ranges_overlap(r1, r2))

    def test_two_overnight_ranges_overlap(self):
        """Test two overlapping overnight ranges"""
        r1 = {"start": "22:00", "end": "04:00"}
        r2 = {"start": "23:00", "end": "05:00"}
        self.assertTrue(ranges_overlap(r1, r2))


class TestValidateBlockedHours(unittest.TestCase):
    """Test validation of blocked hours list"""

    def test_empty_list(self):
        """Test validation of empty list"""
        is_valid, error = validate_blocked_hours([])
        self.assertTrue(is_valid)
        self.assertEqual(error, "")

    def test_single_valid_range(self):
        """Test validation of single valid range"""
        ranges = [{"start": "09:00", "end": "17:00"}]
        is_valid, error = validate_blocked_hours(ranges)
        self.assertTrue(is_valid)

    def test_multiple_valid_ranges(self):
        """Test validation of multiple non-overlapping ranges"""
        ranges = [
            {"start": "09:00", "end": "12:00"},
            {"start": "14:00", "end": "18:00"},
            {"start": "22:00", "end": "06:00"},
        ]
        is_valid, error = validate_blocked_hours(ranges)
        self.assertTrue(is_valid)

    def test_overlapping_ranges(self):
        """Test detection of overlapping ranges"""
        ranges = [
            {"start": "09:00", "end": "14:00"},
            {"start": "12:00", "end": "18:00"},
        ]
        is_valid, error = validate_blocked_hours(ranges)
        self.assertFalse(is_valid)
        self.assertIn("overlap", error.lower())

    def test_invalid_time_format(self):
        """Test detection of invalid time format"""
        ranges = [{"start": "invalid", "end": "17:00"}]
        is_valid, error = validate_blocked_hours(ranges)
        self.assertFalse(is_valid)
        self.assertIn("format", error.lower())

    def test_exclude_index(self):
        """Test exclude_index parameter for editing"""
        ranges = [
            {"start": "09:00", "end": "14:00"},
            {"start": "12:00", "end": "18:00"},  # Would overlap with first
        ]
        # Should report overlap normally
        is_valid, _ = validate_blocked_hours(ranges)
        self.assertFalse(is_valid)

        # Should pass when excluding index 1
        is_valid, _ = validate_blocked_hours(ranges, exclude_index=1)
        self.assertTrue(is_valid)


if __name__ == "__main__":
    unittest.main()
