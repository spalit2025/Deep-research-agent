"""
Pytest configuration and shared fixtures for the test suite
"""

import asyncio
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# Add the project root to sys.path so tests can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    import asyncio

    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def setup_async_environment():
    """Ensure we have a clean async environment for each test."""
    import asyncio

    import utils.rate_limiter

    # Reset any global state
    utils.rate_limiter.reset_rate_limiter()

    # Ensure we have a fresh event loop policy
    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())

    yield

    # Clean up after test
    try:
        loop = asyncio.get_event_loop()
        if not loop.is_closed():
            loop.close()
    except Exception:
        pass


@pytest.fixture
def mock_anthropic_client():
    """Mock Anthropic client for testing"""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Mock response")]
    mock_client.messages.create.return_value = mock_response
    return mock_client


@pytest.fixture
def mock_tavily_client():
    """Mock Tavily client for testing"""
    mock_client = MagicMock()
    mock_client.search.return_value = [
        {
            "title": "Mock Search Result",
            "content": "Mock content for testing",
            "url": "https://example.com/mock",
        }
    ]
    return mock_client


@pytest.fixture
def sample_report_plan():
    """Sample report plan for testing"""
    return {
        "title": "Test Report: AI in Healthcare",
        "sections": [
            {
                "title": "Introduction",
                "description": "Overview of AI in healthcare",
                "needs_research": False,
            },
            {
                "title": "Current Applications",
                "description": "Existing AI applications in healthcare",
                "needs_research": True,
            },
            {
                "title": "Future Prospects",
                "description": "Future developments and potential",
                "needs_research": True,
            },
            {
                "title": "Conclusion",
                "description": "Summary and key insights",
                "needs_research": False,
            },
        ],
    }


@pytest.fixture
def sample_search_queries():
    """Sample search queries for testing"""
    return [
        "AI healthcare applications 2024",
        "machine learning medical diagnosis",
        "artificial intelligence patient care systems",
        "AI medical imaging analysis",
    ]


@pytest.fixture
def mock_config():
    """Mock configuration for testing"""
    return {
        "template": "business",
        "model": "claude-3-5-sonnet-20240620",
        "max_tokens": 2000,
        "temperature": 0,
        "anthropic_rate_limit_delay": 0.01,  # Fast for testing
        "tavily_rate_limit_delay": 0.01,  # Fast for testing
        "max_retries": 2,
        "retry_base_delay": 0.01,
        "enable_rate_limiting": True,
        "enable_retries": True,
        "enable_search_caching": False,  # Disable for testing
        "enable_prompt_versioning": False,  # Disable for testing
    }


@pytest.fixture
def temp_cache_dir(tmp_path):
    """Temporary directory for cache testing"""
    cache_dir = tmp_path / "test_cache"
    cache_dir.mkdir()
    return str(cache_dir)


@pytest.fixture
def temp_prompt_versions_dir(tmp_path):
    """Temporary directory for prompt versioning testing"""
    versions_dir = tmp_path / "test_prompt_versions"
    versions_dir.mkdir()
    return str(versions_dir)


@pytest.fixture(autouse=True)
def no_network_calls():
    """Prevent actual network calls during testing"""
    with patch("anthropic.Anthropic") as mock_anthropic, patch(
        "tavily.TavilyClient"
    ) as mock_tavily:
        # Configure mock responses
        mock_anthropic_instance = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(text='{"title": "Mock Report", "sections": []}')
        ]
        mock_anthropic_instance.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_anthropic_instance

        mock_tavily_instance = MagicMock()
        mock_tavily_instance.search.return_value = []
        mock_tavily.return_value = mock_tavily_instance

        yield {"anthropic": mock_anthropic_instance, "tavily": mock_tavily_instance}


# Test markers for different types of tests
pytest_plugins = []


def pytest_configure(config):
    """Configure custom pytest markers"""
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "network: mark test as requiring network access")


def pytest_collection_modifyitems(config, items):  # noqa: ARG001
    """Modify test collection to handle async tests properly"""
    for item in items:
        # Mark all async tests
        if asyncio.iscoroutinefunction(item.function):
            item.add_marker(pytest.mark.asyncio)


# Fixtures for specific test scenarios
@pytest.fixture
def malformed_json_samples():
    """Collection of malformed JSON samples for testing robustness"""
    return [
        '{"title": "Test", "sections":}',  # Missing value
        '{"title": "Test" "sections": []}',  # Missing comma
        '{title: "Test", "sections": []}',  # Unquoted key
        '{"title": "Test", "sections": [}',  # Missing bracket
        '{"title": "Test", "sections": []',  # Missing closing brace
        "This is not JSON at all",  # Not JSON
        "",  # Empty string
        "   ",  # Whitespace only
        '{"title": "Test", // comment\n"sections": []}',  # Comments
        '{"title": "Test",,, "sections": []}',  # Extra commas
    ]


@pytest.fixture
def valid_json_variations():
    """Collection of valid JSON in different formats"""
    return [
        # Clean JSON
        '{"title": "Test Report", "sections": []}',
        # Markdown wrapped
        """```json
        {"title": "Test Report", "sections": []}
        ```""",
        # With explanation text
        """Here's the structure:

        ```json
        {"title": "Test Report", "sections": []}
        ```

        This should work well.""",
        # Multiline formatted
        """
        {
            "title": "Test Report",
            "sections": []
        }
        """,
        # With extra fields
        """
        {
            "title": "Test Report",
            "sections": [],
            "author": "AI",
            "timestamp": "2024-01-01"
        }
        """,
    ]


@pytest.fixture
def rate_limit_scenarios():
    """Common rate limiting test scenarios"""
    return {
        "no_limits": {
            "anthropic_rate_limit_delay": 0.0,
            "tavily_rate_limit_delay": 0.0,
            "enable_rate_limiting": False,
        },
        "strict_limits": {
            "anthropic_rate_limit_delay": 0.1,
            "tavily_rate_limit_delay": 0.1,
            "enable_rate_limiting": True,
        },
        "anthropic_only": {
            "anthropic_rate_limit_delay": 0.1,
            "tavily_rate_limit_delay": 0.0,
            "enable_rate_limiting": True,
        },
        "production_like": {
            "anthropic_rate_limit_delay": 1.0,
            "tavily_rate_limit_delay": 0.5,
            "enable_rate_limiting": True,
            "max_retries": 3,
            "retry_base_delay": 1.0,
        },
    }
