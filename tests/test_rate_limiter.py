"""
Unit tests for Rate Limiter functionality
Critical component that historically breaks first due to async timing and API protection logic
"""

import asyncio
import time

import pytest

from utils.rate_limiter import (
    APICallManager,
    RateLimiter,
    RetryConfig,
    get_rate_limiter,
    reset_rate_limiter,  # Add this import
    retry_with_exponential_backoff,
)


class TestRateLimiter:
    """Test core rate limiting functionality"""

    def test_rate_limiter_initialization(self):
        """Test rate limiter initializes with correct defaults"""
        limiter = RateLimiter()

        assert limiter.anthropic_delay == 1.0
        assert limiter.tavily_delay == 0.5
        assert limiter.last_anthropic_call == 0.0
        assert limiter.last_tavily_call == 0.0

    def test_rate_limiter_custom_delays(self):
        """Test rate limiter with custom delay settings"""
        limiter = RateLimiter(anthropic_delay=2.5, tavily_delay=1.5)

        assert limiter.anthropic_delay == 2.5
        assert limiter.tavily_delay == 1.5

    @pytest.mark.asyncio
    async def test_anthropic_rate_limiting_timing(self):
        """Test that Anthropic rate limiting enforces correct delays"""
        limiter = RateLimiter(anthropic_delay=0.1)  # Short delay for testing

        # First call should be immediate
        start_time = time.time()
        await limiter.wait_for_anthropic()
        first_call_time = time.time() - start_time

        assert first_call_time < 0.05  # Should be nearly immediate

        # Second call should be delayed
        start_time = time.time()
        await limiter.wait_for_anthropic()
        second_call_time = time.time() - start_time

        assert second_call_time >= 0.1  # Should wait at least the delay
        assert second_call_time < 0.2  # But not too much longer

    @pytest.mark.asyncio
    async def test_tavily_rate_limiting_timing(self):
        """Test that Tavily rate limiting enforces correct delays"""
        limiter = RateLimiter(tavily_delay=0.1)  # Short delay for testing

        # First call should be immediate
        start_time = time.time()
        await limiter.wait_for_tavily()
        first_call_time = time.time() - start_time

        assert first_call_time < 0.05  # Should be nearly immediate

        # Second call should be delayed
        start_time = time.time()
        await limiter.wait_for_tavily()
        second_call_time = time.time() - start_time

        assert second_call_time >= 0.1  # Should wait at least the delay

    @pytest.mark.asyncio
    async def test_independent_api_timing(self):
        """Test that Anthropic and Tavily limits are independent"""
        limiter = RateLimiter(anthropic_delay=0.1, tavily_delay=0.1)

        # Call Anthropic first
        await limiter.wait_for_anthropic()

        # Tavily call should still be immediate
        start_time = time.time()
        await limiter.wait_for_tavily()
        tavily_time = time.time() - start_time

        assert tavily_time < 0.05  # Should be immediate despite Anthropic call

    @pytest.mark.asyncio
    async def test_concurrent_rate_limiting(self):
        """Test rate limiting under concurrent access"""
        limiter = RateLimiter(anthropic_delay=0.1)

        async def make_call():
            start = time.time()
            await limiter.wait_for_anthropic()
            return time.time() - start

        # Start multiple concurrent calls
        tasks = [make_call() for _ in range(3)]
        results = await asyncio.gather(*tasks)

        # First call should be immediate, subsequent ones delayed
        assert results[0] < 0.05  # First call immediate
        assert any(r >= 0.1 for r in results[1:])  # At least one delayed


class TestRetryConfig:
    """Test retry configuration"""

    def test_retry_config_defaults(self):
        """Test retry config initializes with correct defaults"""
        config = RetryConfig()

        assert config.max_retries == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 60.0

    def test_retry_config_custom_values(self):
        """Test retry config with custom values"""
        config = RetryConfig(max_retries=5, base_delay=0.5, max_delay=30.0)

        assert config.max_retries == 5
        assert config.base_delay == 0.5
        assert config.max_delay == 30.0


