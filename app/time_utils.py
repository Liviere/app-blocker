"""
Time utilities for App Blocker.

This module consolidates all time-related parsing, validation, and calculation
functions that were scattered across main.py and gui.py.

WHY THIS EXISTS:
- parse_time_str() and time_to_minutes() were in main.py
- validate_time_format() and time_str_to_minutes() were in gui.py (similar logic)
- ranges_overlap() and validate_blocked_hours() were only in gui.py
- is_time_in_range() was only in main.py
- Centralizing eliminates duplication and provides consistent time handling
"""

from typing import Tuple, List, Dict, Any


def parse_time_str(time_str: str) -> Tuple[int, int]:
    """
    Parse 'HH:MM' string to (hours, minutes) tuple.
    
    WHY: We need numeric values for time comparison logic.
    
    Args:
        time_str: Time string in 'HH:MM' format
        
    Returns:
        Tuple[int, int]: (hours, minutes)
        
    Raises:
        ValueError: If time_str is not in valid format
    """
    if not time_str:
        raise ValueError("Time string cannot be empty")
    
    parts = time_str.strip().split(":")
    if len(parts) != 2:
        raise ValueError("Time must be in HH:MM format")
    
    try:
        hours = int(parts[0])
        minutes = int(parts[1])
        
        if not (0 <= hours <= 23):
            raise ValueError("Hours must be 0-23")
        if not (0 <= minutes <= 59):
            raise ValueError("Minutes must be 0-59")
        
        return hours, minutes
    except (ValueError, IndexError) as e:
        raise ValueError(f"Invalid time format: {e}")


def time_to_minutes(hours: int, minutes: int) -> int:
    """
    Convert hours and minutes to total minutes since midnight.
    
    WHY: Simplifies time comparison - single number instead of two.

    Args:
        hours: Hours (0-23)
        minutes: Minutes (0-59)
        
    Returns:
        int: Total minutes since midnight
    """
    return hours * 60 + minutes


def time_str_to_minutes(time_str: str) -> int:
    """
    Convert 'HH:MM' string directly to minutes since midnight.
    
    WHY: Combines parse_time_str and time_to_minutes for convenience.
    
    Args:
        time_str: Time string in 'HH:MM' format
        
    Returns:
        int: Total minutes since midnight
        
    Raises:
        ValueError: If time_str is not in valid format
    """
    hours, minutes = parse_time_str(time_str)
    return time_to_minutes(hours, minutes)


def validate_time_format(time_str: str) -> bool:
    """
    Validate that string is in HH:MM format (24h).
    
    WHY: Ensures user input can be parsed correctly by the monitor.
    
    Args:
        time_str: Time string to validate
        
    Returns:
        bool: True if valid format, False otherwise
    """
    try:
        parse_time_str(time_str)
        return True
    except ValueError:
        return False


def is_time_in_range(current_minutes: int, start_minutes: int, end_minutes: int) -> bool:
    """
    Check if current time (in minutes) falls within a range.
    
    WHY: Handles both normal ranges (09:00-17:00) and overnight ranges (23:00-02:00).
    Overnight ranges are detected when start > end.
    
    Args:
        current_minutes: Current time in minutes since midnight
        start_minutes: Range start in minutes since midnight
        end_minutes: Range end in minutes since midnight
        
    Returns:
        bool: True if current time is in range
    """
    if start_minutes <= end_minutes:
        # Normal range: e.g., 09:00 to 17:00
        return start_minutes <= current_minutes < end_minutes
    else:
        # Overnight range: e.g., 23:00 to 02:00
        # Current time is in range if it's >= start OR < end
        return current_minutes >= start_minutes or current_minutes < end_minutes


def ranges_overlap(range1: Dict[str, str], range2: Dict[str, str]) -> bool:
    """
    Check if two time ranges overlap.
    
    WHY: We need to prevent users from creating conflicting/overlapping blocked periods.
    Handles both normal and overnight ranges.
    
    Args:
        range1: Dict with 'start' and 'end' time strings
        range2: Dict with 'start' and 'end' time strings
        
    Returns:
        bool: True if ranges overlap
        
    Raises:
        ValueError: If time formats are invalid
    """
    start1 = time_str_to_minutes(range1["start"])
    end1 = time_str_to_minutes(range1["end"])
    start2 = time_str_to_minutes(range2["start"])
    end2 = time_str_to_minutes(range2["end"])
    
    # Convert ranges to sets of minutes for overlap detection
    def get_minutes_set(start: int, end: int) -> set:
        if start <= end:
            return set(range(start, end))
        else:
            # Overnight range: from start to midnight + from midnight to end
            return set(range(start, 24 * 60)) | set(range(0, end))
    
    set1 = get_minutes_set(start1, end1)
    set2 = get_minutes_set(start2, end2)
    
    return bool(set1 & set2)


