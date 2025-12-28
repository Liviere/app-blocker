"""
Security manager for App Blocker.

This module provides master password management, configuration integrity
verification, and protected mode functionality. Protected mode locks 
monitoring settings to prevent circumvention.

WHY THIS EXISTS:
- Users need a way to lock themselves out of disabling monitoring
- Configuration integrity should be verified to detect manual edits
- Protected mode provides time-based commitment device
"""

import base64
import hashlib
import json
import secrets
from datetime import datetime, UTC, timedelta
from pathlib import Path
from typing import Optional, Tuple

# === Cryptographic primitives ===
# We use standard library for crypto to avoid external dependencies.
# PBKDF2 for key derivation.

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False


# ===  Constants and configuration ===
# These values define security parameters.

SALT_LENGTH = 32  # bytes for password salt
PBKDF2_ITERATIONS = 600_000  # OWASP 2023 recommendation for SHA256
PASSWORD_MIN_LENGTH = 8
GENERATED_PASSWORD_LENGTH = 32  # bytes, base64 encoded = 43 chars


def _derive_key_from_password(password: str, salt: bytes) -> bytes:
    """
    Derive a 32-byte encryption key from password using PBKDF2.
    
    WHY: We need a fixed-length key for AES encryption, but passwords
    have variable length. PBKDF2 provides secure key stretching.
    """
    if not CRYPTO_AVAILABLE:
        # Fallback using hashlib (less secure but works without cryptography)
        key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt,
            PBKDF2_ITERATIONS,
            dklen=32
        )
        return base64.urlsafe_b64encode(key)
    
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    key = kdf.derive(password.encode('utf-8'))
    return base64.urlsafe_b64encode(key)


def _hash_password(password: str, salt: bytes) -> str:
    """
    Hash password for verification purposes (not for encryption).
    
    WHY: We store a hash to verify the user knows the password
    without storing the password itself.
    """
    hash_bytes = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt,
        PBKDF2_ITERATIONS
    )
    return base64.b64encode(hash_bytes).decode('ascii')


