"""
Unit tests for ai_day_planner/event_bus.py

Covers:
- subscribe + publish invokes handler
- multiple handlers invoked in FIFO registration order
- unsubscribe removes handler
- handler exception is caught, logged, remaining handlers still called
- publish logs event type and timestamp
- unsubscribe nonexistent handler does not raise
- publish to event type with no handlers does not raise
- handler receives correct payload
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, call, patch

import pytest

from ai_day_planner.event_bus import (
    COEFFICIENT_UPDATED,
    FATIGUE_UPDATED,
    SCHEDULE_UPDATED,
    TASK_CREATED,
    TASK_DELETED,
    TASK_TRACKED,
    TASK_UPDATED,
    TIME_BLOCK_DELETED,
    EventBus,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def logger() -> logging.Logger:
    """Return a real Logger with a NullHandler so output is suppressed."""
    log = logging.getLogger("test.event_bus")
    log.addHandler(logging.NullHandler())
    log.propagate = False
    return log


@pytest.fixture()
def bus(logger: logging.Logger) -> EventBus:
    return EventBus(logger=logger)


# ---------------------------------------------------------------------------
# Tests: subscribe / publish
# ---------------------------------------------------------------------------

class TestSubscribePublish:
    def test_subscribe_and_publish_invokes_handler(self, bus: EventBus):
        handler = MagicMock()
        bus.subscribe(TASK_CREATED, handler)
        bus.publish(TASK_CREATED, {"task_id": "abc"})
        handler.assert_called_once_with({"task_id": "abc"})

    def test_handler_receives_correct_payload(self, bus: EventBus):
        received: list[dict] = []
        bus.subscribe(TASK_UPDATED, received.append)
        payload = {"task_id": "xyz", "field": "title"}
        bus.publish(TASK_UPDATED, payload)
        assert received == [payload]

    def test_publish_to_event_with_no_handlers_does_not_raise(self, bus: EventBus):
        # No handlers registered — must not raise
        bus.publish(SCHEDULE_UPDATED, {"info": "none"})

    def test_multiple_handlers_invoked_in_fifo_order(self, bus: EventBus):
        order: list[int] = []
        bus.subscribe(TASK_CREATED, lambda _: order.append(1))
        bus.subscribe(TASK_CREATED, lambda _: order.append(2))
        bus.subscribe(TASK_CREATED, lambda _: order.append(3))
        bus.publish(TASK_CREATED, {})
        assert order == [1, 2, 3]

    def test_handler_not_called_for_different_event_type(self, bus: EventBus):
        handler = MagicMock()
        bus.subscribe(TASK_CREATED, handler)
        bus.publish(TASK_DELETED, {"task_id": "abc"})
        handler.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: unsubscribe
# ---------------------------------------------------------------------------

class TestUnsubscribe:
    def test_unsubscribe_removes_handler(self, bus: EventBus):
        handler = MagicMock()
        bus.subscribe(TASK_DELETED, handler)
        bus.unsubscribe(TASK_DELETED, handler)
        bus.publish(TASK_DELETED, {})
        handler.assert_not_called()

    def test_unsubscribe_nonexistent_handler_does_not_raise(self, bus: EventBus):
        handler = MagicMock()
        # Never subscribed — must not raise
        bus.unsubscribe(TASK_CREATED, handler)

    def test_unsubscribe_unknown_event_type_does_not_raise(self, bus: EventBus):
        handler = MagicMock()
        bus.unsubscribe("never_registered_event", handler)

    def test_unsubscribe_only_removes_target_handler(self, bus: EventBus):
        handler_a = MagicMock()
        handler_b = MagicMock()
        bus.subscribe(FATIGUE_UPDATED, handler_a)
        bus.subscribe(FATIGUE_UPDATED, handler_b)
        bus.unsubscribe(FATIGUE_UPDATED, handler_a)
        bus.publish(FATIGUE_UPDATED, {})
        handler_a.assert_not_called()
        handler_b.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: exception isolation
# ---------------------------------------------------------------------------

class TestExceptionIsolation:
    def test_handler_exception_does_not_abort_remaining_handlers(self, bus: EventBus):
        def bad_handler(_payload):
            raise RuntimeError("boom")

        good_handler = MagicMock()
        bus.subscribe(TASK_TRACKED, bad_handler)
        bus.subscribe(TASK_TRACKED, good_handler)
        bus.publish(TASK_TRACKED, {"session_id": "s1"})
        good_handler.assert_called_once()

    def test_handler_exception_is_logged(self, bus: EventBus):
        def bad_handler(_payload):
            raise ValueError("oops")

        bus.subscribe(COEFFICIENT_UPDATED, bad_handler)

        with patch.object(bus._logger, "error") as mock_error:
            bus.publish(COEFFICIENT_UPDATED, {})

        mock_error.assert_called_once()
        call_kwargs = mock_error.call_args
        extra = call_kwargs.kwargs.get("extra") or (call_kwargs.args[1] if len(call_kwargs.args) > 1 else {})
        # extra is passed as keyword arg to logger.error
        extra = mock_error.call_args[1].get("extra", {})
        assert "handler" in extra
        assert "event_type" in extra
        assert "exception" in extra

    def test_multiple_failing_handlers_all_logged_and_remaining_called(self, bus: EventBus):
        def bad1(_p):
            raise RuntimeError("first")

        def bad2(_p):
            raise RuntimeError("second")

        good = MagicMock()
        bus.subscribe(TIME_BLOCK_DELETED, bad1)
        bus.subscribe(TIME_BLOCK_DELETED, bad2)
        bus.subscribe(TIME_BLOCK_DELETED, good)

        with patch.object(bus._logger, "error") as mock_error:
            bus.publish(TIME_BLOCK_DELETED, {})

        assert mock_error.call_count == 2
        good.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: logging of published events
# ---------------------------------------------------------------------------

class TestPublishLogging:
    def test_publish_logs_event_type(self, bus: EventBus):
        with patch.object(bus._logger, "info") as mock_info:
            bus.publish(TASK_CREATED, {"task_id": "t1"})

        mock_info.assert_called_once()
        extra = mock_info.call_args[1].get("extra", {})
        assert extra.get("event_type") == TASK_CREATED

    def test_publish_logs_timestamp(self, bus: EventBus):
        from datetime import datetime

        with patch.object(bus._logger, "info") as mock_info:
            bus.publish(TASK_CREATED, {})

        extra = mock_info.call_args[1].get("extra", {})
        ts = extra.get("timestamp")
        assert ts is not None
        # Must parse as ISO 8601
        datetime.fromisoformat(ts)

    def test_publish_logs_payload_keys_not_values(self, bus: EventBus):
        """Payload summary must contain keys only — not values (privacy)."""
        with patch.object(bus._logger, "info") as mock_info:
            bus.publish(TASK_CREATED, {"secret_value": "do_not_log_me", "task_id": "t1"})

        extra = mock_info.call_args[1].get("extra", {})
        payload_keys = extra.get("payload_keys", [])
        assert set(payload_keys) == {"secret_value", "task_id"}
        # Ensure the actual values are not in the logged extra
        assert "do_not_log_me" not in str(extra)


# ---------------------------------------------------------------------------
# Tests: event type constants
# ---------------------------------------------------------------------------

class TestEventTypeConstants:
    def test_all_required_constants_defined(self):
        from ai_day_planner import event_bus as eb
        assert eb.TASK_CREATED == "task_created"
        assert eb.TASK_UPDATED == "task_updated"
        assert eb.TASK_DELETED == "task_deleted"
        assert eb.SCHEDULE_UPDATED == "schedule_updated"
        assert eb.FATIGUE_UPDATED == "fatigue_updated"
        assert eb.TASK_TRACKED == "task_tracked"
        assert eb.COEFFICIENT_UPDATED == "coefficient_updated"
        assert eb.TIME_BLOCK_DELETED == "time_block_deleted"


# ---------------------------------------------------------------------------
# Tests: independence (no global state)
# ---------------------------------------------------------------------------

class TestIndependence:
    def test_two_bus_instances_are_independent(self, logger: logging.Logger):
        bus_a = EventBus(logger=logger)
        bus_b = EventBus(logger=logger)

        handler_a = MagicMock()
        handler_b = MagicMock()

        bus_a.subscribe(TASK_CREATED, handler_a)
        bus_b.subscribe(TASK_CREATED, handler_b)

        bus_a.publish(TASK_CREATED, {})

        handler_a.assert_called_once()
        handler_b.assert_not_called()


# ---------------------------------------------------------------------------
# Property-based tests
# ---------------------------------------------------------------------------

from hypothesis import given, settings
from hypothesis import strategies as st


class TestPropertyHandlerInvocationOrder:
    """
    Property 25: Event Handler Invocation Order

    For any number of handlers registered for a given event type in a known
    order, when that event is published all handlers SHALL be invoked in
    exactly the order they were registered.

    **Validates: Requirements 9.2**
    """

    @given(n_handlers=st.integers(min_value=1, max_value=20))
    @settings(max_examples=100)
    def test_handlers_invoked_in_fifo_registration_order(self, n_handlers: int):
        log = logging.getLogger("test.pbt.order")
        log.addHandler(logging.NullHandler())
        log.propagate = False
        bus = EventBus(logger=log)
        invocation_order: list[int] = []

        # Register n handlers, each appending its index when called
        for i in range(n_handlers):
            # Capture i by default argument to avoid closure-over-loop-variable
            def make_handler(idx: int):
                def handler(_payload: dict) -> None:
                    invocation_order.append(idx)
                return handler

            bus.subscribe(TASK_CREATED, make_handler(i))

        bus.publish(TASK_CREATED, {})

        assert invocation_order == list(range(n_handlers)), (
            f"Expected FIFO order {list(range(n_handlers))}, got {invocation_order}"
        )
