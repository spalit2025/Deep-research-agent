"""
Unit tests for configuration module
Validates config presets, defaults, and environment variable overrides
"""

import os
from unittest.mock import patch

from config import QUICK_CONFIG, ReportConfig, get_config


class TestReportConfig:
    """Test configuration defaults and presets"""

    def test_quick_config_template_is_quick(self):
        """QUICK_CONFIG must have template='quick', not 'standard' (bug fix validation)"""
        assert QUICK_CONFIG.get("template") == "quick"

    def test_default_config_template_is_standard(self):
        """Default config should use 'standard' template"""
        config = get_config("standard")
        assert config.get("template") == "standard"

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
