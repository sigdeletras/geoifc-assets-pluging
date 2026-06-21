"""QGIS plugin implementation for GeoIFC Assets."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from geoifcassets.adapters.ifc.reader import IfcReader, IfcReadStatus
from geoifcassets.adapters.qgis.compat import qgis_version
from geoifcassets.adapters.qgis.dock import GeoIfcAssetsDock
from geoifcassets.adapters.qgis.feature_reader import (
    FeatureIfcReferenceReadResult,
    FeatureReadStatus,
    SelectedFeatureIfcReferenceReader,
)
from geoifcassets.adapters.qgis.i18n import tr
from geoifcassets.adapters.qgis.messages import QgisMessageService
from geoifcassets.adapters.qgis.viewer import IfcViewerDock
from geoifcassets.core.models import IfcReference
from geoifcassets.services.logging import PluginLogger

PLUGIN_NAME = "GeoIFC Assets"


class GeoIfcAssetsPlugin:
    """Minimal QGIS plugin shell for phase 1."""

    def __init__(self, iface: Any) -> None:
        self._iface = iface
        self._logger = PluginLogger()
        self._messages = QgisMessageService(iface, PLUGIN_NAME)
        self._feature_reader = SelectedFeatureIfcReferenceReader()
        self._ifc_reader = IfcReader()
        self._dock: GeoIfcAssetsDock | None = None
        self._viewer_dock: IfcViewerDock | None = None
        self._action: Any | None = None
        self._current_reference: IfcReference | None = None

    def initGui(self) -> None:  # noqa: N802
        """Create menu, toolbar action and dock."""
        from qgis.PyQt.QtGui import QIcon
        from qgis.PyQt.QtWidgets import QAction

        icon_path = Path(__file__).resolve().parents[2] / "icon.svg"
        self._action = QAction(QIcon(str(icon_path)), tr("GeoIfcAssets", PLUGIN_NAME), None)
        self._action.triggered.connect(self._show_dock)

        self._iface.addToolBarIcon(self._action)
        self._iface.addPluginToMenu(PLUGIN_NAME, self._action)

        self._logger.info("Plugin GUI initialized", qgis_version=qgis_version(self._iface))
        self._logger.user_info(tr("GeoIfcAssets", "GeoIFC Assets loaded."))

    def unload(self) -> None:
        """Remove plugin UI from QGIS."""
        if self._action is not None:
            self._iface.removePluginMenu(PLUGIN_NAME, self._action)
            self._iface.removeToolBarIcon(self._action)
            self._action = None

        if self._dock is not None:
            self._dock.qwidget().close()
            self._dock = None

        if self._viewer_dock is not None:
            self._viewer_dock.qwidget().close()
            self._viewer_dock = None

        self._logger.info("Plugin unloaded")

    def _show_dock(self) -> None:
        from qgis.PyQt.QtCore import Qt

        if self._dock is None:
            self._dock = GeoIfcAssetsDock(
                on_refresh=self._refresh_selection,
                on_open_viewer=self._open_viewer,
            )
            dock_area = getattr(Qt, "RightDockWidgetArea", None)
            if dock_area is None:
                dock_area = Qt.DockWidgetArea.RightDockWidgetArea
            self._iface.addDockWidget(dock_area, self._dock.qwidget())

        self._dock.qwidget().show()
        self._messages.info(tr("GeoIfcAssets", "GeoIFC Assets panel opened."))
        self._refresh_selection()

    def _refresh_selection(self) -> None:
        layer = getattr(self._iface, "activeLayer", lambda: None)()
        result = self._feature_reader.read_from_layer(layer)
        self._current_reference = result.reference
        message = self._message_for_read_result(result)

        if self._dock is not None:
            self._dock.set_status(message, can_open_viewer=result.reference is not None)
            self._dock.add_user_log(message)

        if result.status is FeatureReadStatus.OK:
            self._logger.info(
                "IFC reference resolved from selected feature",
                reference_kind=result.reference.kind.value if result.reference else None,
                has_conflict=result.has_conflict,
            )
            if result.has_conflict:
                self._messages.warning(
                    tr(
                        "GeoIfcAssets",
                        "Both ifc_path and ifc_url have values. ifc_path will be used first.",
                    )
                )
        else:
            self._logger.warning("IFC reference could not be resolved", status=result.status.value)

    def _open_viewer(self) -> None:
        from qgis.PyQt.QtCore import Qt

        if self._current_reference is None:
            self._messages.warning(tr("GeoIfcAssets", "No IFC reference is available."))
            return

        if self._viewer_dock is None:
            self._viewer_dock = IfcViewerDock()
            dock_area = getattr(Qt, "RightDockWidgetArea", None)
            if dock_area is None:
                dock_area = Qt.DockWidgetArea.RightDockWidgetArea
            self._iface.addDockWidget(dock_area, self._viewer_dock.qwidget())

        self._viewer_dock.open_reference(self._current_reference)
        self._viewer_dock.qwidget().show()
        read_result = self._ifc_reader.read_summary(self._current_reference.value)
        if read_result.status is IfcReadStatus.OK and read_result.summary is not None:
            schema = read_result.summary.schema or tr("GeoIfcAssets", "unknown schema")
            message = tr("GeoIfcAssets", "IFC viewer opened. Schema: {schema}").format(
                schema=schema
            )
        elif read_result.status is IfcReadStatus.NOT_LOCAL_FILE:
            message = tr("GeoIfcAssets", "IFC viewer opened for remote source.")
        elif read_result.status is IfcReadStatus.NOT_IFC_FILE:
            message = tr("GeoIfcAssets", "The selected file does not look like a valid IFC file.")
        else:
            message = tr("GeoIfcAssets", "IFC viewer opened. IFC metadata was not read.")

        if self._dock is not None:
            self._dock.add_user_log(message)
        self._messages.info(tr("GeoIfcAssets", "IFC viewer opened."))
        self._logger.info(
            "IFC viewer opened",
            reference_kind=self._current_reference.kind.value,
            source=self._current_reference.value,
            ifc_read_status=read_result.status.value,
            ifc_schema=read_result.summary.schema if read_result.summary else None,
        )

    def _message_for_read_result(self, result: FeatureIfcReferenceReadResult) -> str:
        if result.status is FeatureReadStatus.OK and result.reference is not None:
            return tr("GeoIfcAssets", "IFC reference found: {source}").format(
                source=result.reference.value
            )
        if result.status is FeatureReadStatus.NO_LAYER:
            return tr("GeoIfcAssets", "Select a vector layer with ifc_path or ifc_url.")
        if result.status is FeatureReadStatus.INVALID_LAYER:
            return tr("GeoIfcAssets", "The active layer must contain ifc_path or ifc_url.")
        if result.status is FeatureReadStatus.NO_SELECTION:
            return tr("GeoIfcAssets", "Select one GIS feature to open its IFC.")
        if result.status is FeatureReadStatus.EMPTY_REFERENCE:
            return tr("GeoIfcAssets", "The selected feature has no IFC path or URL.")
        return tr("GeoIfcAssets", "The selected feature cannot be used.")
