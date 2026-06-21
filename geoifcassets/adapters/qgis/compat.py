"""Compatibility helpers for QGIS 3 and QGIS 4."""

from __future__ import annotations

from typing import Any


def qgis_version(iface: Any) -> str:
    """Return the QGIS version string when available."""
    try:
        from qgis.core import Qgis
    except ImportError:
        return "unknown"

    version = getattr(Qgis, "QGIS_VERSION", None)
    if isinstance(version, str):
        return version

    app = getattr(iface, "mainWindow", lambda: None)()
    return str(app) if app is not None else "unknown"
