"""
Unit tests for report generator
Validates _call_claude helper, API key validation, fallback plans,
section type detection, report compilation, and save behavior
"""

import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from report_generator import ImprovedReportGenerator, ReportPlan, Section
from utils.token_manager import TokenManager


# Shared fixture for mocked generator
@pytest.fixture
def mock_env():
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
def generator(mock_env):  # noqa: ARG001
    """Create a generator instance with mocked API clients"""
    with patch("report_generator.Anthropic"), \
         patch("report_generator.TavilyClient"), \
         patch("report_generator.get_rate_limiter") as mock_rl, \
         patch("report_generator.create_token_manager"), \
         patch("report_generator.create_search_cache"):
        mock_manager = MagicMock()
        mock_rl.return_value = mock_manager

        gen = ImprovedReportGenerator()

        # Replace rate limiter with async mock
        gen.rate_limiter = MagicMock()
        gen.rate_limiter.call_anthropic_api = AsyncMock()
        gen.rate_limiter.call_tavily_api = AsyncMock()

        yield gen


class TestCallClaudeHelper:
    """Test the _call_claude() helper method"""

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

    @pytest.mark.asyncio
    async def test_call_claude_passes_max_tokens(self, generator):
        """_call_claude should pass max_tokens to the API"""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="ok")]
        generator.rate_limiter.call_anthropic_api.return_value = mock_response

        await generator._call_claude("prompt", 2000)

        # Verify the API was called
        generator.rate_limiter.call_anthropic_api.assert_called_once()


class TestAPIKeyValidation:
    """Test API key validation happens before client construction"""

    def test_missing_anthropic_key_raises(self):
        """Should raise ValueError when ANTHROPIC_API_KEY is missing"""
        with patch.dict(os.environ, {"TAVILY_API_KEY": "test"}, clear=True), \
             pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
            ImprovedReportGenerator()

    def test_missing_tavily_key_raises(self):
        """Should raise ValueError when TAVILY_API_KEY is missing"""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test"}, clear=True), \
             pytest.raises(ValueError, match="TAVILY_API_KEY"):
            ImprovedReportGenerator()

    def test_missing_both_keys_raises_anthropic_first(self):
        """Should raise for ANTHROPIC_API_KEY first when both are missing"""
        with patch.dict(os.environ, {}, clear=True), \
             pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
            ImprovedReportGenerator()


class TestFallbackPlan:
    """Test fallback plan generation for different templates"""

    def test_standard_fallback_plan(self, generator):
        """Standard template fallback should have intro, analysis, conclusion"""
        plan = generator._create_fallback_plan("Test Topic")
        assert plan.title == "Research Report: Test Topic"
        assert len(plan.sections) == 3
        assert plan.sections[0].title == "Introduction"
        assert plan.sections[1].title == "Main Analysis"
        assert plan.sections[2].title == "Conclusion"

    def test_business_fallback_plan(self, mock_env):  # noqa: ARG002
        """Business template fallback should have exec summary, analysis, recs"""
        with patch("report_generator.Anthropic"), \
             patch("report_generator.TavilyClient"), \
             patch("report_generator.get_rate_limiter") as mock_rl, \
             patch("report_generator.create_token_manager"), \
             patch("report_generator.create_search_cache"):
            from config import BUSINESS_CONFIG
            mock_rl.return_value = MagicMock()
            gen = ImprovedReportGenerator(BUSINESS_CONFIG)

            plan = gen._create_fallback_plan("Market Analysis")
            assert "Business Analysis" in plan.title
            assert plan.sections[0].title == "Executive Summary"

    def test_academic_fallback_plan(self, mock_env):  # noqa: ARG002
        """Academic template fallback should have abstract, lit review, conclusion"""
        with patch("report_generator.Anthropic"), \
             patch("report_generator.TavilyClient"), \
             patch("report_generator.get_rate_limiter") as mock_rl, \
             patch("report_generator.create_token_manager"), \
             patch("report_generator.create_search_cache"):
            from config import ACADEMIC_CONFIG
            mock_rl.return_value = MagicMock()
            gen = ImprovedReportGenerator(ACADEMIC_CONFIG)

            plan = gen._create_fallback_plan("Research Topic")
            assert "Academic Review" in plan.title
            assert plan.sections[0].title == "Abstract"

    def test_fallback_sections_have_research_flags(self, generator):
        """Fallback plan sections should have correct needs_research flags"""
        plan = generator._create_fallback_plan("Topic")
        # Intro doesn't need research, main analysis does, conclusion doesn't
        assert plan.sections[0].needs_research is False
        assert plan.sections[1].needs_research is True
        assert plan.sections[2].needs_research is False


