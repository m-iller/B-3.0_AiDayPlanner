"""
In-process synchronous event bus for AI Day Planner.

Modules publish named events; handlers are invoked in FIFO registration order.
Handler exceptions are caught, logged, and do not abort remaining handlers.
Logger is injected — no global state.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Callable

# ---------------------------------------------------------------------------
# Event type constants
# ---------------------------------------------------------------------------

TASK_CREATED = "task_created"
TASK_UPDATED = "task_updated"
TASK_DELETED = "task_deleted"
SCHEDULE_UPDATED = "schedule_updated"
FATIGUE_UPDATED = "fatigue_updated"
TASK_TRACKED = "task_tracked"
COEFFICIENT_UPDATED = "coefficient_updated"
TIME_BLOCK_DELETED = "time_block_deleted"

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

EventPayload = dict[str, Any]
HandlerFn = Callable[[EventPayload], None]


# ---------------------------------------------------------------------------
# EventBus
# ---------------------------------------------------------------------------

class EventBus:
    """
    Synchronous, in-process publish/subscribe event bus.

    Each instance is independent — no global singleton.
    """

    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger
        # dict[event_type, list[HandlerFn]] — preserves insertion order (FIFO)
        self._handlers: dict[str, list[HandlerFn]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: HandlerFn) -> None:
        """Register *handler* to be called when *event_type* is published."""
        self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: HandlerFn) -> None:
        """
        Deregister *handler* by identity.

        No-op if the handler is not registered for *event_type*.
        """
        handlers = self._handlers.get(event_type)
        if handlers is None:
            return
        try:
            handlers.remove(handler)
        except ValueError:
            pass  # not registered — silently ignore per spec

    def publish(self, event_type: str, payload: EventPayload) -> None:
        """
        Invoke all handlers registered for *event_type* in FIFO order.

        - Logs the event (type, ISO 8601 timestamp, payload keys only).
        - If a handler raises, logs the exception and continues to the next handler.
        """
        timestamp = datetime.now(tz=timezone.utc).isoformat()
        self._logger.info(
            "Event published",
            extra={
                "event_type": event_type,
                "timestamp": timestamp,
                "payload_keys": list(payload.keys()),
            },
        )

        for handler in list(self._handlers.get(event_type, [])):
            try:
                handler(payload)
            except Exception as exc:  # noqa: BLE001
                self._logger.error(
                    "Handler raised an exception",
                    extra={
                        "handler": handler.__qualname__,
                        "event_type": event_type,
                        "exception": repr(exc),
                    },
                )