def validate_blocked_hours(ranges: List[Dict[str, str]], exclude_index: int = -1) -> Tuple[bool, str]:
    """
    Validate a list of blocked time ranges.
    
    WHY: Ensures configuration consistency - no overlaps, valid formats.
    exclude_index: skip this index when checking overlaps (for editing existing range).
    Returns (is_valid, error_message).
    
    Args:
        ranges: List of time range dictionaries with 'start' and 'end' keys
        exclude_index: Index to skip during overlap checking (-1 to check all)
        
    Returns:
        Tuple[bool, str]: (is_valid, error_message)
    """
    # Validate each range format
    for i, r in enumerate(ranges):
        if i == exclude_index:
            continue
        
        start = r.get("start", "")
        end = r.get("end", "")
        
        if not validate_time_format(start):
            return False, f"Invalid start time format in range {i+1}: '{start}'"
        
        if not validate_time_format(end):
            return False, f"Invalid end time format in range {i+1}: '{end}'"
    
    # Check for overlaps between all pairs
    for i in range(len(ranges)):
        if i == exclude_index:
            continue
        for j in range(i + 1, len(ranges)):
            if j == exclude_index:
                continue
            try:
                if ranges_overlap(ranges[i], ranges[j]):
                    return False, f"Time ranges {i+1} and {j+1} overlap"
            except ValueError as e:
                return False, f"Error checking overlap: {e}"
    
    return True, ""


# === Higher-level blocked hours functions ===
# These work with datetime objects and blocked hours configuration


def is_within_blocked_hours(now_hour: int, now_minute: int, blocked_hours: List[Dict[str, str]]) -> bool:
    """
    Check if current time falls within any blocked time range.
    
    WHY: Main entry point for blocked hours checking in the monitor loop.
    Returns True if apps should be blocked right now.
    
    Args:
        now_hour: Current hour (0-23)
        now_minute: Current minute (0-59)
        blocked_hours: List of blocked time ranges
        
    Returns:
        bool: True if within blocked hours
    """
    if not blocked_hours:
        return False
    
    current_minutes = time_to_minutes(now_hour, now_minute)
    
    for time_range in blocked_hours:
        start_str = time_range.get("start", "")
        end_str = time_range.get("end", "")
        
        if not start_str or not end_str:
            continue
        
        try:
            start_h, start_m = parse_time_str(start_str)
            end_h, end_m = parse_time_str(end_str)
            
            start_minutes = time_to_minutes(start_h, start_m)
            end_minutes = time_to_minutes(end_h, end_m)
            
            if is_time_in_range(current_minutes, start_minutes, end_minutes):
                return True
        except ValueError:
            # Invalid time format - skip this range
            continue
    
    return False


def get_minutes_until_blocked_hours(now_hour: int, now_minute: int, blocked_hours: List[Dict[str, str]]) -> Tuple[int, str]:
    """
    Calculate minutes until the nearest blocked hours period starts.
    
    WHY: Needed to trigger warning notifications before blocked hours begin.
    Returns (minutes_until_block, start_time_str) or (-1, "") if no upcoming block.
    Returns -1 if currently within blocked hours (already blocking).
    This logic was in main.py.
    
    Args:
        now_hour: Current hour (0-23)
        now_minute: Current minute (0-59)
        blocked_hours: List of blocked time ranges
        
    Returns:
        Tuple[int, str]: (minutes_until_block, start_time_str) or (-1, "")
    """
    if not blocked_hours:
        return -1, ""
    
    current_minutes = time_to_minutes(now_hour, now_minute)
    min_distance = float('inf')
    nearest_start_str = ""
    
    for time_range in blocked_hours:
        start_str = time_range.get("start", "")
        end_str = time_range.get("end", "")
        
        if not start_str or not end_str:
            continue
        
        try:
            start_h, start_m = parse_time_str(start_str)
            start_minutes = time_to_minutes(start_h, start_m)
            
            # Check if we're currently in this blocked period
            end_h, end_m = parse_time_str(end_str)
            end_minutes = time_to_minutes(end_h, end_m)
            
            if is_time_in_range(current_minutes, start_minutes, end_minutes):
                # Already in blocked hours - no warning needed
                return -1, ""
            
            # Calculate distance to start of this blocked period
            if current_minutes < start_minutes:
                # Same day: start is ahead
                distance = start_minutes - current_minutes
            else:
                # Next day: wrap around midnight (1440 = minutes in day)
                distance = (1440 - current_minutes) + start_minutes
            
            if distance < min_distance:
                min_distance = distance
                nearest_start_str = start_str
                
        except ValueError:
            continue
    
    if min_distance == float('inf'):
        return -1, ""
    
    return int(min_distance), nearest_start_str