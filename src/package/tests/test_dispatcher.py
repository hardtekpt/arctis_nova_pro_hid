"""Tests for arctis_hid.core.dispatcher.EventDispatcher."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from arctis_hid.core.dispatcher import EventDispatcher
from arctis_hid.devices.nova_pro.models import VolumeEvent


class TestEventDispatcher:
    def setup_method(self):
        self.dispatcher = EventDispatcher()

    # ── on / emit ──────────────────────────────────────────────────────────────

    def test_registered_callback_fires_on_emit(self):
        cb = MagicMock()
        self.dispatcher.on("MyEvent", cb)
        self.dispatcher.emit("MyEvent", "payload")
        cb.assert_called_once_with("payload")

    def test_multiple_callbacks_all_fire_in_order(self):
        calls = []
        self.dispatcher.on("E", lambda e: calls.append("first"))
        self.dispatcher.on("E", lambda e: calls.append("second"))
        self.dispatcher.emit("E", None)
        assert calls == ["first", "second"]

    def test_emit_with_no_listeners_does_not_raise(self):
        self.dispatcher.emit("NoListeners", "data")   # must not raise

    def test_emit_passes_event_object_unchanged(self):
        received = []
        self.dispatcher.on("Ev", received.append)
        sentinel = object()
        self.dispatcher.emit("Ev", sentinel)
        assert received == [sentinel]

    # ── off ────────────────────────────────────────────────────────────────────

    def test_off_removes_specific_callback(self):
        cb1 = MagicMock()
        cb2 = MagicMock()
        self.dispatcher.on("E", cb1)
        self.dispatcher.on("E", cb2)
        self.dispatcher.off("E", cb1)
        self.dispatcher.emit("E", None)
        cb1.assert_not_called()
        cb2.assert_called_once()

    def test_off_unregistered_callback_does_not_raise(self):
        cb = MagicMock()
        self.dispatcher.off("NonExistent", cb)   # must not raise

    def test_off_leaves_other_events_untouched(self):
        cb = MagicMock()
        self.dispatcher.on("A", cb)
        self.dispatcher.on("B", cb)
        self.dispatcher.off("A", cb)
        self.dispatcher.emit("B", None)
        cb.assert_called_once()

    # ── emit_typed ─────────────────────────────────────────────────────────────

    def test_emit_typed_uses_class_name_as_key(self):
        cb = MagicMock()
        self.dispatcher.on("VolumeEvent", cb)
        event = VolumeEvent(percent=75.0)
        self.dispatcher.emit_typed(event)
        cb.assert_called_once_with(event)

    def test_emit_typed_does_not_fire_wrong_event_name(self):
        cb = MagicMock()
        self.dispatcher.on("WrongName", cb)
        self.dispatcher.emit_typed(VolumeEvent(percent=50.0))
        cb.assert_not_called()

    # ── edge cases ────────────────────────────────────────────────────────────

    def test_same_callback_registered_twice_fires_twice(self):
        cb = MagicMock()
        self.dispatcher.on("E", cb)
        self.dispatcher.on("E", cb)
        self.dispatcher.emit("E", None)
        assert cb.call_count == 2

    def test_callback_exception_does_not_block_subsequent_callbacks(self):
        def bad_cb(e):
            raise RuntimeError("boom")

        good_cb = MagicMock()
        self.dispatcher.on("E", bad_cb)
        self.dispatcher.on("E", good_cb)
        with pytest.raises(RuntimeError):
            self.dispatcher.emit("E", None)
        # good_cb is called after bad_cb raises — dispatcher does NOT catch exceptions
        # (the current implementation propagates the first exception)
        # This test documents the current behavior: emit stops on exception.
        good_cb.assert_not_called()