class TestExponentialBackoff:
    """Test exponential backoff retry mechanism"""

    @pytest.mark.asyncio
    async def test_successful_function_no_retry(self):
        """Test that successful functions don't trigger retries"""
        call_count = 0

        async def successful_func():
            nonlocal call_count
            call_count += 1
            return "success"

        config = RetryConfig(max_retries=3, base_delay=0.01)
        result = await retry_with_exponential_backoff(successful_func, config)

        assert result == "success"
        assert call_count == 1  # Called only once

    @pytest.mark.asyncio
    async def test_failing_function_retries(self):
        """Test that failing functions trigger retries"""
        call_count = 0

        async def failing_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception(f"Attempt {call_count} failed")
            return "success"

        config = RetryConfig(max_retries=3, base_delay=0.01)
        result = await retry_with_exponential_backoff(failing_func, config)

        assert result == "success"
        assert call_count == 3  # Called 3 times before success

    @pytest.mark.asyncio
    async def test_exhausted_retries_raises_exception(self):
        """Test that exhausted retries raise the last exception"""
        call_count = 0

        async def always_failing_func():
            nonlocal call_count
            call_count += 1
            raise ValueError(f"Failure {call_count}")

        config = RetryConfig(max_retries=2, base_delay=0.01)

        with pytest.raises(ValueError, match="Failure 3"):
            await retry_with_exponential_backoff(always_failing_func, config)

        assert call_count == 3  # Initial + 2 retries

    @pytest.mark.asyncio
    async def test_exponential_backoff_timing(self):
        """Test that exponential backoff increases delay correctly"""
        call_times = []

        async def timing_func():
            call_times.append(time.time())
            if len(call_times) < 3:
                raise Exception("Not yet")
            return "success"

        config = RetryConfig(max_retries=3, base_delay=0.1, max_delay=10.0)

        await retry_with_exponential_backoff(timing_func, config)

        # Check that delays approximately follow exponential pattern
        # First retry: ~0.1s, Second retry: ~0.2s
        if len(call_times) >= 3:
            delay1 = call_times[1] - call_times[0]
            delay2 = call_times[2] - call_times[1]

            assert delay1 >= 0.1
            assert delay2 >= 0.2
            assert delay2 > delay1  # Exponential increase

    @pytest.mark.asyncio
    async def test_max_delay_cap(self):
        """Test that delays are capped at max_delay"""
        call_times = []

        async def timing_func():
            call_times.append(time.time())
            raise Exception("Always fail")

        config = RetryConfig(max_retries=5, base_delay=1.0, max_delay=0.2)

        with pytest.raises(Exception):  # noqa: B017
            await retry_with_exponential_backoff(timing_func, config)

        # All delays should be capped at max_delay (0.2s)
        for i in range(1, len(call_times)):
            delay = call_times[i] - call_times[i - 1]
            assert delay <= 0.3  # Allow some tolerance

    def test_synchronous_function_retry(self):
        """Test retry mechanism with synchronous functions"""
        call_count = 0

        def sync_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception(f"Sync failure {call_count}")
            return "sync success"

        # Note: This test uses asyncio.run since retry_with_exponential_backoff
        # needs to handle both sync and async functions
        async def test_wrapper():
            config = RetryConfig(max_retries=3, base_delay=0.01)
            return await retry_with_exponential_backoff(sync_func, config)

        result = asyncio.run(test_wrapper())
        assert result == "sync success"
        assert call_count == 3


