"""QGIS plugin implementation for GeoIFC Assets."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from geoifcassets.adapters.ifc.reader import IfcReader, IfcReadStatus
from geoifcassets.adapters.qgis.compat import qgis_version
from geoifcassets.adapters.qgis.dock import (
    FeatureListItem,
    GeoIfcAssetsDock,
    LayerListItem,
)
from geoifcassets.adapters.qgis.feature_reader import (
    FeatureIfcReferenceReadResult,
    FeatureReadStatus,
    SelectedFeatureIfcReferenceReader,
)
from geoifcassets.adapters.qgis.i18n import tr
from geoifcassets.adapters.qgis.messages import QgisMessageService
from geoifcassets.adapters.qgis.viewer import IfcViewerDock, _ensure_swiftshader_flag
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
        self._selected_layer: Any | None = None
        self._selected_feature: Any | None = None

    def initGui(self) -> None:  # noqa: N802
        """Create menu, toolbar action and dock."""
        # Set Chromium flags as early as possible (before any QWebEngineView
        # is created in this QGIS session) so SwiftShader applies on first use.
        _ensure_swiftshader_flag()

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

        if self._viewer_dock is not None:
            self._viewer_dock.destroy()
            self._viewer_dock = None

        if self._dock is not None:
            self._dock.qwidget().close()
            self._dock = None

        self._logger.info("Plugin unloaded")

    def _show_dock(self) -> None:
        from qgis.PyQt.QtCore import Qt

        if self._dock is None:
            self._viewer_dock = IfcViewerDock()
            self._dock = GeoIfcAssetsDock(
                on_refresh_layers=self._available_ifc_layers,
                on_layer_selected=self._features_for_layer,
                on_feature_selected=self._select_feature,
                on_open_viewer=self._open_viewer,
                viewer_widget=self._viewer_dock.qwidget(),
            )
            dock_area = getattr(Qt, "RightDockWidgetArea", None)
            if dock_area is None:
                dock_area = Qt.DockWidgetArea.RightDockWidgetArea
            self._iface.addDockWidget(dock_area, self._dock.qwidget())

        self._dock.qwidget().show()
        self._messages.info(tr("GeoIfcAssets", "GeoIFC Assets panel opened."))
        self._dock.refresh_layers()

    def _available_ifc_layers(self) -> list[LayerListItem]:
        layers = []
        canvas = getattr(self._iface, "mapCanvas", lambda: None)()
        canvas_layers = getattr(canvas, "layers", lambda: [])()
        for layer in canvas_layers:
            if not _is_vector_layer(layer):
                continue
            fields = [field.name() for field in layer.fields()]
            if "ifc_path" not in fields and "ifc_url" not in fields:
                continue
            layers.append(
                LayerListItem(layer_id=layer.id(), name=layer.name())
            )
        return layers

    def _features_for_layer(self, layer_id: str) -> list[FeatureListItem]:
        layer = self._layer_by_id(layer_id)
        if layer is None:
            self._sync_current_feature(
                self._feature_reader.read_from_feature(None, None)
            )
            return []
        self._selected_layer = layer
        self._selected_feature = None
        self._sync_current_feature(
            self._feature_reader.read_from_feature(layer, None)
        )
        features = []
        fields = [field.name() for field in layer.fields()]
        for feature in layer.getFeatures():
            source = _feature_ifc_source(feature, fields)
            features.append(
                FeatureListItem(
                    feature_id=feature.id(),
                    label=_feature_label(feature),
                    ifc_source=source,
                )
            )
        return features

    def _select_feature(self, layer_id: str, feature_id: int) -> None:
        layer = self._layer_by_id(layer_id)
        feature = _feature_by_id(layer, feature_id)
        self._selected_layer = layer
        self._selected_feature = feature

        result = self._feature_reader.read_from_feature(layer, feature)
        self._sync_current_feature(result)

        if self._current_reference is not None and self._viewer_dock is not None:
            self._viewer_dock.open_reference(self._current_reference)
        elif self._viewer_dock is not None:
            self._viewer_dock.clear_reference()

    def _sync_current_feature(
        self, result: FeatureIfcReferenceReadResult
    ) -> None:
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

    def _layer_by_id(self, layer_id: str) -> Any | None:
        canvas = getattr(self._iface, "mapCanvas", lambda: None)()
        for layer in getattr(canvas, "layers", lambda: [])():
            if getattr(layer, "id", lambda: None)() == layer_id:
                return layer
        return None

    def _open_viewer(self) -> None:
        if self._current_reference is None:
            self._messages.warning(tr("GeoIfcAssets", "No IFC reference is available."))
            return

        if self._viewer_dock is not None:
            self._viewer_dock.open_reference(self._current_reference)
        if self._dock is not None:
            self._dock.switch_to_viewer_tab()

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


def _is_vector_layer(layer: Any) -> bool:
    try:
        from qgis.core import QgsMapLayer

        vector_type = getattr(QgsMapLayer, "VectorLayer", None)
        if vector_type is None:
            vector_type = QgsMapLayer.LayerType.VectorLayer
        return layer.type() == vector_type
    except Exception:  # noqa: BLE001
        return hasattr(layer, "getFeatures") and hasattr(layer, "fields")


def _feature_by_id(layer: Any | None, feature_id: int) -> Any | None:
    if layer is None:
        return None
    for feature in layer.getFeatures():
        if feature.id() == feature_id:
            return feature
    return None


def _feature_ifc_source(feature: Any, fields: list[str]) -> str:
    for field_name in ("ifc_path", "ifc_url"):
        if field_name in fields:
            value = str(feature[field_name] or "").strip()
            if value:
                return value
    return ""


def _feature_label(feature: Any) -> str:
    for field_name in ("name", "nombre", "Name", "Nombre"):
        try:
            value = str(feature[field_name] or "").strip()
        except Exception:  # noqa: BLE001
            continue
        if value:
            return value
    return tr("GeoIfcAssets", "Feature {feature_id}").format(
        feature_id=feature.id()
    )
