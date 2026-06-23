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
        self._active_storey: dict | None = None

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
            self._viewer_dock = IfcViewerDock(on_transfer=self._handle_transfer)
            self._dock = GeoIfcAssetsDock(
                on_refresh_layers=self._available_ifc_layers,
                on_layer_selected=self._features_for_layer,
                on_feature_selected=self._select_feature,
                on_open_viewer=self._open_viewer,
                viewer_widget=self._viewer_dock.qwidget(),
                on_generate_footprint=self._generate_footprint,
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

        self._active_storey = None
        if self._dock is not None:
            self._dock.set_active_storey(None)

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

    def _handle_transfer(self, data: dict) -> None:
        """Receive a transfer message from the viewer (Qt main thread).

        Dispatches on ``data["type"]``:
        - ``"storey_selected"`` — storey filter changed in the viewer
        - anything else         — BIM→GIS property transfer (legacy default)
        """
        msg_type = data.get("type")
        if msg_type == "storey_selected":
            self._handle_storey_selected(data)
        else:
            self._logger.info(
                "BIM→GIS transfer received", pset=data.get("pset"), key=data.get("key")
            )
            self._show_transfer_dialog(data)

    def _handle_storey_selected(self, data: dict) -> None:
        """Update active storey state when the viewer storey bar changes."""
        storey_id = data.get("storey_id")
        storey_name = data.get("storey_name")
        if storey_id is None:
            self._active_storey = None
            if self._dock is not None:
                self._dock.set_active_storey(None)
            self._logger.info("Storey filter cleared in viewer")
        else:
            self._active_storey = data
            if self._dock is not None:
                self._dock.set_active_storey(storey_name)
            self._logger.info("Storey selected in viewer", storey_id=storey_id, storey_name=storey_name)

    def _ask_manual_georef(self) -> "GeorefInfo | None":  # type: ignore[name-defined]
        """Show a dialog to collect an EPSG code when the IFC has no IfcMapConversion.

        Returns a GeorefInfo with identity transformation (coordinates pass through
        unchanged) using the user-supplied CRS, or None if the user cancels.
        """
        from geoifcassets.adapters.ifc.footprint_extractor import GeorefInfo  # noqa: PLC0415
        from qgis.PyQt.QtWidgets import (  # noqa: PLC0415
            QDialog,
            QDialogButtonBox,
            QFormLayout,
            QLabel,
            QLineEdit,
            QVBoxLayout,
        )

        dlg = QDialog()
        dlg.setWindowTitle(tr("GeoIfcAssets", "Specify CRS for IFC footprint"))
        dlg.setMinimumWidth(420)
        layout = QVBoxLayout(dlg)

        info = QLabel(
            tr(
                "GeoIfcAssets",
                "No IfcMapConversion found in this IFC file.\n\n"
                "If the model coordinates are already in a known projected CRS "
                "(e.g. exported directly in UTM), enter its EPSG code and the "
                "geometry will be used as-is without any coordinate transformation.",
            )
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        form = QFormLayout()
        epsg_input = QLineEdit()
        epsg_input.setPlaceholderText(tr("GeoIfcAssets", "e.g. 25830"))
        form.addRow(tr("GeoIfcAssets", "EPSG code:"), epsg_input)
        layout.addLayout(form)

        try:
            ok_cancel = QDialogButtonBox.Ok | QDialogButtonBox.Cancel  # type: ignore[attr-defined]
        except AttributeError:
            ok_cancel = (
                QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
            )
        buttons = QDialogButtonBox(ok_cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)

        if not dlg.exec():
            return None

        epsg_raw = epsg_input.text().strip().lstrip("EPSGepsg: ")
        if not epsg_raw.isdigit():
            self._messages.warning(
                tr("GeoIfcAssets", "Invalid EPSG code. Enter digits only (e.g. 25830).")
            )
            return None

        self._logger.info("Manual CRS supplied for footprint", epsg=epsg_raw)
        return GeorefInfo(
            eastings=0.0,
            northings=0.0,
            orthogonal_height=0.0,
            x_axis_abscissa=1.0,
            x_axis_ordinate=0.0,
            scale=1.0,
            crs_name=f"EPSG:{epsg_raw}",
            epsg=epsg_raw,
        )

    def _generate_footprint(self) -> None:
        """Extract floor footprint from current IFC and add it as a temporary QGIS layer."""
        from geoifcassets.adapters.ifc.footprint_extractor import (  # noqa: PLC0415
            FootprintExtractError,
            GeorefInfo,
            detect_georef,
            diagnose_georef,
            extract_storey_footprint,
        )
        from geoifcassets.adapters.qgis.footprint_layer import add_footprint_layer  # noqa: PLC0415

        if self._current_reference is None:
            self._messages.warning(tr("GeoIfcAssets", "No IFC file is loaded."))
            return

        if self._active_storey is None:
            self._messages.warning(
                tr("GeoIfcAssets", "Select a storey in the IFC viewer before generating the footprint.")
            )
            return

        ifc_path = self._current_reference.value
        if ifc_path.startswith(("http://", "https://")):
            self._messages.warning(
                tr("GeoIfcAssets", "Floor footprint is only available for local IFC files.")
            )
            return

        storey_id: int = self._active_storey.get("storey_id")
        storey_name: str = self._active_storey.get("storey_name") or f"Storey #{storey_id}"

        georef = detect_georef(ifc_path)
        if georef is None:
            diag = diagnose_georef(ifc_path)
            if self._dock is not None:
                self._dock.add_user_log(
                    tr("GeoIfcAssets", "Georeferencing diagnostic: {diag}").format(diag=diag)
                )
            self._logger.warning("No IfcMapConversion — asking for manual CRS", source=ifc_path, diag=diag)
            georef = self._ask_manual_georef()
            if georef is None:
                return

        try:
            footprint = extract_storey_footprint(ifc_path, storey_id, storey_name, georef)
        except FootprintExtractError as exc:
            self._messages.warning(
                tr("GeoIfcAssets", "Could not extract floor footprint: {error}").format(
                    error=str(exc)
                )
            )
            self._logger.warning("Footprint extraction failed", error=str(exc))
            return

        try:
            add_footprint_layer(footprint, ifc_path)
        except Exception as exc:  # noqa: BLE001
            self._messages.warning(
                tr("GeoIfcAssets", "Could not create QGIS layer: {error}").format(error=str(exc))
            )
            self._logger.error("Footprint layer creation failed", error=str(exc))
            return

        msg = tr(
            "GeoIfcAssets",
            "Floor '{storey}' added as temporary QGIS layer ({crs}).",
        ).format(storey=storey_name, crs=footprint.crs_auth_id)
        if footprint.used_fallback:
            msg += " " + tr(
                "GeoIfcAssets",
                "(No IfcSlab found — all elements used as geometry source.)",
            )

        self._messages.info(msg)
        if self._dock is not None:
            self._dock.add_user_log(msg)
        self._logger.info(
            "Footprint layer created",
            storey=storey_name,
            crs=footprint.crs_auth_id,
            elements=footprint.element_count,
            used_fallback=footprint.used_fallback,
        )

    def _show_transfer_dialog(self, data: dict) -> None:
        """Open a dialog that maps one BIM property value onto a GIS layer field."""
        from qgis.PyQt.QtWidgets import (
            QComboBox,
            QDialog,
            QDialogButtonBox,
            QFormLayout,
            QLabel,
            QVBoxLayout,
        )

        layer = self._selected_layer
        feature = self._selected_feature
        if layer is None or feature is None:
            self._messages.warning(
                tr("GeoIfcAssets", "No GIS feature selected. Select a feature before transferring.")
            )
            return

        pset = data.get("pset", "")
        key = data.get("key", "")
        value = str(data.get("value", ""))

        dlg = QDialog()
        dlg.setWindowTitle(tr("GeoIfcAssets", "Transfer BIM property to GIS"))
        dlg.setMinimumWidth(400)

        outer = QVBoxLayout(dlg)

        form = QFormLayout()
        pset_label = pset if pset else tr("GeoIfcAssets", "Attributes")
        form.addRow(tr("GeoIfcAssets", "Property set:"), QLabel(pset_label))
        form.addRow(tr("GeoIfcAssets", "Property:"), QLabel(key))
        form.addRow(tr("GeoIfcAssets", "Value:"), QLabel(value))
        outer.addLayout(form)

        outer.addSpacing(8)
        outer.addWidget(
            QLabel(
                tr("GeoIfcAssets", "Target field in layer «{layer}»:").format(
                    layer=layer.name()
                )
            )
        )

        fields = [field.name() for field in layer.fields()]
        combo = QComboBox()
        combo.addItems(fields)
        combo.setEditable(True)
        outer.addWidget(combo)

        try:
            ok_cancel = QDialogButtonBox.Ok | QDialogButtonBox.Cancel  # type: ignore[attr-defined]
        except AttributeError:
            ok_cancel = (
                QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
            )
        buttons = QDialogButtonBox(ok_cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        outer.addWidget(buttons)

        if not dlg.exec():
            return

        field_name = combo.currentText().strip()
        if not field_name:
            return

        if field_name not in fields:
            from qgis.PyQt.QtCore import QVariant
            from qgis.core import QgsField

            layer.startEditing()
            layer.addAttribute(QgsField(field_name, QVariant.String))
            if not layer.commitChanges():
                self._messages.warning(
                    tr("GeoIfcAssets", "Could not add field «{field}» to layer.").format(
                        field=field_name
                    )
                )
                return

        field_index = layer.fields().indexOf(field_name)
        if field_index < 0:
            self._messages.warning(
                tr("GeoIfcAssets", "Field «{field}» not found in layer.").format(field=field_name)
            )
            return

        feature_id = feature.id()
        layer.startEditing()
        ok = layer.changeAttributeValue(feature_id, field_index, value)
        if ok:
            layer.commitChanges()
            msg = tr(
                "GeoIfcAssets",
                "BIM property «{key}» → GIS field «{field}» written.",
            ).format(key=key, field=field_name)
            self._messages.info(msg)
            if self._dock is not None:
                self._dock.add_user_log(msg)
            self._logger.info(
                "BIM→GIS transfer complete",
                key=key,
                value=value,
                layer=layer.name(),
                field=field_name,
                feature_id=feature_id,
            )
        else:
            layer.rollBack()
            self._messages.warning(
                tr("GeoIfcAssets", "Could not write value to field «{field}».").format(
                    field=field_name
                )
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
