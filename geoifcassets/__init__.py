"""QGIS plugin entry point for GeoIFC Assets."""

from __future__ import annotations

from typing import Any


def classFactory(iface: Any) -> Any:  # noqa: N802
    """Create the plugin instance expected by QGIS."""
    from geoifcassets.adapters.qgis.plugin import GeoIfcAssetsPlugin

    return GeoIfcAssetsPlugin(iface)
