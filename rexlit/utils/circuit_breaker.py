"""Circuit breaker pattern for resilient service calls.

Implements the circuit breaker pattern to prevent cascading failures when
calling external services or resource-intensive operations like LLM inference.

States:
- CLOSED: Normal operation, calls pass through
- OPEN: Too many failures, calls fail fast without attempting operation
- HALF_OPEN: Testing if service recovered, limited calls allowed

See: https://martinfowler.com/bliki/CircuitBreaker.html
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal, TypeVar

T = TypeVar("T")


class CircuitBreakerOpen(Exception):
    """Raised when circuit breaker is in OPEN state and rejects calls."""

    pass


@dataclass
class CircuitBreaker:
    """Circuit breaker for resilient service calls.

    Example:
        >>> breaker = CircuitBreaker(failure_threshold=5, timeout_seconds=60)
        >>> try:
        >>>     result = breaker.call(lambda: expensive_api_call())
        >>> except CircuitBreakerOpen:
        >>>     # Handle gracefully, use fallback
        >>>     result = use_fallback()
    """

    failure_threshold: int = 5
    """Number of consecutive failures before opening circuit"""

    timeout_seconds: float = 60.0
    """Seconds to wait before attempting recovery (OPEN → HALF_OPEN)"""

    half_open_max_calls: int = 1
    """Max calls allowed in HALF_OPEN state before fully closing"""

    current_failures: int = field(default=0, init=False)
    """Current consecutive failure count"""

    state: Literal["CLOSED", "OPEN", "HALF_OPEN"] = field(default="CLOSED", init=False)
    """Current circuit state"""

    last_failure_time: float | None = field(default=None, init=False)
    """Timestamp of last failure (for timeout calculation)"""

    half_open_calls: int = field(default=0, init=False)
    """Calls attempted in HALF_OPEN state"""

    def call(self, fn: Callable[[], T]) -> T:
        """Execute function with circuit breaker protection.

        Args:
            fn: Callable to execute (should take no args)

        Returns:
            Result of fn()

        Raises:
            CircuitBreakerOpen: If circuit is OPEN and not ready to retry
            Exception: Any exception raised by fn() (will increment failure count)
        """
        if self.state == "OPEN":
            if self._should_attempt_reset():
                self.state = "HALF_OPEN"
                self.half_open_calls = 0
            else:
                raise CircuitBreakerOpen(
                    f"Circuit breaker is OPEN (failed {self.current_failures} times). "
                    f"Retry after {self.timeout_seconds}s timeout."
                )

        try:
            result = fn()
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e

    def _on_success(self) -> None:
        """Handle successful call."""
        if self.state == "HALF_OPEN":
            self.half_open_calls += 1
            if self.half_open_calls >= self.half_open_max_calls:
                # Recovery confirmed, close circuit
                self.state = "CLOSED"
                self.current_failures = 0
                self.last_failure_time = None
        elif self.state == "CLOSED":
            # Reset failure count on any success
            self.current_failures = 0
            self.last_failure_time = None

    def _on_failure(self) -> None:
        """Handle failed call."""
        self.current_failures += 1
        self.last_failure_time = time.time()

        if self.current_failures >= self.failure_threshold:
            self.state = "OPEN"

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt recovery."""
        if self.last_failure_time is None:
            return True

        elapsed = time.time() - self.last_failure_time
        return elapsed >= self.timeout_seconds

    def reset(self) -> None:
        """Manually reset circuit breaker to CLOSED state."""
        self.state = "CLOSED"
        self.current_failures = 0
        self.last_failure_time = None
        self.half_open_calls = 0

    def get_state(self) -> dict[str, str | int | float | None]:
        """Get current circuit breaker state for monitoring/debugging."""
        return {
            "state": self.state,
            "failures": self.current_failures,
            "last_failure": self.last_failure_time,
            "threshold": self.failure_threshold,
        }
