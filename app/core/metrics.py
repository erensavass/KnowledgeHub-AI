from collections import defaultdict
from threading import Lock


class MetricsRegistry:
    """Small dependency-free registry for low-cardinality process metrics."""

    def __init__(self) -> None:
        self._values: dict[str, float] = defaultdict(float)
        self._lock = Lock()

    def increment(self, name: str, value: float = 1) -> None:
        with self._lock:
            self._values[name] += value

    def render(self) -> str:
        with self._lock:
            values = dict(self._values)
        lines = []
        for name, value in sorted(values.items()):
            lines.extend((f"# TYPE {name} counter", f"{name} {value:g}"))
        return "\n".join(lines) + "\n"

    def reset(self) -> None:
        with self._lock:
            self._values.clear()


metrics = MetricsRegistry()
