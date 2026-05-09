"""Small circuit breaker for external service degradation."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import Lock


@dataclass
class CircuitBreaker:
    """Track repeated external-service failures and short-circuit temporarily.

    This is intentionally a small two-state circuit breaker:
    - closed: calls are allowed
    - open: calls should be skipped until ``recovery_timeout_seconds`` expires

    It does not implement a separate half-open state, trial-call limit, or
    success threshold. Callers decide when to check ``is_open`` and when to
    record success/failure.
    """

    failure_threshold: int = 5
    recovery_timeout_seconds: int = 60
    _failures: int = field(default=0, init=False, repr=False)
    _opened_at: float | None = field(default=None, init=False, repr=False)
    _lock: Lock = field(default_factory=Lock, init=False, repr=False)

    @property
    def is_open(self) -> bool:
        """Return True when calls should be skipped until recovery timeout expires."""
        with self._lock:
            if self._opened_at is None:
                return False

            if time.monotonic() - self._opened_at > self.recovery_timeout_seconds:
                self._failures = 0
                self._opened_at = None
                return False

            return True

    def record_failure(self) -> None:
        """Record one failed call and open the circuit after the configured threshold."""
        with self._lock:
            self._failures += 1
            if self._failures >= self.failure_threshold:
                self._opened_at = time.monotonic()

    def record_success(self) -> None:
        """Reset failure state after a successful call."""
        with self._lock:
            self._failures = 0
            self._opened_at = None
