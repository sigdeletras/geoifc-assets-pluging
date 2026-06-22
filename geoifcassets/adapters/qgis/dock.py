"""Initial dock widget for GeoIFC Assets."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from geoifcassets.adapters.qgis.i18n import tr


class GeoIfcAssetsDock:
    """Factory wrapper for the QGIS dock widget."""

    def __init__(
        self,
        on_refresh: Callable[[], None],
        on_open_viewer: Callable[[], None],
    ) -> None:
        from qgis.PyQt.QtWidgets import (
            QDockWidget,
            QHBoxLayout,
            QLabel,
            QPushButton,
            QTabWidget,
            QTextEdit,
            QVBoxLayout,
            QWidget,
        )

        self.widget = QDockWidget(tr("GeoIfcAssets", "GeoIFC Assets"))
        self.widget.setObjectName("GeoIfcAssetsDock")

        content = QWidget()
        layout = QVBoxLayout(content)

        tabs = QTabWidget()
        properties_tab = QWidget()
        properties_layout = QVBoxLayout(properties_tab)
        viewer_tab = QWidget()
        viewer_layout = QVBoxLayout(viewer_tab)

        self._status_label = QLabel(
            tr(
                "GeoIfcAssets",
                "Select a GIS feature with ifc_path or ifc_url to start.",
            )
        )
        self._status_label.setWordWrap(True)
        properties_layout.addWidget(self._status_label)

        self._user_log = QTextEdit()
        self._user_log.setReadOnly(True)
        self._user_log.setPlaceholderText(tr("GeoIfcAssets", "Workflow messages"))
        properties_layout.addWidget(self._user_log)

        buttons_layout = QHBoxLayout()
        self._refresh_button = QPushButton(tr("GeoIfcAssets", "Refresh selection"))
        self._open_button = QPushButton(tr("GeoIfcAssets", "Open IFC viewer"))
        self._open_button.setEnabled(False)
        self._refresh_button.clicked.connect(on_refresh)
        self._open_button.clicked.connect(on_open_viewer)
        buttons_layout.addWidget(self._refresh_button)
        buttons_layout.addWidget(self._open_button)
        viewer_layout.addLayout(buttons_layout)
        viewer_layout.addStretch(1)

        tabs.addTab(properties_tab, tr("GeoIfcAssets", "Properties"))
        tabs.addTab(viewer_tab, tr("GeoIfcAssets", "IFC Viewer"))
        layout.addWidget(tabs)

        self.widget.setWidget(content)

    def qwidget(self) -> Any:
        return self.widget

    def set_status(self, message: str, can_open_viewer: bool = False) -> None:
        self._status_label.setText(message)
        self._open_button.setEnabled(can_open_viewer)

    def add_user_log(self, message: str) -> None:
        self._user_log.append(message)