class TestAPICallManager:
    """Test the main API call manager"""

    def test_api_call_manager_initialization(self):
        """Test API call manager initializes correctly"""
        manager = APICallManager()

        assert manager.rate_limiting_enabled is True
        assert manager.retry_enabled is True
        assert isinstance(manager.rate_limiter, RateLimiter)
        assert isinstance(manager.retry_config, RetryConfig)

    def test_api_call_manager_custom_config(self):
        """Test API call manager with custom configuration"""
        config = {
            "anthropic_rate_limit_delay": 2.0,
            "tavily_rate_limit_delay": 1.0,
            "max_retries": 5,
            "enable_rate_limiting": False,
            "enable_retries": False,
        }

        manager = APICallManager(config)

        assert manager.rate_limiter.anthropic_delay == 2.0
        assert manager.rate_limiter.tavily_delay == 1.0
        assert manager.retry_config.max_retries == 5
        assert manager.rate_limiting_enabled is False
        assert manager.retry_enabled is False

    @pytest.mark.asyncio
    async def test_anthropic_api_call_with_rate_limiting(self):
        """Test Anthropic API calls with rate limiting enabled"""
        manager = APICallManager(
            {
                "anthropic_rate_limit_delay": 0.1,
                "enable_rate_limiting": True,
                "enable_retries": False,
            }
        )

        call_times = []

        async def mock_api_call():
            call_times.append(time.time())
            return "api response"

        # Make two calls
        await manager.call_anthropic_api(mock_api_call)
        await manager.call_anthropic_api(mock_api_call)

        # Second call should be delayed
        if len(call_times) >= 2:
            delay = call_times[1] - call_times[0]
            assert delay >= 0.1

    @pytest.mark.asyncio
    async def test_tavily_api_call_with_rate_limiting(self):
        """Test Tavily API calls with rate limiting enabled"""
        manager = APICallManager(
            {
                "tavily_rate_limit_delay": 0.1,
                "enable_rate_limiting": True,
                "enable_retries": False,
            }
        )

        call_times = []

        async def mock_api_call():
            call_times.append(time.time())
            return "api response"

        # Make two calls
        await manager.call_tavily_api(mock_api_call)
        await manager.call_tavily_api(mock_api_call)

        # Second call should be delayed
        if len(call_times) >= 2:
            delay = call_times[1] - call_times[0]
            assert delay >= 0.1

    @pytest.mark.asyncio
    async def test_api_call_with_retries(self):
        """Test API calls with retry mechanism enabled"""
        manager = APICallManager(
            {
                "max_retries": 2,
                "retry_base_delay": 0.01,
                "enable_rate_limiting": False,
                "enable_retries": True,
            }
        )

        call_count = 0

        async def flaky_api_call():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception(f"API error {call_count}")
            return "success"

        result = await manager.call_anthropic_api(flaky_api_call)

        assert result == "success"
        assert call_count == 3  # Initial + 2 retries

    @pytest.mark.asyncio
    async def test_api_call_disabled_features(self):
        """Test API calls with rate limiting and retries disabled"""
        manager = APICallManager(
            {"enable_rate_limiting": False, "enable_retries": False}
        )

        start_time = time.time()

        async def quick_api_call():
            return "immediate response"

        # Make multiple calls quickly
        results = []
        for _ in range(3):
            result = await manager.call_anthropic_api(quick_api_call)
            results.append(result)

        total_time = time.time() - start_time

        # Should complete very quickly without delays
        assert total_time < 0.1
        assert all(r == "immediate response" for r in results)

    @pytest.mark.asyncio
    async def test_api_call_mixed_sync_async(self):
        """Test API call manager handles both sync and async functions"""
        manager = APICallManager(
            {"enable_rate_limiting": False, "enable_retries": False}
        )

        # Async function
        async def async_func():
            return "async result"

        # Sync function
        def sync_func():
            return "sync result"

        async_result = await manager.call_anthropic_api(async_func)
        sync_result = await manager.call_anthropic_api(sync_func)

        assert async_result == "async result"
        assert sync_result == "sync result"


