from __future__ import annotations

from geoifcassets.services.logging import PluginLogger, UserLogLevel


def test_user_log_entries_are_recorded() -> None:
    logger = PluginLogger("geoifcassets.tests")

    logger.user_info("Ready")
    logger.user_warning("Check layer fields")
    logger.user_error("Cannot open IFC")

    entries = logger.user_entries
    assert [entry.level for entry in entries] == [
        UserLogLevel.INFO,
        UserLogLevel.WARNING,
        UserLogLevel.ERROR,
    ]
    assert [entry.message for entry in entries] == [
        "Ready",
        "Check layer fields",
        "Cannot open IFC",
    ]


def test_user_log_entries_can_be_cleared() -> None:
    logger = PluginLogger("geoifcassets.tests")

    logger.user_info("Ready")
    logger.clear_user_entries()

    assert logger.user_entries == ()