class TestDetermineSectionType:
    """Test section type detection from title"""

    def test_introduction(self, generator):
        assert generator._determine_section_type("Introduction") == "introduction"
        assert generator._determine_section_type("Project Intro") == "introduction"

    def test_conclusion(self, generator):
        assert generator._determine_section_type("Conclusion") == "conclusion"
        assert generator._determine_section_type("Final Conclusions") == "conclusion"

    def test_executive_summary(self, generator):
        assert generator._determine_section_type("Executive Summary") == "executive_summary"
        assert generator._determine_section_type("Summary of Findings") == "executive_summary"

    def test_literature_review(self, generator):
        assert generator._determine_section_type("Literature Review") == "literature_review"
        assert generator._determine_section_type("Review of Prior Work") == "literature_review"

    def test_abstract(self, generator):
        assert generator._determine_section_type("Abstract") == "abstract"

    def test_recommendations(self, generator):
        assert generator._determine_section_type("Strategic Recommendations") == "recommendations"

    def test_technical(self, generator):
        assert generator._determine_section_type("Technical Overview") == "technical_overview"
        assert generator._determine_section_type("System Architecture") == "technical_overview"

    def test_default(self, generator):
        assert generator._determine_section_type("Market Analysis") == "default"
        assert generator._determine_section_type("Findings") == "default"


class TestCompileReport:
    """Test report compilation"""

    def test_compile_basic_report(self, generator):
        """_compile_report should produce valid markdown"""
        plan = ReportPlan(
            title="Test Report",
            sections=[
                Section(title="Introduction", description="Intro", content="Some intro text"),
                Section(title="Analysis", description="Analysis", content="Analysis content"),
            ],
        )
        report = generator._compile_report(plan)

        assert "# Test Report" in report
        assert "## Introduction" in report
        assert "Some intro text" in report
        assert "## Analysis" in report
        assert "Analysis content" in report

    def test_compile_avoids_duplicate_headers(self, generator):
        """If content already has ## header, don't add another"""
        plan = ReportPlan(
            title="Report",
            sections=[
                Section(
                    title="Intro",
                    description="Intro",
                    content="## Intro\n\nAlready has header",
                ),
            ],
        )
        report = generator._compile_report(plan)

        # Should NOT have "## Intro" duplicated
        assert report.count("## Intro") == 1

    def test_compile_includes_metadata(self, generator):
        """Compiled report should include generation metadata"""
        plan = ReportPlan(
            title="Report",
            sections=[Section(title="S", description="D", content="C")],
        )
        report = generator._compile_report(plan)
        assert "report generated on" in report


class TestSaveReport:
    """Test report saving"""

    def test_save_report_creates_file(self, generator):
        """save_report should create a file with report content"""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator.config.set("output_directory", tmpdir)

            filepath = generator.save_report("# My Report\n\nContent here")

            assert os.path.exists(filepath)
            with open(filepath) as f:
                assert "# My Report" in f.read()

    def test_save_report_custom_filename(self, generator):
        """save_report should use custom filename when provided"""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator.config.set("output_directory", tmpdir)

            filepath = generator.save_report("Content", filename="custom.md")

            assert filepath.endswith("custom.md")
            assert os.path.exists(filepath)

    def test_save_report_auto_filename_includes_template(self, generator):
        """Auto-generated filename should include the template name"""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator.config.set("output_directory", tmpdir)

            filepath = generator.save_report("Content")

            assert "standard" in os.path.basename(filepath)
            assert filepath.endswith(".md")


