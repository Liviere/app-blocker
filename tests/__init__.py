"""
Test package for App Blocker

This package contains tests that use isolated configuration files
to avoid interfering with the user's actual App Blocker configuration.

Test modules:
- test_app_blocker.py: Basic functionality tests
- test_isolated_config.py: Advanced tests with isolated configuration
- test_with_utils.py: Example tests using test utilities
- test_utils.py: Utilities for creating isolated test environments
"""

from app.versioning import VERSION

__version__ = VERSION
