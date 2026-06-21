"""Translation helpers for QGIS UI strings."""

from __future__ import annotations


def tr(context: str, text: str) -> str:
    """Translate text using Qt when the plugin runs inside QGIS."""
    try:
        from qgis.PyQt.QtCore import QCoreApplication
    except ImportError:
        return text

    return str(QCoreApplication.translate(context, text))
