"""
Tests for single instance functionality
"""

import sys
import os
import subprocess
import time
import tempfile
from pathlib import Path

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.single_instance import SingleInstance, ensure_single_instance  # noqa: E402


class TestSingleInstance:
    """Test the SingleInstance class"""

    def test_single_instance_creation(self):
        """Test that a single instance can be created"""
        instance = SingleInstance("TestApp1")
        assert instance is not None
        assert instance.is_locked is True
        assert instance.is_already_running() is False
        instance.release()

    def test_second_instance_blocked(self):
        """Test that a second instance is blocked"""
        instance1 = SingleInstance("TestApp2")
        assert instance1.is_locked is True

        instance2 = SingleInstance("TestApp2")
        assert instance2.is_locked is False
        assert instance2.is_already_running() is True

        instance1.release()
        instance2.release()

    def test_instance_release_and_reacquire(self):
        """Test that after release, a new instance can be acquired"""
        instance1 = SingleInstance("TestApp3")
        assert instance1.is_locked is True

        instance1.release()

        instance2 = SingleInstance("TestApp3")
        assert instance2.is_locked is True
        assert instance2.is_already_running() is False

        instance2.release()

    def test_different_app_names(self):
        """Test that different app names don't interfere"""
        instance1 = SingleInstance("TestApp4")
        instance2 = SingleInstance("TestApp5")

        assert instance1.is_locked is True
        assert instance2.is_locked is True
        assert instance1.is_already_running() is False
        assert instance2.is_already_running() is False

        instance1.release()
        instance2.release()

    def test_ensure_single_instance_helper(self):
        """Test the ensure_single_instance helper function"""
        instance1 = ensure_single_instance("TestApp6")
        assert instance1 is not None

        instance2 = ensure_single_instance("TestApp6")
        assert instance2 is None

        instance1.release()

        instance3 = ensure_single_instance("TestApp6")
        assert instance3 is not None
        instance3.release()

    def test_multiple_releases_safe(self):
        """Test that multiple releases don't cause errors"""
        instance = SingleInstance("TestApp7")
        instance.release()
        instance.release()  # Should not raise error
        instance.release()  # Should not raise error


class TestSingleInstanceIntegration:
    """Integration tests with actual Python subprocesses"""

    def test_subprocess_single_instance(self):
        """Test single instance across actual processes"""
        # This test is skipped on non-Windows platforms as file locking
        # behavior may differ, and the primary use case is Windows
        if sys.platform != "win32":
            pytest.skip("Subprocess test primarily for Windows")

        # Create a test script that tries to acquire a lock
        # Ensure the subprocess can import our project module by injecting the repo root
        repo_root = str(Path(__file__).parent.parent.resolve())
        test_script = f"""
import sys
sys.path.insert(0, r"{repo_root}")
from app.single_instance import ensure_single_instance
import time

instance = ensure_single_instance("SubprocessTest")
if instance:
    print("LOCKED")
    sys.stdout.flush()
    time.sleep(3)  # Hold lock for 3 seconds
    instance.release()
    print("RELEASED")
else:
    print("BLOCKED")
    sys.exit(1)
"""

        # Write test script to temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(test_script)
            script_path = f.name

        try:
            # Start first process
            proc1 = subprocess.Popen(
                [sys.executable, script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            # Wait a bit for first process to acquire lock
            time.sleep(0.5)

            # Try to start second process (should be blocked)
            proc2 = subprocess.Popen(
                [sys.executable, script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            # Wait for both to complete
            stdout2, stderr2 = proc2.communicate(timeout=5)
            stdout1, stderr1 = proc1.communicate(timeout=5)

            # First process should have acquired lock
            assert "LOCKED" in stdout1
            assert proc1.returncode == 0

            # Second process should have been blocked
            assert "BLOCKED" in stdout2
            assert proc2.returncode == 1

        finally:
            # Cleanup
            try:
                os.unlink(script_path)
            except Exception:
                pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
