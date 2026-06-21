"""User message adapter for QGIS."""

from __future__ import annotations

from typing import Any


def _message_level(name: str) -> Any:
    try:
        from qgis.core import Qgis
    except ImportError:
        return name

    message_level = getattr(Qgis, "MessageLevel", None)
    if message_level is not None and hasattr(message_level, name):
        return getattr(message_level, name)

    legacy_level = getattr(Qgis, name, None)
    if legacy_level is not None:
        return legacy_level

    return name


class QgisMessageService:
    """Show user-facing messages through QGIS when available."""

    def __init__(self, iface: Any, plugin_name: str) -> None:
        self._iface = iface
        self._plugin_name = plugin_name

    def info(self, message: str) -> None:
        self._push_message(message, _message_level("Info"))

    def warning(self, message: str) -> None:
        self._push_message(message, _message_level("Warning"))

    def error(self, message: str) -> None:
        self._push_message(message, _message_level("Critical"))

    def _push_message(self, message: str, level: Any) -> None:
        message_bar = getattr(self._iface, "messageBar", lambda: None)()
        if message_bar is None:
            return
        message_bar.pushMessage(self._plugin_name, message, level, 5)
