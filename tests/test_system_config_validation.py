"""
Configuration Validation Tests

Verifies that the application fails early and clearly when required
environment variables are missing, and that defaults are applied correctly.

Test data and expected values are defined in tests/test_config.py.
Update that file to change test parameters without modifying this script.
"""

import pytest
import os
from unittest.mock import patch

# Import externalized test configuration
from tests.test_config import CONFIG, EXPECTED, MESSAGES


@pytest.mark.config_validation
class TestMissingRequiredConfig:
    """Tests for missing required configuration in production mode."""
    
    # Get required vars from config
    REQUIRED_VARS = EXPECTED["config"]["required_production_vars"]
    
    def test_missing_airtable_api_key_in_production_returns_clear_error(self):
        """
        GIVEN: APP_ENV is 'production' and AIRTABLE_API_KEY is not set
        WHEN: validate_config() is called
        THEN: Returns a list containing a clear error message about AIRTABLE_API_KEY
        """
        env_var = self.REQUIRED_VARS[0]  # AIRTABLE_API_KEY from config
        
        with patch.dict(os.environ, {
            'APP_ENV': CONFIG["environments"]["production"],
            'AIRTABLE_API_KEY': '',
            'AIRTABLE_BASE_ID': 'test_base_id',
        }, clear=False):
            # Must reimport to get fresh config values
            import importlib
            import src.config.config as config_module
            importlib.reload(config_module)
            
            errors = config_module.validate_config()
            
            assert len(errors) > 0, "Expected validation errors for missing API key"
            assert any('AIRTABLE_API_KEY' in error for error in errors), \
                f"Expected clear error about AIRTABLE_API_KEY, got: {errors}"
    
    def test_missing_airtable_base_id_in_production_returns_clear_error(self):
        """
        GIVEN: APP_ENV is 'production' and AIRTABLE_BASE_ID is not set
        WHEN: validate_config() is called
        THEN: Returns a list containing a clear error message about AIRTABLE_BASE_ID
        """
        with patch.dict(os.environ, {
            'APP_ENV': 'production',
            'AIRTABLE_API_KEY': 'test_api_key',
            'AIRTABLE_BASE_ID': '',
        }, clear=False):
            import importlib
            import src.config.config as config_module
            importlib.reload(config_module)
            
            errors = config_module.validate_config()
            
            assert len(errors) > 0, "Expected validation errors for missing base ID"
            assert any('AIRTABLE_BASE_ID' in error for error in errors), \
                f"Expected clear error about AIRTABLE_BASE_ID, got: {errors}"
    
    def test_both_airtable_vars_missing_in_production_returns_multiple_errors(self):
        """
        GIVEN: APP_ENV is 'production' and both AIRTABLE vars are missing
        WHEN: validate_config() is called
        THEN: Returns errors for BOTH missing variables (not just the first)
        """
        with patch.dict(os.environ, {
            'APP_ENV': 'production',
            'AIRTABLE_API_KEY': '',
            'AIRTABLE_BASE_ID': '',
        }, clear=False):
            import importlib
            import src.config.config as config_module
            importlib.reload(config_module)
            
            errors = config_module.validate_config()
            
            api_key_error = any('AIRTABLE_API_KEY' in e for e in errors)
            base_id_error = any('AIRTABLE_BASE_ID' in e for e in errors)
            
            assert api_key_error and base_id_error, \
                f"Expected errors for both variables, got: {errors}"


