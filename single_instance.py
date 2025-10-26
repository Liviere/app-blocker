"""
Single instance enforcement for App Blocker
Ensures only one instance of the application can run at a time on Windows
"""

import sys
import os


class SingleInstance:
    """
    Ensures only one instance of the application can run at a time.
    Uses Windows mutex on Windows platforms, file locking on other platforms.
    """

    def __init__(self, name="AppBlocker"):
        """
        Initialize single instance checker.

        Args:
            name: Unique name for this application instance
        """
        self.name = name
        self.mutex = None
        self.lockfile = None
        self.is_locked = False

        if sys.platform == "win32":
            self._init_windows_mutex()
        else:
            self._init_file_lock()

    def _init_windows_mutex(self):
        """Initialize Windows mutex for single instance check"""
        try:
            import ctypes
            from ctypes import wintypes

            # Define Windows API functions
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

            # CreateMutexW function
            CreateMutexW = kernel32.CreateMutexW
            CreateMutexW.argtypes = [
                wintypes.LPVOID,  # lpMutexAttributes
                wintypes.BOOL,  # bInitialOwner
                wintypes.LPCWSTR,  # lpName
            ]
            CreateMutexW.restype = wintypes.HANDLE

            # Create a unique mutex name for this application
            mutex_name = f"Global\\{self.name}_SingleInstance"

            # Try to create the mutex
            self.mutex = CreateMutexW(None, True, mutex_name)

            # Check if mutex already exists (ERROR_ALREADY_EXISTS = 183)
            last_error = ctypes.get_last_error()
            if last_error == 183:  # ERROR_ALREADY_EXISTS
                self.is_locked = False
                # Close the mutex handle
                if self.mutex:
                    kernel32.CloseHandle(self.mutex)
                    self.mutex = None
            else:
                self.is_locked = True

        except Exception as e:
            print(f"Error creating Windows mutex: {e}")
            # Fallback to file-based locking if mutex creation fails
            self._init_file_lock()

    def _init_file_lock(self):
        """Initialize file-based locking for non-Windows platforms"""
        try:
            import tempfile
            from pathlib import Path

            # Create lock file in temp directory
            temp_dir = Path(tempfile.gettempdir())
            lockfile_path = temp_dir / f"{self.name}_instance.lock"

            # Try to create and lock the file
            if sys.platform == "win32":
                # On Windows, use exclusive file open with msvcrt
                try:
                    import msvcrt

                    self.lockfile = open(lockfile_path, "w")
                    msvcrt.locking(self.lockfile.fileno(), msvcrt.LK_NBLCK, 1)
                    # Write PID to lockfile
                    self.lockfile.write(str(os.getpid()))
                    self.lockfile.flush()
                    self.is_locked = True
                except (IOError, OSError):
                    self.is_locked = False
                    if self.lockfile:
                        try:
                            self.lockfile.close()
                        except Exception:
                            pass
                        self.lockfile = None
            else:
                # On Unix-like systems, use fcntl
                import fcntl

                try:
                    # Open file for read/write, create if doesn't exist
                    self.lockfile = open(lockfile_path, "w")
                    # Try to acquire exclusive lock without blocking
                    fcntl.flock(self.lockfile.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    # Write PID to lockfile
                    self.lockfile.write(str(os.getpid()))
                    self.lockfile.flush()
                    self.is_locked = True
                except (IOError, OSError, BlockingIOError):
                    self.is_locked = False
                    if self.lockfile:
                        try:
                            self.lockfile.close()
                        except Exception:
                            pass
                        self.lockfile = None

        except Exception as e:
            print(f"Error creating lock file: {e}")
            self.is_locked = False

    def is_already_running(self):
        """
        Check if another instance is already running.

        Returns:
            bool: True if another instance is running, False otherwise
        """
        return not self.is_locked

    def release(self):
        """Release the instance lock"""
        if not self.is_locked:
            return

        if sys.platform == "win32" and self.mutex:
            try:
                import ctypes

                kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
                kernel32.CloseHandle(self.mutex)
                self.mutex = None
            except Exception:
                pass  # Silently fail during cleanup

        if self.lockfile:
            try:
                self.lockfile.close()
            except Exception:
                pass  # Silently fail during cleanup

            # Try to remove the lock file
            try:
                import tempfile
                from pathlib import Path

                temp_dir = Path(tempfile.gettempdir())
                lockfile_path = temp_dir / f"{self.name}_instance.lock"
                if lockfile_path.exists():
                    lockfile_path.unlink()
            except Exception:
                pass  # Silently fail during cleanup

        self.is_locked = False

    def __del__(self):
        """Cleanup when object is destroyed"""
        self.release()


def ensure_single_instance(app_name="AppBlocker"):
    """
    Ensure only one instance of the application is running.

    Args:
        app_name: Unique name for this application

    Returns:
        SingleInstance object if successful, None if another instance is running
    """
    instance = SingleInstance(app_name)
    if instance.is_already_running():
        return None
    return instance


if __name__ == "__main__":
    # Test the single instance mechanism
    print("Testing single instance mechanism...")

    instance1 = ensure_single_instance("TestApp")
    if instance1:
        print("✓ First instance acquired successfully")

        # Try to create a second instance
        instance2 = ensure_single_instance("TestApp")
        if instance2:
            print("✗ ERROR: Second instance should not be allowed!")
            instance2.release()
        else:
            print("✓ Second instance correctly blocked")

        # Release first instance
        instance1.release()
        print("✓ First instance released")

        # Now try to create a new instance after release
        instance3 = ensure_single_instance("TestApp")
        if instance3:
            print("✓ New instance acquired after release")
            instance3.release()
        else:
            print("✗ ERROR: Should be able to acquire after release")
    else:
        print("✗ ERROR: Could not acquire first instance")
