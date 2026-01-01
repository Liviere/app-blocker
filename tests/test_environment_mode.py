"""
Tests for environment flag behavior and update application timing.

WHY: Ensure time limit changes apply immediately unless protected mode
    requires delayed updates; environment flag is informational only.
"""

import os


class TestEnvironmentMode:
    """Test environment flag detection only"""

    def test_default_environment_is_production(self):
        """Environment should default to PRODUCTION mode"""
        # Clear any existing env var
        old_env = os.environ.pop("APP_BLOCKER_ENV", None)
        try:
            from app.common import is_development_mode
            assert not is_development_mode()
        finally:
            if old_env:
                os.environ["APP_BLOCKER_ENV"] = old_env

    def test_environment_mode_toggle(self):
        """Should be able to toggle between PRODUCTION and DEVELOPMENT"""
        old_env = os.environ.get("APP_BLOCKER_ENV")
        try:
            from app.common import is_development_mode
            
            # Start in production
            os.environ["APP_BLOCKER_ENV"] = "PRODUCTION"
            assert not is_development_mode()

            # Switch to development
            os.environ["APP_BLOCKER_ENV"] = "DEVELOPMENT"
            assert is_development_mode()

            # Switch back to production
            os.environ["APP_BLOCKER_ENV"] = "PRODUCTION"
            assert not is_development_mode()
        finally:
            if old_env:
                os.environ["APP_BLOCKER_ENV"] = old_env
            else:
                os.environ.pop("APP_BLOCKER_ENV", None)

    def test_case_insensitive_environment_check(self):
        """Environment check should be case-insensitive"""
        old_env = os.environ.get("APP_BLOCKER_ENV")
        try:
            from app.common import is_development_mode

            # Test various cases for development
            for env_value in ["development", "DEVELOPMENT", "Development", "DevelopMent"]:
                os.environ["APP_BLOCKER_ENV"] = env_value
                assert is_development_mode()

            # Test various cases for production
            for env_value in ["production", "PRODUCTION", "Production", "ProDuction"]:
                os.environ["APP_BLOCKER_ENV"] = env_value
                assert not is_development_mode()
        finally:
            if old_env:
                os.environ["APP_BLOCKER_ENV"] = old_env
            else:
                os.environ.pop("APP_BLOCKER_ENV", None)

    def test_missing_environment_defaults_to_production(self):
        """If environment variable is missing, should default to PRODUCTION"""
        old_env = os.environ.pop("APP_BLOCKER_ENV", None)
        try:
            from app.common import is_development_mode
            assert not is_development_mode()
        finally:
            if old_env:
                os.environ["APP_BLOCKER_ENV"] = old_env

    def test_invalid_environment_treated_as_production(self):
        """Invalid environment values should be treated as PRODUCTION"""
        old_env = os.environ.get("APP_BLOCKER_ENV")
        try:
            from app.common import is_development_mode
            
            for invalid_value in ["STAGING", "TEST", "DEBUG", ""]:
                os.environ["APP_BLOCKER_ENV"] = invalid_value
                assert not is_development_mode(), f"Invalid value '{invalid_value}' was treated as DEVELOPMENT"
        finally:
            if old_env:
                os.environ["APP_BLOCKER_ENV"] = old_env
            else:
                os.environ.pop("APP_BLOCKER_ENV", None)


class TestEnvironmentModeIntegration:
    """(Legacy placeholder intentionally empty)"""
    pass
