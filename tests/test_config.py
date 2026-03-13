"""
Unit tests for configuration module
Validates config presets, defaults, environment variable overrides, and helpers
"""

import os
from unittest.mock import patch

from config import (
    ACADEMIC_CONFIG,
    BUSINESS_CONFIG,
    QUICK_CONFIG,
    TECHNICAL_CONFIG,
    ReportConfig,
    create_custom_config,
    get_config,
)


class TestReportConfigDefaults:
    """Test configuration defaults"""

    def test_quick_config_template_is_quick(self):
        """QUICK_CONFIG must have template='quick', not 'standard' (bug fix validation)"""
        assert QUICK_CONFIG.get("template") == "quick"

    def test_default_config_template_is_standard(self):
        """Default config should use 'standard' template"""
        config = get_config("standard")
        assert config.get("template") == "standard"

    def test_business_config_template(self):
        """BUSINESS_CONFIG should have template='business'"""
        assert BUSINESS_CONFIG.get("template") == "business"

    def test_academic_config_template(self):
        """ACADEMIC_CONFIG should have template='academic'"""
        assert ACADEMIC_CONFIG.get("template") == "academic"

    def test_technical_config_template(self):
        """TECHNICAL_CONFIG should have template='technical'"""
        assert TECHNICAL_CONFIG.get("template") == "technical"

    def test_default_settings_present(self):
        """All expected default settings should exist"""
        config = ReportConfig()
        expected_keys = [
            "template", "model", "max_tokens", "temperature",
            "search_depth", "max_search_results", "output_directory",
            "enable_rate_limiting", "enable_retries", "enable_token_management",
            "enable_search_caching",
        ]
        for key in expected_keys:
            assert config.get(key) is not None, f"Missing default for '{key}'"


class TestModelConfiguration:
    """Test model name configuration and env var override"""

    def test_model_defaults_to_claude_sonnet(self):
        """Model should default to claude-sonnet-4 when MODEL_NAME env var is unset"""
        env = os.environ.copy()
        env.pop("MODEL_NAME", None)
        with patch.dict(os.environ, env, clear=True):
            config = ReportConfig()
            assert config.get("model") == "claude-sonnet-4-20250514"

    def test_model_override_via_env_var(self):
        """MODEL_NAME env var should override default model"""
        with patch.dict(os.environ, {"MODEL_NAME": "my-custom-model"}):
            config = ReportConfig()
            assert config.get("model") == "my-custom-model"
            assert config.get("token_model_name") == "my-custom-model"

    def test_custom_settings_override_env_var(self):
        """Explicit custom_settings should take precedence over env var"""
        with patch.dict(os.environ, {"MODEL_NAME": "env-model"}):
            config = ReportConfig({"model": "explicit-model"})
            assert config.get("model") == "explicit-model"


class TestConfigPresets:
    """Test configuration presets"""

    def test_get_config_returns_preset(self):
        """get_config should return matching preset"""
        for preset in ["business", "academic", "technical", "quick", "standard"]:
            config = get_config(preset)
            assert config is not None

    def test_get_config_unknown_returns_default(self):
        """Unknown preset name should return default config"""
        config = get_config("nonexistent")
        assert config is not None
        assert config.get("template") == "standard"

    def test_business_config_higher_word_count(self):
        """Business config should have higher word counts"""
        assert BUSINESS_CONFIG.get("section_word_count") == "400-600"

    def test_academic_config_more_search_results(self):
        """Academic config should have more search results"""
        assert ACADEMIC_CONFIG.get("max_search_results") == 6

    def test_quick_config_fewer_search_results(self):
        """Quick config should have fewer search results"""
        assert QUICK_CONFIG.get("max_search_results") == 3


class TestConfigMethods:
    """Test ReportConfig methods"""

    def test_get_returns_value(self):
        """get() should return stored value"""
        config = ReportConfig()
        assert config.get("template") == "standard"

    def test_get_returns_default_for_missing(self):
        """get() should return default for missing keys"""
        config = ReportConfig()
        assert config.get("nonexistent", "fallback") == "fallback"

    def test_set_updates_value(self):
        """set() should update stored value"""
        config = ReportConfig()
        config.set("template", "custom")
        assert config.get("template") == "custom"

    def test_get_prompt_template(self):
        """get_prompt_template should return template value"""
        config = ReportConfig({"template": "business"})
        assert config.get_prompt_template() == "business"

    def test_get_word_count_for_section_type(self):
        """get_word_count_for_section_type should return correct counts"""
        config = ReportConfig()
        assert config.get_word_count_for_section_type("introduction") == "150-250"
        assert config.get_word_count_for_section_type("conclusion") == "150-250"
        assert config.get_word_count_for_section_type("default") == "300-500"
        assert config.get_word_count_for_section_type("unknown") == "300-500"

    def test_custom_settings_merge(self):
        """Custom settings should override defaults, not replace them"""
        config = ReportConfig({"template": "custom", "max_tokens": 5000})
        assert config.get("template") == "custom"
        assert config.get("max_tokens") == 5000
        # Other defaults should still be present
        assert config.get("temperature") == 0
        assert config.get("output_directory") == "generated_reports"


class TestCreateCustomConfig:
    """Test factory function"""

    def test_create_custom_config(self):
        """create_custom_config should create config with kwargs"""
        config = create_custom_config(template="custom", max_tokens=3000)
        assert config.get("template") == "custom"
        assert config.get("max_tokens") == 3000
