"""reliability.py - M7: retries + circuit breaker for sensor-feed / ERP calls.

IN SHORT: facts.py's telemetry lookup and mcp_server.py's inventory/ERP
calls are, today, 100% reliable local reads - but the spec calls for
hardening them as if they were flaky external APIs, because "false
negatives here are costly": a failed call that SILENTLY returns empty or
default data looks identical to a genuine "no history" answer, and an
agent (or a human) acting on that can miss something that still exists.

  @with_retries(name)   : retries a transient-looking failure with jittered
                          backoff, through a shared CircuitBreaker per name
  CircuitBreaker          : after too many consecutive failures for one
                          name, stops trying for a cooldown window and
                          fails FAST instead of retrying into a dead service

Both RAISE on failure - never return a default value standing in for real
data. A caller that wants a fallback must choose one explicitly and say so
(e.g. a guard flag), not have one silently injected here.
"""
import logging
import random
import time
from dataclasses import dataclass, field
from functools import wraps

logger = logging.getLogger(__name__)


class ServiceUnavailable(Exception):
    """Retries exhausted, or the circuit is open. Treat this as 'we do not know
    right now', never as 'the answer is empty' - callers must not swallow it
    into a default value."""


# ---------------------------------------------------------------------------
# Circuit breaker: one instance per upstream name (e.g. "sensor_feed", "erp")
# ---------------------------------------------------------------------------
@dataclass
class CircuitBreaker:
    name: str
    failure_threshold: int = 3         # consecutive failures before opening (design choice)
    cooldown_s: float = 30.0           # how long the circuit stays open (design choice)
    _consecutive_failures: int = field(default=0, init=False)
    _opened_at: float | None = field(default=None, init=False)

    def _is_open(self) -> bool:
        if self._opened_at is None:
            return False
        if time.monotonic() - self._opened_at >= self.cooldown_s:
            logger.info("CIRCUIT %s: cooldown elapsed, half-open (next call is a probe)", self.name)
            self._opened_at = None          # half-open: let the next call through as a probe
            return False
        return True

    def before_call(self) -> None:
        if self._is_open():
            raise ServiceUnavailable(f"{self.name}: circuit open, cooling down")

    @property
    def status(self) -> dict:
        """Read-only snapshot for a dashboard - never mutates state (unlike _is_open(),
        which half-opens the circuit as a side effect of checking it)."""
        open_now = self._opened_at is not None and time.monotonic() - self._opened_at < self.cooldown_s
        return {"name": self.name, "consecutive_failures": self._consecutive_failures, "open": open_now}

    def record_success(self) -> None:
        self._consecutive_failures = 0

    def record_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures >= self.failure_threshold and self._opened_at is None:
            self._opened_at = time.monotonic()
            logger.warning("CIRCUIT %s: opened after %d consecutive failures",
                           self.name, self._consecutive_failures)


_BREAKERS: dict[str, CircuitBreaker] = {}


def get_breaker(name: str, **kwargs) -> CircuitBreaker:
    """The shared CircuitBreaker for `name` (one per process, created on first use)."""
    if name not in _BREAKERS:
        _BREAKERS[name] = CircuitBreaker(name, **kwargs)
    return _BREAKERS[name]


def all_breaker_status() -> list[dict]:
    """Status of every circuit breaker created so far (for a dashboard)."""
    return [cb.status for cb in _BREAKERS.values()]


# ---------------------------------------------------------------------------
# Retry decorator (through the named circuit breaker)
# ---------------------------------------------------------------------------
def with_retries(name: str, attempts: int = 3, base_delay_s: float = 0.2, breaker: bool = True):
    """Retry the wrapped call up to `attempts` times with jittered backoff.
    Raises ServiceUnavailable - never returns a stand-in value - once retries
    are exhausted or the shared circuit for `name` is open."""
    def decorator(fn):
        cb = get_breaker(name) if breaker else None

        @wraps(fn)
        def wrapper(*args, **kwargs):
            if cb:
                cb.before_call()
            last_exc = None
            for attempt in range(1, attempts + 1):
                try:
                    result = fn(*args, **kwargs)
                    if cb:
                        cb.record_success()
                    return result
                except Exception as e:
                    last_exc = e
                    if cb:
                        cb.record_failure()
                    logger.warning("RETRY %s: attempt %d/%d failed (%s: %s)",
                                   name, attempt, attempts, type(e).__name__, e)
                    if attempt < attempts:
                        time.sleep(base_delay_s * attempt + random.uniform(0, base_delay_s))
            raise ServiceUnavailable(f"{name}: failed after {attempts} attempts") from last_exc
        return wrapper
    return decorator
