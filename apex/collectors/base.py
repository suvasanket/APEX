"""Base collector interfaces, data structures, and resilience utilities for APEX."""

from abc import ABC, abstractmethod
import asyncio
from datetime import date
from functools import wraps
import hashlib
import time
from typing import Any, Callable, Coroutine, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from apex.models.fare import FareObservation


class CollectorResult(BaseModel):
    """Encapsulates the output of a scraper run with raw provenance."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=False)

    observations: list[FareObservation] = Field(
        default_factory=list,
        description="Parsed canonical FareObservation instances",
    )
    raw_payload: str = Field(
        ...,
        description="Raw response string (JSON, HTML, or API payload)",
    )
    raw_hash: str = Field(
        ...,
        description="SHA-256 hex digest of the raw_payload",
        pattern=r"^[a-f0-9]{64}$",
    )
    execution_meta: dict[str, Any] = Field(
        default_factory=dict,
        description="Metadata including timing, HTTP status, route, and error diagnostics",
    )

    @classmethod
    def create(
        cls,
        observations: list[FareObservation],
        raw_payload: str,
        execution_meta: Optional[dict[str, Any]] = None,
        raw_hash: Optional[str] = None,
    ) -> "CollectorResult":
        """Factory method computing SHA-256 automatically if not supplied."""
        computed_hash = raw_hash or hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()
        return cls(
            observations=observations,
            raw_payload=raw_payload,
            raw_hash=computed_hash,
            execution_meta=execution_meta or {},
        )

    @model_validator(mode="after")
    def verify_payload_hash(self) -> "CollectorResult":
        expected_hash = hashlib.sha256(self.raw_payload.encode("utf-8")).hexdigest()
        if self.raw_hash.lower() != expected_hash:
            raise ValueError(
                f"raw_hash does not match SHA-256 of raw_payload: "
                f"expected {expected_hash}, got {self.raw_hash}"
            )
        return self


class CircuitBreakerOpenException(Exception):
    """Raised when an operation is attempted on an open circuit breaker."""

    def __init__(self, service_name: str, retry_after_seconds: float):
        self.service_name = service_name
        self.retry_after_seconds = retry_after_seconds
        super().__init__(
            f"Circuit breaker is OPEN for {service_name}. "
            f"Retry after {retry_after_seconds:.1f}s"
        )


class CircuitBreakerState:
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    """Safety circuit breaker protecting remote targets and avoiding IP bans.

    Transitions:
    - CLOSED -> OPEN: Triggered after `failure_threshold` consecutive failures.
    - OPEN -> HALF_OPEN: Triggered when `recovery_timeout_seconds` has elapsed.
    - HALF_OPEN -> CLOSED: On successful request execution.
    - HALF_OPEN -> OPEN: On any failure while probing in half-open state.
    """

    def __init__(
        self,
        service_name: str = "collector",
        failure_threshold: int = 3,
        recovery_timeout_seconds: float = 900.0,  # 15 minutes default
    ):
        self.service_name = service_name
        self.failure_threshold = failure_threshold
        self.recovery_timeout_seconds = recovery_timeout_seconds
        self._state: str = CircuitBreakerState.CLOSED
        self._consecutive_failures: int = 0
        self._last_failure_time: Optional[float] = None

    @property
    def state(self) -> str:
        """Evaluate current state, checking timeout transition to HALF_OPEN."""
        if self._state == CircuitBreakerState.OPEN:
            if self._last_failure_time is not None:
                elapsed = time.monotonic() - self._last_failure_time
                if elapsed >= self.recovery_timeout_seconds:
                    self._state = CircuitBreakerState.HALF_OPEN
        return self._state

    @property
    def consecutive_failures(self) -> int:
        return self._consecutive_failures

    def can_execute(self) -> bool:
        """Check if execution is allowed. Raises CircuitBreakerOpenException if blocked."""
        current_state = self.state
        if current_state == CircuitBreakerState.OPEN:
            elapsed = time.monotonic() - (self._last_failure_time or 0.0)
            retry_after = max(0.0, self.recovery_timeout_seconds - elapsed)
            raise CircuitBreakerOpenException(self.service_name, retry_after)
        return True

    def record_success(self) -> None:
        """Record a successful execution."""
        self._consecutive_failures = 0
        self._state = CircuitBreakerState.CLOSED
        self._last_failure_time = None

    def record_failure(self) -> None:
        """Record a failed execution."""
        self._consecutive_failures += 1
        self._last_failure_time = time.monotonic()
        if self._consecutive_failures >= self.failure_threshold:
            self._state = CircuitBreakerState.OPEN

    def reset(self) -> None:
        """Reset breaker back to initial CLOSED state."""
        self._state = CircuitBreakerState.CLOSED
        self._consecutive_failures = 0
        self._last_failure_time = None

    T = TypeVar("T")

    def __call__(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """Decorator for sync or async functions."""
        if asyncio.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                self.can_execute()
                try:
                    res = await func(*args, **kwargs)
                    self.record_success()
                    return res
                except Exception:
                    self.record_failure()
                    raise

            return async_wrapper
        else:

            @wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                self.can_execute()
                try:
                    res = func(*args, **kwargs)
                    self.record_success()
                    return res
                except Exception:
                    self.record_failure()
                    raise

            return sync_wrapper


class BaseCollector(ABC):
    """Abstract base class for all APEX route data scrapers."""

    def __init__(
        self,
        name: str,
        source_code: str,
        min_delay_seconds: float = 1.0,
        max_requests_per_minute: int = 30,
        user_agent: str = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/128.0.0.0 Safari/537.36 (APEX Research Engine)"
        ),
        circuit_breaker: Optional[CircuitBreaker] = None,
    ):
        self.name = name
        self.source_code = source_code
        self.min_delay_seconds = min_delay_seconds
        self.max_requests_per_minute = max_requests_per_minute
        self.user_agent = user_agent
        self.circuit_breaker = circuit_breaker or CircuitBreaker(service_name=source_code)

    @abstractmethod
    async def collect_route(
        self, origin: str, destination: str, travel_date: date, window_label: str
    ) -> CollectorResult:
        """Collect observations for a specific route and travel date.

        Must emit a valid CollectorResult encapsulating canonical FareObservation records.
        """
        ...