class TestDevelopmentModeDefaults:
    """Tests that development mode applies safe defaults."""
    
    def test_missing_airtable_vars_acceptable_in_development(self):
        """
        GIVEN: APP_ENV is 'development' and AIRTABLE vars are not set
        WHEN: validate_config() is called
        THEN: No errors are returned (development allows missing credentials)
        """
        with patch.dict(os.environ, {
            'APP_ENV': 'development',
            'AIRTABLE_API_KEY': '',
            'AIRTABLE_BASE_ID': '',
        }, clear=False):
            import importlib
            import src.config.config as config_module
            importlib.reload(config_module)
            
            errors = config_module.validate_config()
            
            # Filter out non-Airtable errors (like limit validation)
            airtable_errors = [e for e in errors if 'AIRTABLE' in e]
            
            assert len(airtable_errors) == 0, \
                f"Development mode should allow missing Airtable config, got: {airtable_errors}"
    
    def test_default_limit_per_source_is_reasonable(self):
        """
        GIVEN: DEFAULT_LIMIT_PER_SOURCE is not explicitly set
        WHEN: Config is loaded
        THEN: A reasonable default value is applied (not 0, not thousands)
        """
        with patch.dict(os.environ, {}, clear=False):
            # Remove the env var if it exists
            env_copy = os.environ.copy()
            if 'DEFAULT_LIMIT_PER_SOURCE' in env_copy:
                del env_copy['DEFAULT_LIMIT_PER_SOURCE']
            
            with patch.dict(os.environ, env_copy, clear=True):
                import importlib
                import src.config.config as config_module
                importlib.reload(config_module)
                
                assert 1 <= config_module.DEFAULT_LIMIT_PER_SOURCE <= 100, \
                    f"Default limit should be reasonable, got: {config_module.DEFAULT_LIMIT_PER_SOURCE}"
    
    def test_default_request_timeout_is_reasonable(self):
        """
        GIVEN: REQUEST_TIMEOUT is not explicitly set
        WHEN: Config is loaded
        THEN: A reasonable default is applied (5-120 seconds)
        """
        import importlib
        import src.config.config as config_module
        importlib.reload(config_module)
        
        assert 5 <= config_module.REQUEST_TIMEOUT <= 120, \
            f"Default timeout should be reasonable, got: {config_module.REQUEST_TIMEOUT}"


class TestConfigValidationBoundaries:
    """Tests for configuration boundary validation."""
    
    def test_negative_limit_per_source_is_rejected(self):
        """
        GIVEN: DEFAULT_LIMIT_PER_SOURCE is set to a negative value
        WHEN: validate_config() is called
        THEN: Returns an error about invalid limit
        """
        with patch.dict(os.environ, {
            'APP_ENV': 'development',
            'DEFAULT_LIMIT_PER_SOURCE': '-5',
        }, clear=False):
            import importlib
            import src.config.config as config_module
            importlib.reload(config_module)
            
            errors = config_module.validate_config()
            
            limit_errors = [e for e in errors if 'LIMIT' in e.upper()]
            assert len(limit_errors) > 0, \
                f"Expected error for negative limit, got: {errors}"
    
    def test_zero_limit_per_source_is_rejected(self):
        """
        GIVEN: DEFAULT_LIMIT_PER_SOURCE is set to 0
        WHEN: validate_config() is called
        THEN: Returns an error about invalid limit
        """
        with patch.dict(os.environ, {
            'APP_ENV': 'development',
            'DEFAULT_LIMIT_PER_SOURCE': '0',
        }, clear=False):
            import importlib
            import src.config.config as config_module
            importlib.reload(config_module)
            
            errors = config_module.validate_config()
            
            limit_errors = [e for e in errors if 'LIMIT' in e.upper()]
            assert len(limit_errors) > 0, \
                f"Expected error for zero limit, got: {errors}"
    
    def test_negative_scrape_delay_is_rejected(self):
        """
        GIVEN: SCRAPE_DELAY is set to a negative value
        WHEN: validate_config() is called
        THEN: Returns an error about invalid delay
        """
        with patch.dict(os.environ, {
            'APP_ENV': 'development',
            'SCRAPE_DELAY': '-1.0',
        }, clear=False):
            import importlib
            import src.config.config as config_module
            importlib.reload(config_module)
            
            errors = config_module.validate_config()
            
            delay_errors = [e for e in errors if 'DELAY' in e.upper()]
            assert len(delay_errors) > 0, \
                f"Expected error for negative delay, got: {errors}"


class TestConfigErrorMessages:
    """Tests that error messages are human-readable and actionable."""
    
    def test_error_messages_are_not_raw_exceptions(self):
        """
        GIVEN: Configuration validation fails
        WHEN: Errors are returned
        THEN: Error messages are sentences, not exception types or stack traces
        """
        with patch.dict(os.environ, {
            'APP_ENV': 'production',
            'AIRTABLE_API_KEY': '',
        }, clear=False):
            import importlib
            import src.config.config as config_module
            importlib.reload(config_module)
            
            errors = config_module.validate_config()
            
            for error in errors:
                # Should not contain exception class names
                assert 'Exception' not in error, f"Error looks like raw exception: {error}"
                assert 'Traceback' not in error, f"Error contains traceback: {error}"
                # Should be readable (contains spaces, reasonable length)
                assert ' ' in error, f"Error is not a sentence: {error}"
                assert len(error) > 10, f"Error is too short to be helpful: {error}"

