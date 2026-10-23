"""Per-customer sliding-window rate limiting."""
import time

from intake.errors import ValidationError


class RateLimiter:
    """Caps how many requests a single customer may make within a rolling time window."""

    def __init__(self, limit: int = 30, window_s: float = 60.0) -> None:
        """Create a limiter allowing limit requests per customer per window_s seconds."""
        self.limit = limit
        self.window_s = window_s
        self._moments: dict[str, list[float]] = {}

    def _resolve_customer_id(self, customer_id: str) -> str:
        """Strip customer_id and raise ValidationError if the result is empty."""
        stripped = customer_id.strip()
        if stripped == "":
            raise ValidationError("customer_id must not be empty or whitespace-only")
        return stripped

    def _count_in_window(self, customer_id: str, now: float) -> int:
        """Return the number of customer_id's recorded moments still within the window of now."""
        moments = self._moments.get(customer_id, [])
        return sum(1 for t in moments if not t < now - self.window_s)

    def allow(self, customer_id: str, now: float | None = None) -> bool:
        """Return whether a request for customer_id is allowed now, recording it if so."""
        key = self._resolve_customer_id(customer_id)
        moment = time.time() if now is None else now
        if self._count_in_window(key, moment) < self.limit:
            self._moments.setdefault(key, []).append(moment)
            return True
        return False

    def remaining(self, customer_id: str, now: float | None = None) -> int:
        """Return how many more requests customer_id may make right now before being denied."""
        key = self._resolve_customer_id(customer_id)
        moment = time.time() if now is None else now
        return self.limit - self._count_in_window(key, moment)
