# Single Instance Enforcement

## Overview

The app-blocker application enforces single-instance behavior to prevent multiple copies from running simultaneously, which could cause conflicts and malfunctions.

## How It Works

### Implementation

The single instance mechanism is implemented in `single_instance.py` and uses different approaches based on the operating system:

**Windows (Production):**
- Uses Windows named mutex for reliable single-instance detection
- Mutex name: `Global\AppBlocker_SingleInstance`
- Most reliable method for Windows applications

**Unix/Linux (Development/Testing):**
- Uses file-based locking with `fcntl.flock()`
- Lock file location: `%TEMP%/AppBlocker_instance.lock`
- Allows development and testing on non-Windows platforms

### Separate Locks for GUI and Monitor

The application uses two different locks:
- **GUI Lock:** `AppBlocker_GUI` - Prevents multiple GUI instances
- **Monitor Lock:** `AppBlocker_Monitor` - Prevents multiple monitor instances

This design allows the GUI and monitor to run concurrently (which is the normal use case), while still preventing duplicate instances of each component.

## User Experience

### Launching Multiple GUI Instances

When a user tries to launch a second GUI instance:
1. A warning dialog appears with the message:
   ```
   App Blocker Already Running
   
   App Blocker is already running.
   
   Only one instance of the application can run at a time.
   Check your system tray or taskbar for the existing instance.
   ```
2. The second instance exits immediately
3. The first instance continues running normally

### Launching Multiple Monitor Instances

When a second monitor instance is attempted:
1. A message is printed to the console:
   ```
   App Blocker monitoring is already running. Only one instance allowed.
   ```
2. The second instance exits with code 1
3. The first instance continues monitoring

## Testing

### Unit Tests

Run the single instance tests:
```bash
pytest tests/test_single_instance.py -v
```

Test coverage includes:
- Basic single instance creation
- Blocking of second instances
- Release and reacquire behavior
- Different app names don't interfere
- Multiple releases are safe
- Subprocess behavior (Windows only)

### Demonstration

Run the demo script to see the behavior:
```bash
python demo_single_instance.py
```

This demonstrates:
- GUI single instance enforcement
- Monitor single instance enforcement
- Concurrent GUI and monitor operation

## Technical Details

### Lock Lifecycle

1. **Acquisition:** When the application starts, it attempts to acquire the lock
2. **Holding:** The lock is held for the entire application lifetime
3. **Release:** The lock is released when the application exits (normal or abnormal)

### Resource Cleanup

The implementation ensures proper cleanup:
- Locks are released in the application's `finally` block
- The `SingleInstance` class has a destructor (`__del__`) for cleanup
- Multiple releases are safe (idempotent)

### Thread Safety

The implementation is thread-safe:
- Windows mutex is inherently thread-safe
- File locks on Unix are process-level, not thread-level
- Each instance creates its own lock object

## Known Limitations

1. **File Lock Limitations (Unix):**
   - File locks are per-process on Unix systems
   - If testing in the same Python process, use subprocess tests

2. **Stale Locks:**
   - In rare cases (system crash), lock files may remain
   - Lock files are automatically cleaned up on next successful run
   - Manual cleanup: Delete files in `%TEMP%` matching `AppBlocker_*_instance.lock`

3. **User Session Isolation:**
   - Each user session has separate locks
   - Multiple users can run the app simultaneously on the same machine

## Troubleshooting

### "Already Running" but Application Not Visible

If you receive the "already running" message but can't find the application:

1. **Check System Tray:**
   - Look for the App Blocker icon in the system tray
   - Right-click and select "Show App Blocker"

2. **Check Task Manager:**
   - Look for `app-blocker-gui.exe` or `python.exe` running `gui.py`
   - End the task if it's stuck

3. **Clean Lock Files (Last Resort):**
   - Navigate to `%TEMP%` (Windows: `C:\Users\<username>\AppData\Local\Temp`)
   - Delete files matching `AppBlocker_*_instance.lock`
   - Try launching the application again

### Testing Multiple Instances

To test the single instance behavior:

1. Launch the GUI: `python gui.py`
2. Try to launch another GUI instance: `python gui.py`
3. You should see the warning dialog

For automated testing, see the test suite in `tests/test_single_instance.py`.
