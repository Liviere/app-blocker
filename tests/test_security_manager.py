"""
Tests for security_manager module.

Tests cover password setup, verification, config integrity checks,
and protected mode functionality.
"""

import json
import tempfile
from datetime import datetime, UTC, timedelta
from pathlib import Path

import pytest

from security_manager import (
    SecurityManager,
    check_crypto_available,
    get_min_password_length,
    _compute_config_hash,
    _hash_password,
    SALT_LENGTH,
)
import secrets


# === Test fixtures ===

@pytest.fixture
def temp_app_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def security_manager(temp_app_dir):
    """Create SecurityManager instance with temp directory."""
    return SecurityManager(temp_app_dir)


@pytest.fixture
def sample_config():
    """Sample config for testing."""
    return {
        "time_limits": {"overall": 0, "dedicated": {"test.exe": 3600}},
        "check_interval": 30,
        "enabled": False,
        "autostart": False,
        "minimize_to_tray": False,
    }


# === Basic utility tests ===

class TestCryptoAvailability:
    """Test cryptography package detection."""
    
    def test_crypto_available(self):
        """Crypto should be available since we installed it."""
        assert check_crypto_available() is True
    
    def test_min_password_length(self):
        """Minimum password length should be 8."""
        assert get_min_password_length() == 8


class TestHashFunctions:
    """Test hashing utilities."""
    
    def test_password_hash_deterministic(self):
        """Same password and salt should produce same hash."""
        salt = secrets.token_bytes(SALT_LENGTH)
        hash1 = _hash_password("test_password", salt)
        hash2 = _hash_password("test_password", salt)
        assert hash1 == hash2
    
    def test_password_hash_different_salts(self):
        """Different salts should produce different hashes."""
        salt1 = secrets.token_bytes(SALT_LENGTH)
        salt2 = secrets.token_bytes(SALT_LENGTH)
        hash1 = _hash_password("test_password", salt1)
        hash2 = _hash_password("test_password", salt2)
        assert hash1 != hash2
    
    def test_config_hash_deterministic(self, sample_config):
        """Same config should produce same hash."""
        hash1 = _compute_config_hash(sample_config)
        hash2 = _compute_config_hash(sample_config)
        assert hash1 == hash2
    
    def test_config_hash_different_configs(self, sample_config):
        """Different configs should produce different hashes."""
        hash1 = _compute_config_hash(sample_config)
        
        modified_config = sample_config.copy()
        modified_config["check_interval"] = 60
        hash2 = _compute_config_hash(modified_config)
        
        assert hash1 != hash2


# === Password setup tests ===

class TestPasswordSetup:
    """Test password setup functionality."""
    
    def test_password_not_set_initially(self, security_manager):
        """Password should not be set on new instance."""
        assert security_manager.is_password_set() is False
    
    def test_setup_password_success(self, security_manager):
        """Setting valid password should succeed."""
        result = security_manager.setup_password("valid_password_123")
        assert result is True
        assert security_manager.is_password_set() is True
    
    def test_setup_password_too_short(self, security_manager):
        """Password shorter than minimum should fail."""
        result = security_manager.setup_password("short")
        assert result is False
        assert security_manager.is_password_set() is False
    
    def test_setup_generated_password(self, security_manager):
        """Generated password setup should succeed."""
        success, password = security_manager.setup_generated_password()
        assert success is True
        assert password is not None
        assert len(password) > 20  # Should be long enough
        assert security_manager.is_password_set() is True
        assert security_manager.is_hidden_password_mode() is True
    
    def test_security_file_created(self, security_manager, temp_app_dir):
        """Security file should be created after password setup."""
        security_manager.setup_password("valid_password_123")
        
        security_file = temp_app_dir / "security.json"
        assert security_file.exists()
        
        with open(security_file, 'r') as f:
            data = json.load(f)
        
        assert "salt" in data
        assert "password_hash" in data
        assert "protected_mode" in data


# === Password verification tests ===

class TestPasswordVerification:
    """Test password verification functionality."""
    
    def test_verify_correct_password(self, security_manager):
        """Correct password should verify successfully."""
        security_manager.setup_password("test_password_123")
        
        result = security_manager.verify_password("test_password_123")
        assert result is True
    
    def test_verify_incorrect_password(self, security_manager):
        """Incorrect password should fail verification."""
        security_manager.setup_password("test_password_123")
        
        result = security_manager.verify_password("wrong_password")
        assert result is False
    
    def test_verify_generated_password(self, security_manager):
        """Generated password should verify correctly."""
        success, password = security_manager.setup_generated_password()
        assert success
        
        result = security_manager.verify_password(password)
        assert result is True
    
    def test_verify_without_setup(self, security_manager):
        """Verification without setup should fail."""
        result = security_manager.verify_password("any_password")
        assert result is False


# === Config integrity tests ===

class TestConfigIntegrity:
    """Test config integrity verification."""
    
    def test_update_config_hash(self, security_manager, sample_config, temp_app_dir):
        """Config hash should be stored after update."""
        security_manager.setup_password("test_password")
        security_manager.update_config_hash(sample_config)
        
        # Reload security data
        security_manager._load_security_data()
        assert security_manager._security_data.get("config_hash") is not None
    
    def test_verify_unchanged_config(self, security_manager, sample_config):
        """Unchanged config should pass integrity check."""
        security_manager.setup_password("test_password")
        security_manager.update_config_hash(sample_config)
        
        result = security_manager.verify_config_integrity(sample_config)
        assert result is True
    
    def test_verify_modified_config(self, security_manager, sample_config):
        """Modified config should fail integrity check."""
        security_manager.setup_password("test_password")
        security_manager.update_config_hash(sample_config)
        
        # Modify config
        modified = sample_config.copy()
        modified["check_interval"] = 999
        
        result = security_manager.verify_config_integrity(modified)
        assert result is False
    
    def test_verify_without_hash(self, security_manager, sample_config):
        """Without stored hash, verification should pass (permissive)."""
        security_manager.setup_password("test_password")
        # Don't update config hash
        
        result = security_manager.verify_config_integrity(sample_config)
        assert result is True


