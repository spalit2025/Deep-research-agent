"""
Structured Logging and Metrics for Production Observability
Provides correlation IDs, structured logging, metrics collection, and alerting capabilities
"""

from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from functools import wraps
from threading import local
import time
import traceback
from typing import Any, Dict, List, Optional, Union
import uuid

import structlog

# Configure structlog once at module level (not per-logger instance)
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="ISO"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)


class LogLevel(Enum):
    """Structured log levels"""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ComponentType(Enum):
    """System components for structured logging"""

    REPORT_GENERATOR = "report_generator"
    JSON_PARSER = "json_parser"
    RATE_LIMITER = "rate_limiter"
    SEARCH_CACHE = "search_cache"
    TOKEN_MANAGER = "token_manager"
    PROMPT_LOADER = "prompt_loader"
    API_CLIENT = "api_client"


class OperationType(Enum):
    """Types of operations for metrics"""

    REPORT_GENERATION = "report_generation"
    JSON_PARSING = "json_parsing"
    API_CALL = "api_call"
    CACHE_OPERATION = "cache_operation"
    TOKEN_OPTIMIZATION = "token_optimization"
    SEARCH_QUERY = "search_query"
    PROMPT_LOADING = "prompt_loading"


@dataclass
class LogContext:
    """Structured context for logging"""

    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    report_id: Optional[str] = None
    operation_type: Optional[OperationType] = None
    component: Optional[ComponentType] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for structured logging"""
        return {
            k: v.value if isinstance(v, Enum) else v
            for k, v in asdict(self).items()
            if v is not None
        }


@dataclass
class MetricEvent:
    """A single metric event"""

    name: str
    value: Union[int, float]
    timestamp: float = field(default_factory=time.time)
    tags: Dict[str, str] = field(default_factory=dict)
    context: Optional[LogContext] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for export"""
        result = {
            "name": self.name,
            "value": self.value,
            "timestamp": self.timestamp,
            "tags": self.tags,
        }
        if self.context:
            result["context"] = self.context.to_dict()
        return result


@dataclass
class PerformanceMetrics:
    """Performance tracking for operations"""

    operation_count: int = 0
    total_duration: float = 0.0
    success_count: int = 0
    error_count: int = 0
    avg_duration: float = 0.0
    success_rate: float = 0.0
    last_update: float = field(default_factory=time.time)

    def record_success(self, duration: float):
        """Record a successful operation"""
        self.operation_count += 1
        self.success_count += 1
        self.total_duration += duration
        self._update_averages()

    def record_error(self, duration: float):
        """Record a failed operation"""
        self.operation_count += 1
        self.error_count += 1
        self.total_duration += duration
        self._update_averages()

    def _update_averages(self):
        """Update calculated averages"""
        if self.operation_count > 0:
            self.avg_duration = self.total_duration / self.operation_count
            self.success_rate = self.success_count / self.operation_count
        self.last_update = time.time()


class StructuredLogger:
    """Structured logger with correlation IDs and context.

    Uses structlog.bind() to attach component info, rather than
    reconfiguring structlog globally on each instantiation.
    """

    def __init__(self, component: ComponentType):
        self.component = component
        self._local = local()
        self.logger = structlog.get_logger(component.value).bind(
            component=component.value
        )

    def set_context(self, context: LogContext):
        """Set logging context for current thread"""
        self._local.context = context

    def get_context(self) -> Optional[LogContext]:
        """Get current logging context"""
        return getattr(self._local, "context", None)

    def _with_context(self, kwargs: dict) -> dict:
        """Merge thread-local context into log kwargs"""
        ctx = self.get_context()
        if ctx:
            return {**ctx.to_dict(), **kwargs}
        return kwargs

    def debug(self, message: str, **kwargs):
        """Log debug message with context"""
        self.logger.debug(message, **self._with_context(kwargs))

    def info(self, message: str, **kwargs):
        """Log info message with context"""
        self.logger.info(message, **self._with_context(kwargs))

    def warning(self, message: str, **kwargs):
        """Log warning message with context"""
        self.logger.warning(message, **self._with_context(kwargs))

    def error(self, message: str, error: Optional[Exception] = None, **kwargs):
        """Log error message with context and exception details"""
        if error:
            kwargs["error_type"] = type(error).__name__
            kwargs["error_message"] = str(error)
            kwargs["traceback"] = traceback.format_exc()
        self.logger.error(message, **self._with_context(kwargs))

    def critical(self, message: str, **kwargs):
        """Log critical message with context"""
        self.logger.critical(message, **self._with_context(kwargs))


