"""Decision cache: avoids re-classifying identical text within a short time window."""
import re
import time

from intake.llm import LLM
from intake.orchestrator import Decision, classify


def _normalise(text: str) -> str:
    """Return the cache key for text: stripped, internal whitespace collapsed, lower-cased."""
    return re.sub(r"\s+", " ", text.strip()).lower()


class DecisionCache:
    """Caches a Decision per normalised text for ttl_s seconds, avoiding redundant classification."""

    def __init__(self, ttl_s: float = 60.0) -> None:
        """Create a cache whose entries are considered live for ttl_s seconds."""
        self.ttl_s = ttl_s
        self._entries: dict[str, tuple[Decision, float]] = {}

    def get_or_classify(self, text: str, llm: LLM, now: float | None = None) -> Decision:
        """Return the live cached Decision for text, or classify, cache, and return a new one."""
        moment = time.time() if now is None else now
        key = _normalise(text)
        entry = self._entries.get(key)
        if entry is not None:
            decision, t0 = entry
            if moment - t0 < self.ttl_s:
                return decision

        decision = classify(text, llm)
        self._entries[key] = (decision, moment)
        return decision

    @property
    def size(self) -> int:
        """Return the number of entries that are still live right now."""
        now = time.time()
        return sum(1 for _, t0 in self._entries.values() if now - t0 < self.ttl_s)

    def clear(self) -> None:
        """Remove every entry from the cache, live or expired."""
        self._entries.clear()
