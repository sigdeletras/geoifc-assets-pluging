"""Logging services for plugin developer logs and user-facing logs."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum

LOGGER_NAME = "geoifcassets"


class UserLogLevel(StrEnum):
    """User-facing log severity."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class UserLogEntry:
    """A translated or translatable message intended for the final user."""

    level: UserLogLevel
    message: str


class PluginLogger:
    """Small wrapper around Python logging plus an in-memory user log."""

    def __init__(self, name: str = LOGGER_NAME) -> None:
        self._developer_logger = logging.getLogger(name)
        self._user_entries: list[UserLogEntry] = []

    @property
    def user_entries(self) -> tuple[UserLogEntry, ...]:
        return tuple(self._user_entries)

    def debug(self, message: str, **context: object) -> None:
        self._developer_logger.debug(message, extra={"geoifc_context": context})

    def info(self, message: str, **context: object) -> None:
        self._developer_logger.info(message, extra={"geoifc_context": context})

    def warning(self, message: str, **context: object) -> None:
        self._developer_logger.warning(message, extra={"geoifc_context": context})

    def exception(self, message: str, **context: object) -> None:
        self._developer_logger.exception(message, extra={"geoifc_context": context})

    def user_info(self, message: str) -> None:
        self._add_user_entry(UserLogLevel.INFO, message)

    def user_warning(self, message: str) -> None:
        self._add_user_entry(UserLogLevel.WARNING, message)

    def user_error(self, message: str) -> None:
        self._add_user_entry(UserLogLevel.ERROR, message)

    def clear_user_entries(self) -> None:
        self._user_entries.clear()

    def _add_user_entry(self, level: UserLogLevel, message: str) -> None:
        self._user_entries.append(UserLogEntry(level=level, message=message))