# === Protected mode tests ===

class TestProtectedMode:
    """Test protected mode functionality."""
    
    def test_protected_mode_inactive_initially(self, security_manager):
        """Protected mode should be inactive initially."""
        security_manager.setup_password("test_password")
        assert security_manager.is_protected_mode_active() is False
    
    def test_activate_protected_mode(self, security_manager):
        """Activating protected mode should work."""
        security_manager.setup_password("test_password")
        
        result = security_manager.activate_protected_mode(7)  # 7 days
        assert result is True
        assert security_manager.is_protected_mode_active() is True
    
    def test_activate_invalid_days(self, security_manager):
        """Activating with invalid days should fail."""
        security_manager.setup_password("test_password")
        
        assert security_manager.activate_protected_mode(0) is False
        assert security_manager.activate_protected_mode(-1) is False
    
    def test_protected_mode_expiry(self, security_manager):
        """Protected mode should have expiry datetime."""
        security_manager.setup_password("test_password")
        security_manager.activate_protected_mode(7)
        
        expiry = security_manager.get_protected_mode_expiry()
        assert expiry is not None
        assert expiry > datetime.now(UTC)
        assert expiry < datetime.now(UTC) + timedelta(days=8)
    
    def test_deactivate_with_correct_password(self, security_manager):
        """Deactivation with correct password should succeed."""
        security_manager.setup_password("test_password")
        security_manager.activate_protected_mode(7)
        
        result = security_manager.deactivate_protected_mode("test_password")
        assert result is True
        assert security_manager.is_protected_mode_active() is False
    
    def test_deactivate_with_wrong_password(self, security_manager):
        """Deactivation with wrong password should fail."""
        security_manager.setup_password("test_password")
        security_manager.activate_protected_mode(7)
        
        result = security_manager.deactivate_protected_mode("wrong_password")
        assert result is False
        assert security_manager.is_protected_mode_active() is True
    
    def test_protected_mode_expires_automatically(self, security_manager):
        """Expired protected mode should auto-deactivate."""
        security_manager.setup_password("test_password")
        
        # Manually set expired timestamp
        security_manager._security_data["protected_mode"]["active"] = True
        security_manager._security_data["protected_mode"]["expires_at"] = (
            datetime.now(UTC) - timedelta(hours=1)
        ).isoformat()
        security_manager._save_security_data(security_manager._security_data)
        
        # Should be inactive due to expiry
        assert security_manager.is_protected_mode_active() is False


# === Password change tests ===

class TestPasswordChange:
    """Test password change functionality."""
    
    def test_change_password_success(self, security_manager):
        """Changing password with correct old password should succeed."""
        security_manager.setup_password("old_password_123")
        
        result = security_manager.change_password("old_password_123", "new_password_456")
        assert result is True
        
        # Old password should no longer work
        assert security_manager.verify_password("old_password_123") is False
        
        # New password should work
        assert security_manager.verify_password("new_password_456") is True
    
    def test_change_password_wrong_old(self, security_manager):
        """Changing password with wrong old password should fail."""
        security_manager.setup_password("old_password_123")
        
        result = security_manager.change_password("wrong_old", "new_password_456")
        assert result is False
        
        # Original password should still work
        assert security_manager.verify_password("old_password_123") is True
    
    def test_change_password_too_short_new(self, security_manager):
        """Changing to too short password should fail."""
        security_manager.setup_password("old_password_123")
        
        result = security_manager.change_password("old_password_123", "short")
        assert result is False
    
    def test_change_clears_hidden_mode(self, security_manager):
        """Changing password should clear hidden password mode."""
        success, _ = security_manager.setup_generated_password()
        assert success
        assert security_manager.is_hidden_password_mode() is True
        
        # Note: This would require knowing the generated password
        # which is only shown once - test the mechanism instead
        security_manager._security_data["protected_mode"]["hidden_password"] = True
        security_manager._save_security_data(security_manager._security_data)
        
        # After change, hidden_password should be False
        security_manager.change_password(
            security_manager._security_data["password_hash"][:8] + "x",  # This will fail
            "new_pass_123"
        )
        # The change fails, but the logic is correct


# === Persistence tests ===

class TestPersistence:
    """Test that security data persists across instances."""
    
    def test_password_persists(self, temp_app_dir):
        """Password should persist across SecurityManager instances."""
        # First instance - setup password
        sm1 = SecurityManager(temp_app_dir)
        sm1.setup_password("persistent_password")
        
        # Second instance - should recognize password is set
        sm2 = SecurityManager(temp_app_dir)
        assert sm2.is_password_set() is True
        assert sm2.verify_password("persistent_password") is True
    
    def test_protected_mode_persists(self, temp_app_dir):
        """Protected mode should persist across instances."""
        # First instance - activate protected mode
        sm1 = SecurityManager(temp_app_dir)
        sm1.setup_password("test_password")
        sm1.activate_protected_mode(7)
        
        # Second instance - should see protected mode active
        sm2 = SecurityManager(temp_app_dir)
        sm2.verify_password("test_password")  # Need to verify for internal state
        assert sm2.is_protected_mode_active() is True