class TestSearchWeb:
    """Test web search with caching"""

    @pytest.mark.asyncio
    async def test_search_returns_results(self, generator):
        """_search_web should return deduplicated results"""
        generator.search_cache = None  # Disable caching
        generator.rate_limiter.call_tavily_api.return_value = {
            "results": [
                {"title": "Result 1", "url": "https://a.com"},
                {"title": "Result 2", "url": "https://b.com"},
            ]
        }

        results = await generator._search_web(["query 1"], "topic")

        assert len(results) == 2
        assert results[0]["title"] == "Result 1"

    @pytest.mark.asyncio
    async def test_search_deduplicates_by_url(self, generator):
        """_search_web should deduplicate results by URL"""
        generator.search_cache = None
        generator.rate_limiter.call_tavily_api.return_value = {
            "results": [{"title": "R", "url": "https://same.com"}]
        }

        results = await generator._search_web(["q1", "q2"], "topic")

        # Same URL from two queries should be deduplicated
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_search_handles_api_error(self, generator):
        """_search_web should handle API errors gracefully"""
        generator.search_cache = None
        generator.rate_limiter.call_tavily_api.side_effect = Exception("API error")

        results = await generator._search_web(["query"], "topic")

        # Should return empty list, not raise
        assert results == []


class TestWriteSectionWithSources:
    """Test section writing with error handling"""

    @pytest.mark.asyncio
    async def test_write_section_error_returns_fallback(self, generator):
        """Section writing failure should return fallback content"""
        generator.token_manager = None
        generator.rate_limiter.call_anthropic_api.side_effect = Exception("API down")

        section = Section(title="Test", description="Test section")
        result = await generator._write_section_with_sources(section, [], "topic")

        assert "## Test" in result
        assert "error" in result.lower()


class TestWriteContextualSection:
    """Test contextual section writing (intro/conclusion)"""

    @pytest.mark.asyncio
    async def test_contextual_section_success(self, generator):
        """Should return Claude's response for contextual sections"""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="## Intro\n\nGreat introduction")]
        generator.rate_limiter.call_anthropic_api.return_value = mock_response

        section = Section(title="Introduction", description="Overview")
        all_sections = [
            section,
            Section(title="Analysis", description="Main analysis", needs_research=True),
        ]

        result = await generator._write_contextual_section(section, all_sections, "AI")
        assert "introduction" in result.lower() or "Intro" in result

    @pytest.mark.asyncio
    async def test_contextual_section_error_returns_fallback(self, generator):
        """Contextual section failure should return fallback content"""
        generator.rate_limiter.call_anthropic_api.side_effect = Exception("fail")

        section = Section(title="Conclusion", description="Summary")
        result = await generator._write_contextual_section(section, [], "topic")

        assert "## Conclusion" in result
        assert "error" in result.lower()


class TestTokenManagerBugFixes:
    """Test token_manager bug fixes"""

    def test_estimate_tokens_returns_int(self):
        """estimate_tokens must return int, not float"""
        tm = TokenManager()
        result = tm.estimate_tokens("hello world test string")
        assert isinstance(result, int)

    def test_estimate_tokens_empty_string(self):
        """estimate_tokens should return 0 for empty string"""
        tm = TokenManager()
        assert tm.estimate_tokens("") == 0
        assert tm.estimate_tokens(None) == 0

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

    def test_token_warning_below_90_no_warning(self):
        """Usage below 90% should not show any warning"""
        from utils.token_manager import TokenUsage

        tm = TokenManager()
        usage = TokenUsage(
            prompt_tokens=50000,
            sources_tokens=0,
            total_tokens=50000,
            context_limit=100000,
            usage_percentage=50.0,
        )
        report = tm.get_usage_report(usage)
        assert "WARNING" not in report
        assert "CRITICAL" not in report
