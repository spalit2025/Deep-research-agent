"""
Rate limiting utilities for API calls
Prevents hitting rate limits with built-in delays and retry mechanisms
"""

import asyncio
from functools import wraps
import logging
import time
from typing import Any, Callable, Dict

from .observability import ComponentType, OperationType, get_logger, timed_operation

# Structured logger
logger = get_logger(ComponentType.RATE_LIMITER)

# Keep fallback for compatibility
_fallback_logger = logging.getLogger(__name__)


class RateLimiter:
    """Rate limiter with configurable delays and retry mechanisms"""

    def __init__(self, anthropic_delay: float = 1.0, tavily_delay: float = 0.5):
        """
        Initialize rate limiter

        Args:
            anthropic_delay: Delay between Anthropic API calls (seconds)
            tavily_delay: Delay between Tavily API calls (seconds)
        """
        self.anthropic_delay = anthropic_delay
        self.tavily_delay = tavily_delay
        self.last_anthropic_call = 0.0
        self.last_tavily_call = 0.0

    @timed_operation(
        "rate_limit_wait", ComponentType.RATE_LIMITER, OperationType.API_CALL
    )
    async def wait_for_anthropic(self):
        """Ensure minimum delay between Anthropic API calls"""
        current_time = time.time()
        time_since_last = current_time - self.last_anthropic_call

        context = {
            "api": "anthropic",
            "time_since_last": time_since_last,
            "required_delay": self.anthropic_delay,
        }

        if time_since_last < self.anthropic_delay:
            wait_time = self.anthropic_delay - time_since_last
            logger.info(
                "Rate limiting active for Anthropic API", wait_time=wait_time, **context
            )
            await asyncio.sleep(wait_time)
        else:
            logger.debug("No rate limiting needed for Anthropic API", **context)

        self.last_anthropic_call = time.time()

    @timed_operation(
        "rate_limit_wait", ComponentType.RATE_LIMITER, OperationType.API_CALL
    )
    async def wait_for_tavily(self):
        """Ensure minimum delay between Tavily API calls"""
        current_time = time.time()
        time_since_last = current_time - self.last_tavily_call

        context = {
            "api": "tavily",
            "time_since_last": time_since_last,
            "required_delay": self.tavily_delay,
        }

        if time_since_last < self.tavily_delay:
            wait_time = self.tavily_delay - time_since_last
            logger.info(
                "Rate limiting active for Tavily API", wait_time=wait_time, **context
            )
            await asyncio.sleep(wait_time)
        else:
            logger.debug("No rate limiting needed for Tavily API", **context)

        self.last_tavily_call = time.time()


class RetryConfig:
    """Configuration for retry mechanisms"""

    def __init__(
        self, max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 60.0
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay


@timed_operation("api_retry", ComponentType.RATE_LIMITER, OperationType.API_CALL)
async def retry_with_exponential_backoff(
    func: Callable, retry_config: RetryConfig, *args, **kwargs
) -> Any:
    """
    Execute function with exponential backoff retry

    Args:
        func: Function to execute
        retry_config: Retry configuration
        *args, **kwargs: Arguments for the function

    Returns:
        Function result

    Raises:
        Exception: If all retries are exhausted
    """
    function_name = getattr(func, "__name__", str(func))
    last_exception = None

    logger.info(
        "Starting API call with retry logic",
        function=function_name,
        max_retries=retry_config.max_retries,
        base_delay=retry_config.base_delay,
    )

    for attempt in range(retry_config.max_retries + 1):
        context = {
            "function": function_name,
            "attempt": attempt + 1,
            "max_retries": retry_config.max_retries,
        }

        try:
            logger.debug("Attempting API call", **context)

            result = func(*args, **kwargs)
            if asyncio.iscoroutine(result):
                result = await result

            logger.info("API call successful", **context)
            return result

        except Exception as e:
            last_exception = e

            if attempt == retry_config.max_retries:
                logger.error("All retries exhausted", error=e, **context)
                raise e

            # Calculate exponential backoff delay
            delay = min(retry_config.base_delay * (2**attempt), retry_config.max_delay)

            logger.warning(
                "API call failed, retrying",
                error=e,
                backoff_delay=delay,
                will_retry=True,
                **context,
            )

            await asyncio.sleep(delay)

    raise last_exception


class APICallManager:
    """Manages API calls with rate limiting and retry mechanisms"""

    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize API call manager

        Args:
            config: Configuration dictionary with rate limiting settings
        """
        self.config = config or {}

        # Rate limiting configuration
        anthropic_delay = self.config.get("anthropic_rate_limit_delay", 1.0)
        tavily_delay = self.config.get("tavily_rate_limit_delay", 0.5)
        self.rate_limiter = RateLimiter(anthropic_delay, tavily_delay)

        # Retry configuration
        max_retries = self.config.get("max_retries", 3)
        base_delay = self.config.get("retry_base_delay", 1.0)
        max_delay = self.config.get("retry_max_delay", 60.0)
        self.retry_config = RetryConfig(max_retries, base_delay, max_delay)

        # Enable/disable rate limiting
        self.rate_limiting_enabled = self.config.get("enable_rate_limiting", True)
        self.retry_enabled = self.config.get("enable_retries", True)

    async def call_anthropic_api(self, api_func: Callable, *args, **kwargs) -> Any:
        """
        Make a rate-limited call to Anthropic API

        Args:
            api_func: The API function to call
            *args, **kwargs: Arguments for the API function

        Returns:
            API response
        """
        if self.rate_limiting_enabled:
            await self.rate_limiter.wait_for_anthropic()

        if self.retry_enabled:
            return await retry_with_exponential_backoff(
                api_func, self.retry_config, *args, **kwargs
            )
        else:
            result = api_func(*args, **kwargs)
            if asyncio.iscoroutine(result):
                result = await result
            return result

    async def call_tavily_api(self, api_func: Callable, *args, **kwargs) -> Any:
        """
        Make a rate-limited call to Tavily API

        Args:
            api_func: The API function to call
            *args, **kwargs: Arguments for the API function

        Returns:
            API response
        """
        if self.rate_limiting_enabled:
            await self.rate_limiter.wait_for_tavily()

        if self.retry_enabled:
            return await retry_with_exponential_backoff(
                api_func, self.retry_config, *args, **kwargs
            )
        else:
            result = api_func(*args, **kwargs)
            if asyncio.iscoroutine(result):
                result = await result
            return result


# Decorator for automatic rate limiting
def rate_limited_anthropic(manager: APICallManager):
    """Decorator for Anthropic API calls"""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await manager.call_anthropic_api(func, *args, **kwargs)

        return wrapper

    return decorator


def rate_limited_tavily(manager: APICallManager):
    """Decorator for Tavily API calls"""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await manager.call_tavily_api(func, *args, **kwargs)

        return wrapper

    return decorator


# Global rate limiter instance
_global_rate_limiter = None


def get_rate_limiter(config: Dict[str, Any] = None) -> APICallManager:
    """Get or create global rate limiter instance"""
    global _global_rate_limiter
    if _global_rate_limiter is None:
        _global_rate_limiter = APICallManager(config)
    return _global_rate_limiter


def reset_rate_limiter():
    """Reset global rate limiter (useful for testing)"""
    global _global_rate_limiter
    _global_rate_limiter = None