class TestErrorScenarios:
    """Test error handling and edge cases"""

    @pytest.mark.asyncio
    async def test_api_timeout_simulation(self):
        """Test handling of API timeouts"""
        manager = APICallManager(
            {"max_retries": 2, "retry_base_delay": 0.01, "enable_retries": True}
        )

        async def timeout_func():
            await asyncio.sleep(0.01)  # Simulate timeout
            raise asyncio.TimeoutError("API timeout")

        with pytest.raises(asyncio.TimeoutError):
            await manager.call_anthropic_api(timeout_func)

    @pytest.mark.asyncio
    async def test_network_error_simulation(self):
        """Test handling of network errors"""
        manager = APICallManager({"max_retries": 1, "retry_base_delay": 0.01})

        async def network_error_func():
            raise ConnectionError("Network unreachable")

        with pytest.raises(ConnectionError):
            await manager.call_tavily_api(network_error_func)

    @pytest.mark.asyncio
    async def test_rate_limit_exceeded_simulation(self):
        """Test handling of rate limit exceeded errors"""
        manager = APICallManager({"max_retries": 3, "retry_base_delay": 0.01})

        call_count = 0

        async def rate_limited_func():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                # Simulate rate limit error that eventually succeeds
                raise Exception("Rate limit exceeded")
            return "success after rate limit"

        result = await manager.call_anthropic_api(rate_limited_func)
        assert result == "success after rate limit"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_concurrent_api_calls_safety(self):
        """Test that concurrent API calls don't interfere with each other"""
        manager = APICallManager(
            {"anthropic_rate_limit_delay": 0.05, "enable_rate_limiting": True}
        )

        async def api_call(call_id):
            await asyncio.sleep(0.01)  # Simulate API latency
            return f"result_{call_id}"

        # Start multiple concurrent calls
        tasks = [manager.call_anthropic_api(lambda: api_call(i)) for i in range(5)]

        completed_results = await asyncio.gather(*tasks)

        # All calls should complete successfully
        assert len(completed_results) == 5
        assert all("result_" in str(r) for r in completed_results)

    def test_zero_delay_configuration(self):
        """Test rate limiter with zero delay (edge case)"""
        limiter = RateLimiter(anthropic_delay=0.0, tavily_delay=0.0)

        assert limiter.anthropic_delay == 0.0
        assert limiter.tavily_delay == 0.0

    @pytest.mark.asyncio
    async def test_very_high_delay_configuration(self):
        """Test rate limiter with very high delays"""
        # Note: Using small delays in test, but testing the logic
        limiter = RateLimiter(anthropic_delay=0.1, tavily_delay=0.1)

        start = time.time()
        await limiter.wait_for_anthropic()
        first_time = time.time() - start

        start = time.time()
        await limiter.wait_for_anthropic()
        second_time = time.time() - start

        assert first_time < 0.05  # First call immediate
        assert second_time >= 0.1  # Second call delayed


class TestIntegration:
    """Integration tests with realistic scenarios"""

    @pytest.mark.asyncio
    async def test_realistic_anthropic_usage_pattern(self):
        """Test realistic pattern of Anthropic API usage"""
        manager = APICallManager(
            {
                "anthropic_rate_limit_delay": 0.1,
                "max_retries": 2,
                "retry_base_delay": 0.01,
            }
        )

        call_count = 0

        async def mock_anthropic_call(prompt):
            nonlocal call_count
            call_count += 1

            # Simulate occasional failures
            if call_count == 2:
                raise Exception("Temporary API error")

            return f"Response to: {prompt[:20]}..."

        # Simulate report generation with multiple API calls
        prompts = [
            "Plan a report on AI in healthcare",
            "Generate search queries for AI healthcare",
            "Write introduction section",
            "Write conclusion section",
        ]

        results = []
        for prompt in prompts:
            result = await manager.call_anthropic_api(
                lambda p=prompt: mock_anthropic_call(p)
            )
            results.append(result)

        assert len(results) == 4
        assert all("Response to:" in r for r in results)

    @pytest.mark.asyncio
    async def test_realistic_tavily_usage_pattern(self):
        """Test realistic pattern of Tavily API usage"""
        manager = APICallManager({"tavily_rate_limit_delay": 0.05, "max_retries": 1})

        async def mock_tavily_search(query):
            # Simulate search results
            return [{"title": f"Result for {query}", "content": "Search content..."}]

        # Simulate multiple search queries for a report
        queries = [
            "AI healthcare applications 2024",
            "machine learning medical diagnosis",
            "AI patient outcomes research",
        ]

        search_results = []
        for query in queries:
            results = await manager.call_tavily_api(
                lambda q=query: mock_tavily_search(q)
            )
            search_results.extend(results)

        assert len(search_results) == 3
        assert all("Result for" in r["title"] for r in search_results)

    def test_get_rate_limiter_factory(self):
        """Test the rate limiter factory function"""
        config = {
            "anthropic_rate_limit_delay": 1.5,
            "tavily_rate_limit_delay": 0.8,
            "max_retries": 4,
        }

        manager = get_rate_limiter(config)

        assert isinstance(manager, APICallManager)
        assert manager.rate_limiter.anthropic_delay == 1.5
        assert manager.rate_limiter.tavily_delay == 0.8
        assert manager.retry_config.max_retries == 4

    def test_get_rate_limiter_no_config(self):
        """Test rate limiter factory with no configuration"""
        # Reset global state first
        reset_rate_limiter()

        manager = get_rate_limiter()

        assert isinstance(manager, APICallManager)
        assert manager.rate_limiter.anthropic_delay == 1.0  # Default
        assert manager.rate_limiter.tavily_delay == 0.5  # Default
