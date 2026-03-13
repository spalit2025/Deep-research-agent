"""
Unit tests for report generator
Validates _call_claude helper, API key validation, and core behavior
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from utils.token_manager import TokenManager


class TestCallClaudeHelper:
    """Test the _call_claude() helper method"""

    @pytest.fixture
    def mock_env(self):
        """Set up mock environment variables for testing"""
        with patch.dict(
            os.environ,
            {
                "ANTHROPIC_API_KEY": "test-anthropic-key",
                "TAVILY_API_KEY": "test-tavily-key",
            },
        ):
            yield

    @pytest.fixture
    def generator(self, mock_env):
        """Create a generator instance with mocked API clients"""
        with patch("report_generator.Anthropic") as mock_anthropic, \
             patch("report_generator.TavilyClient"), \
             patch("report_generator.get_rate_limiter") as mock_rl, \
             patch("report_generator.create_token_manager"), \
             patch("report_generator.create_search_cache"):
            # Set up rate limiter mock
            mock_manager = MagicMock()
            mock_rl.return_value = mock_manager

            from report_generator import ImprovedReportGenerator
            gen = ImprovedReportGenerator()

            # Replace rate limiter with async mock
            gen.rate_limiter = MagicMock()
            gen.rate_limiter.call_anthropic_api = AsyncMock()

            yield gen

    @pytest.mark.asyncio
    async def test_call_claude_returns_text(self, generator):
        """_call_claude should return response text content"""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Hello world")]
        generator.rate_limiter.call_anthropic_api.return_value = mock_response

        result = await generator._call_claude("test prompt", 100)
        assert result == "Hello world"

    @pytest.mark.asyncio
    async def test_call_claude_raises_on_empty_response(self, generator):
        """_call_claude should raise ValueError when response has no content"""
        mock_response = MagicMock()
        mock_response.content = []
        generator.rate_limiter.call_anthropic_api.return_value = mock_response

        with pytest.raises(ValueError, match="Empty response"):
            await generator._call_claude("test prompt", 100)

    @pytest.mark.asyncio
    async def test_call_claude_raises_on_none_content(self, generator):
        """_call_claude should raise ValueError when response.content is None"""
        mock_response = MagicMock()
        mock_response.content = None
        generator.rate_limiter.call_anthropic_api.return_value = mock_response

        with pytest.raises(ValueError, match="Empty response"):
            await generator._call_claude("test prompt", 100)


class TestAPIKeyValidation:
    """Test API key validation happens before client construction"""

    def test_missing_anthropic_key_raises(self):
        """Should raise ValueError when ANTHROPIC_API_KEY is missing"""
        with patch.dict(os.environ, {"TAVILY_API_KEY": "test"}, clear=True):
            with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
                from report_generator import ImprovedReportGenerator
                ImprovedReportGenerator()

    def test_missing_tavily_key_raises(self):
        """Should raise ValueError when TAVILY_API_KEY is missing"""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test"}, clear=True):
            with pytest.raises(ValueError, match="TAVILY_API_KEY"):
                from report_generator import ImprovedReportGenerator
                ImprovedReportGenerator()


class TestTokenManagerBugFixes:
    """Test token_manager bug fixes"""

    def test_estimate_tokens_returns_int(self):
        """estimate_tokens must return int, not float"""
        tm = TokenManager()
        result = tm.estimate_tokens("hello world test string")
        assert isinstance(result, int)

    def test_token_warning_critical_before_high(self):
        """Usage >95% should show CRITICAL, not just WARNING"""
        from utils.token_manager import TokenUsage

        tm = TokenManager()

        # 96% usage should trigger CRITICAL
        usage = TokenUsage(
            prompt_tokens=96000,
            sources_tokens=0,
            total_tokens=96000,
            context_limit=100000,
            usage_percentage=96.0,
        )
        report = tm.get_usage_report(usage)
        assert "CRITICAL" in report

        # 92% should trigger WARNING but not CRITICAL
        usage.usage_percentage = 92.0
        report = tm.get_usage_report(usage)
        assert "WARNING" in report
        assert "CRITICAL" not in report