class MetricsCollector:
    """Collects and aggregates performance metrics"""

    def __init__(self):
        self.metrics: Dict[str, PerformanceMetrics] = {}
        self.events: List[MetricEvent] = []
        self.counters: Dict[str, int] = {}
        self.gauges: Dict[str, float] = {}

    def record_operation(
        self,
        operation: str,
        duration: float,
        success: bool,
        context: Optional[LogContext] = None,
        **tags,
    ):
        """Record an operation's performance"""
        if operation not in self.metrics:
            self.metrics[operation] = PerformanceMetrics()

        if success:
            self.metrics[operation].record_success(duration)
        else:
            self.metrics[operation].record_error(duration)

        # Record as event
        event = MetricEvent(
            name=f"{operation}_duration",
            value=duration,
            tags={**tags, "success": str(success)},
            context=context,
        )
        self.events.append(event)

    def increment_counter(
        self, name: str, value: int = 1, context: Optional[LogContext] = None, **tags
    ):
        """Increment a counter metric"""
        self.counters[name] = self.counters.get(name, 0) + value

        event = MetricEvent(name=name, value=value, tags=tags, context=context)
        self.events.append(event)

    def set_gauge(
        self, name: str, value: float, context: Optional[LogContext] = None, **tags
    ):
        """Set a gauge metric"""
        self.gauges[name] = value

        event = MetricEvent(name=name, value=value, tags=tags, context=context)
        self.events.append(event)

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary for all operations"""
        summary = {}
        for operation, metrics in self.metrics.items():
            summary[operation] = {
                "total_operations": metrics.operation_count,
                "success_rate": metrics.success_rate,
                "avg_duration_ms": metrics.avg_duration * 1000,
                "total_errors": metrics.error_count,
            }
        return summary

    def export_metrics(self) -> List[Dict[str, Any]]:
        """Export all metrics for external systems"""
        return [event.to_dict() for event in self.events]

    def clear_events(self):
        """Clear stored events (after export)"""
        self.events.clear()


class ObservabilityManager:
    """Central manager for structured logging and metrics"""

    def __init__(
        self, enable_metrics: bool = True, enable_structured_logging: bool = True
    ):
        self.enable_metrics = enable_metrics
        self.enable_structured_logging = enable_structured_logging

        # Initialize components
        if enable_metrics:
            self.metrics = MetricsCollector()

        self._loggers: Dict[ComponentType, StructuredLogger] = {}

        # Performance thresholds for alerting
        self.thresholds = {
            "api_call_duration": 10.0,  # seconds
            "json_parse_duration": 1.0,  # seconds
            "cache_miss_rate": 0.8,  # 80%
            "error_rate": 0.1,  # 10%
        }

    def get_logger(self, component: ComponentType) -> StructuredLogger:
        """Get structured logger for component"""
        if component not in self._loggers:
            self._loggers[component] = StructuredLogger(component)
        return self._loggers[component]

    def create_context(
        self, operation_type: OperationType, component: ComponentType, **kwargs
    ) -> LogContext:
        """Create new logging context"""
        # Filter kwargs to only include LogContext fields
        valid_fields = {"user_id", "session_id", "report_id"}
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in valid_fields}

        return LogContext(
            operation_type=operation_type, component=component, **filtered_kwargs
        )

    @contextmanager
    def operation_context(
        self,
        operation_type: OperationType,
        component: ComponentType,
        operation_name: str,
        **context_kwargs,
    ):
        """Context manager for tracking operations with logging and metrics"""
        context = self.create_context(operation_type, component, **context_kwargs)
        logger = self.get_logger(component)

        # Set context for this operation
        logger.set_context(context)

        start_time = time.time()
        success = False
        error = None

        try:
            logger.info(
                f"Starting {operation_name}", operation=operation_name, **context_kwargs
            )
            yield context
            success = True

        except Exception as e:
            error = e
            logger.error(
                f"Operation failed: {operation_name}", error=e, operation=operation_name
            )
            raise

        finally:
            duration = time.time() - start_time

            # Log completion
            if success:
                logger.info(
                    f"Completed {operation_name}",
                    operation=operation_name,
                    duration_ms=duration * 1000,
                    success=True,
                )

            # Record metrics
            if self.enable_metrics:
                self.metrics.record_operation(
                    operation_name, duration, success, context
                )

                # Check thresholds and alert
                self._check_thresholds(operation_name, duration, success)

    def _check_thresholds(self, operation: str, duration: float, success: bool):
        """Check performance thresholds and log alerts"""
        alerts = []

        # Duration thresholds
        for threshold_key, threshold_value in self.thresholds.items():
            if threshold_key.endswith("_duration") and operation in threshold_key:
                if duration > threshold_value:
                    alerts.append(
                        f"Slow operation: {operation} took {duration:.2f}s (threshold: {threshold_value}s)"
                    )

        # Error rate threshold
        if not success:
            if operation in self.metrics.metrics:
                error_rate = 1 - self.metrics.metrics[operation].success_rate
                if error_rate > self.thresholds.get("error_rate", 0.1):
                    alerts.append(f"High error rate: {operation} at {error_rate:.1%}")

        # Log alerts
        for alert in alerts:
            logger = self.get_logger(ComponentType.REPORT_GENERATOR)
            logger.warning("Performance threshold exceeded", alert=alert)

    def get_health_status(self) -> Dict[str, Any]:
        """Get overall system health status"""
        if not self.enable_metrics:
            return {"status": "metrics_disabled"}

        summary = self.metrics.get_performance_summary()

        # Calculate overall health
        overall_error_rate = 0
        total_operations = 0

        for metrics in summary.values():
            if metrics["total_operations"] > 0:
                total_operations += metrics["total_operations"]
                overall_error_rate += metrics["total_errors"]

        overall_error_rate = overall_error_rate / max(total_operations, 1)

        status = "healthy"
        if overall_error_rate > 0.1:  # 10% error rate
            status = "degraded"
        if overall_error_rate > 0.3:  # 30% error rate
            status = "unhealthy"

        return {
            "status": status,
            "overall_error_rate": overall_error_rate,
            "total_operations": total_operations,
            "component_metrics": summary,
            "timestamp": datetime.now().isoformat(),
        }


# Global observability manager
_observability_manager = None


def get_observability_manager() -> ObservabilityManager:
    """Get global observability manager"""
    global _observability_manager
    if _observability_manager is None:
        _observability_manager = ObservabilityManager()
    return _observability_manager


def get_logger(component: ComponentType) -> StructuredLogger:
    """Quick access to structured logger"""
    return get_observability_manager().get_logger(component)


def timed_operation(
    operation_name: str, component: ComponentType, operation_type: OperationType
):
    """Decorator for automatic operation timing and logging"""

    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            obs = get_observability_manager()
            with obs.operation_context(operation_type, component, operation_name):
                return await func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            obs = get_observability_manager()
            with obs.operation_context(operation_type, component, operation_name):
                return func(*args, **kwargs)

        # Return appropriate wrapper based on function type
        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


# Convenience functions for common patterns
def log_api_call(api_name: str, success: bool, duration: float, **kwargs):
    """Log API call with standard format"""
    logger = get_logger(ComponentType.API_CLIENT)
    metrics = get_observability_manager().metrics

    logger.info(
        "API call completed",
        api=api_name,
        success=success,
        duration_ms=duration * 1000,
        **kwargs,
    )

    metrics.record_operation(f"api_call_{api_name}", duration, success)


def log_json_parsing(success: bool, text_length: int, duration: float, parse_type: str):
    """Log JSON parsing with standard format"""
    logger = get_logger(ComponentType.JSON_PARSER)
    metrics = get_observability_manager().metrics

    logger.info(
        "JSON parsing attempt",
        success=success,
        text_length=text_length,
        parse_type=parse_type,
        duration_ms=duration * 1000,
    )

    metrics.record_operation("json_parsing", duration, success, parse_type=parse_type)