def _compute_config_hash(config: dict) -> str:
    """
    Compute SHA256 hash of config for integrity verification.
    
    WHY: Detect if user manually edited config.json to circumvent limits.
    """
    config_str = json.dumps(config, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(config_str.encode('utf-8')).hexdigest()


# === SecurityManager class ===
# Main class orchestrating all security features.

class SecurityManager:
    """
    Manages master password, config integrity, and protected mode.
    
    WHY THIS CLASS EXISTS:
    - Centralizes all security-related logic
    - Maintains security state across application lifetime
    - Provides clean API for GUI integration
    
    NOTE: Config remains in plaintext for monitor process compatibility.
    Security is enforced via integrity checks and protected mode.
    """
    
    SECURITY_FILE = "security.json"
    
    def __init__(self, app_dir: Path):
        self.app_dir = Path(app_dir)
        self.security_path = self.app_dir / self.SECURITY_FILE
        self.config_path = self.app_dir / "config.json"
        
        self._security_data: Optional[dict] = None
        self._password_verified = False
    
    # --- Password setup and verification ---
    
    def is_password_set(self) -> bool:
        """Check if master password has been configured."""
        return self.security_path.exists()
    
    def setup_password(self, password: str) -> bool:
        """
        Set up master password for the first time.
        
        WHY: Creates security.json with password hash and salt.
        Returns False if password is too short.
        """
        if len(password) < PASSWORD_MIN_LENGTH:
            return False
        
        salt = secrets.token_bytes(SALT_LENGTH)
        password_hash = _hash_password(password, salt)
        
        # Compute current config hash if exists
        config_hash = None
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                config_hash = _compute_config_hash(config)
            except Exception:
                pass
        
        security_data = {
            "version": 1,
            "salt": base64.b64encode(salt).decode('ascii'),
            "password_hash": password_hash,
            "config_hash": config_hash,
            "protected_mode": {
                "active": False,
                "expires_at": None,
                "hidden_password": False,
            },
            "created_at": datetime.now(UTC).isoformat(),
        }
        
        self._save_security_data(security_data)
        self._security_data = security_data
        self._password_verified = True
        
        return True
    
    def setup_generated_password(self) -> Tuple[bool, Optional[str]]:
        """
        Generate and set up a random password that user won't know.
        
        WHY: For users who want maximum commitment - they can't
        disable protected mode even if they want to.
        
        Returns: (success, password_for_display_once)
        Password is shown once for emergency recovery, then forgotten.
        """
        password = secrets.token_urlsafe(GENERATED_PASSWORD_LENGTH)
        
        salt = secrets.token_bytes(SALT_LENGTH)
        password_hash = _hash_password(password, salt)
        
        # Compute current config hash if exists
        config_hash = None
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                config_hash = _compute_config_hash(config)
            except Exception:
                pass
        
        security_data = {
            "version": 1,
            "salt": base64.b64encode(salt).decode('ascii'),
            "password_hash": password_hash,
            "config_hash": config_hash,
            "protected_mode": {
                "active": False,
                "expires_at": None,
                "hidden_password": True,  # Marks that user chose hidden password
            },
            "created_at": datetime.now(UTC).isoformat(),
        }
        
        self._save_security_data(security_data)
        self._security_data = security_data
        self._password_verified = True
        
        # Return password for one-time display (emergency recovery)
        return True, password
    
    def verify_password(self, password: str) -> bool:
        """
        Verify if provided password matches stored hash.
        
        WHY: Used for unlocking app and deactivating protected mode.
        """
        if not self._security_data:
            self._load_security_data()
        
        if not self._security_data:
            return False
        
        salt = base64.b64decode(self._security_data["salt"])
        expected_hash = self._security_data["password_hash"]
        actual_hash = _hash_password(password, salt)
        
        # Constant-time comparison to prevent timing attacks
        if secrets.compare_digest(expected_hash, actual_hash):
            self._password_verified = True
            return True
        
        return False
    
    def is_hidden_password_mode(self) -> bool:
        """Check if user chose generated (hidden) password."""
        if not self._security_data:
            self._load_security_data()
        
        if not self._security_data:
            return False
        
        return self._security_data.get("protected_mode", {}).get("hidden_password", False)
    
    # --- Config integrity verification ---
    
    def update_config_hash(self, config: dict):
        """
        Update stored config hash after legitimate config change.
        
        WHY: After GUI saves config, we update the hash so future
        integrity checks pass.
        """
        if not self._security_data:
            self._load_security_data()
        
        if not self._security_data:
            return
        
        self._security_data["config_hash"] = _compute_config_hash(config)
        self._save_security_data(self._security_data)
    
    def verify_config_integrity(self, config: dict) -> bool:
        """
        Check if config matches stored hash.
        
        WHY: Detect manual edits to config.json that bypass GUI.
        Returns True if config is valid or no hash stored.
        """
        if not self._security_data:
            self._load_security_data()
        
        if not self._security_data:
            return True  # No security data = no verification
        
        stored_hash = self._security_data.get("config_hash")
        if not stored_hash:
            return True  # No hash stored = skip verification
        
        current_hash = _compute_config_hash(config)
        return secrets.compare_digest(stored_hash, current_hash)
    
    # --- Protected mode management ---
    
    def is_protected_mode_active(self) -> bool:
        """
        Check if protected mode is currently active.
        
        WHY: Determines if UI restrictions should be enforced.
        Protected mode expires after configured duration.
        """
        if not self._security_data:
            self._load_security_data()
        
        if not self._security_data:
            return False
        
        protected = self._security_data.get("protected_mode", {})
        if not protected.get("active", False):
            return False
        
        expires_at = protected.get("expires_at")
        if not expires_at:
            return True  # No expiry = permanent
        
        try:
            expiry_dt = datetime.fromisoformat(expires_at)
            if expiry_dt.tzinfo is None:
                expiry_dt = expiry_dt.replace(tzinfo=UTC)
            
            if datetime.now(UTC) >= expiry_dt:
                # Expired - deactivate
                self._security_data["protected_mode"]["active"] = False
                self._save_security_data(self._security_data)
                return False
            
            return True
        except Exception:
            return False
    
    def get_protected_mode_expiry(self) -> Optional[datetime]:
        """Get expiry datetime of protected mode."""
        if not self._security_data:
            self._load_security_data()
        
        if not self._security_data:
            return None
        
        expires_at = self._security_data.get("protected_mode", {}).get("expires_at")
        if not expires_at:
            return None
        
        try:
            expiry_dt = datetime.fromisoformat(expires_at)
            if expiry_dt.tzinfo is None:
                expiry_dt = expiry_dt.replace(tzinfo=UTC)
            return expiry_dt
        except Exception:
            return None
    
    def activate_protected_mode(self, days: int) -> bool:
        """
        Activate protected mode for specified number of days.
        
        WHY: User commits to monitoring for a period.
        During this time, they cannot disable monitoring,
        change autostart, or close the app.
        """
        if not self._security_data:
            self._load_security_data()
        
        if not self._security_data:
            return False
        
        if days <= 0:
            return False
        
        expires_at = datetime.now(UTC) + timedelta(days=days)
        
        self._security_data["protected_mode"]["active"] = True
        self._security_data["protected_mode"]["expires_at"] = expires_at.isoformat()
        self._security_data["protected_mode"]["activated_at"] = datetime.now(UTC).isoformat()
        
        self._save_security_data(self._security_data)
        return True
    
    def deactivate_protected_mode(self, password: str) -> bool:
        """
        Deactivate protected mode using master password.
        
        WHY: Emergency exit for protected mode.
        Requires password to prevent accidental deactivation.
        """
        if not self.verify_password(password):
            return False
        
        self._security_data["protected_mode"]["active"] = False
        self._security_data["protected_mode"]["expires_at"] = None
        self._security_data["protected_mode"]["deactivated_at"] = datetime.now(UTC).isoformat()
        
        self._save_security_data(self._security_data)
        return True
    
    # --- Internal helpers ---
    
    def _load_security_data(self):
        """Load security.json file."""
        if not self.security_path.exists():
            self._security_data = None
            return
        
        try:
            with open(self.security_path, 'r') as f:
                self._security_data = json.load(f)
        except Exception:
            self._security_data = None
    
    def _save_security_data(self, data: dict):
        """Save security.json file."""
        try:
            with open(self.security_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass
    
    def change_password(self, old_password: str, new_password: str) -> bool:
        """
        Change master password.
        
        WHY: Users may need to change password if compromised.
        Requires old password for verification.
        """
        if not self.verify_password(old_password):
            return False
        
        if len(new_password) < PASSWORD_MIN_LENGTH:
            return False
        
        # Generate new salt and hash
        new_salt = secrets.token_bytes(SALT_LENGTH)
        new_hash = _hash_password(new_password, new_salt)
        
        # Update security data
        self._security_data["salt"] = base64.b64encode(new_salt).decode('ascii')
        self._security_data["password_hash"] = new_hash
        self._security_data["protected_mode"]["hidden_password"] = False
        self._security_data["password_changed_at"] = datetime.now(UTC).isoformat()
        
        self._save_security_data(self._security_data)
        return True


# === Utility functions for external use ===

def check_crypto_available() -> bool:
    """Check if cryptography package is available."""
    return CRYPTO_AVAILABLE


def get_min_password_length() -> int:
    """Get minimum password length requirement."""
    return PASSWORD_MIN_LENGTH
