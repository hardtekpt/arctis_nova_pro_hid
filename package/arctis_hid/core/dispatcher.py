from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable


class EventDispatcher:
    """Simple synchronous callback dispatcher keyed by event name."""

    def __init__(self) -> None:
        self._listeners: dict[str, list[Callable]] = defaultdict(list)

    def on(self, event_name: str, cb: Callable) -> None:
        self._listeners[event_name].append(cb)

    def off(self, event_name: str, cb: Callable) -> None:
        try:
            self._listeners[event_name].remove(cb)
        except ValueError:
            pass

    def emit(self, event_name: str, event: Any) -> None:
        for cb in list(self._listeners[event_name]):
            cb(event)

    def emit_typed(self, event: Any) -> None:
        """Emit using the event's class name as the event key."""
        self.emit(type(event).__name__, event)
