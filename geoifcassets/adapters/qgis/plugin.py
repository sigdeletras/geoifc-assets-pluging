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
        self._last_extracted_ifc: str | None = None
        self._last_discoveries: list = []
        self._core_template: Any | None = None
        self._custom_template: Any | None = None
        self._last_extracted_fields: dict[str, Any] = {}

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
                on_metric_transfer=self._on_metric_transfer,
                on_browse_ifc=self._browse_ifc_file,
                on_create_temp_layer=self._show_create_temp_layer_dialog,
                on_add_to_layer=self._show_add_to_layer_dialog,
                on_load_json_template=self._load_json_template_file,
                on_load_to_gis=self._handle_load_to_gis,
            )
            self._load_default_template()
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
                    label=_feature_label(feature, source),
                    ifc_source=source,
                )
            )
        return features

    def _select_feature(self, layer_id: str, feature_id: int) -> None:
        layer = self._layer_by_id(layer_id)
        feature = _feature_by_id(layer, feature_id)
        self._selected_layer = layer
        self._selected_feature = feature

        if feature is not None and layer is not None:
            geom = feature.geometry()
            if geom and not geom.isNull():
                from qgis.core import QgsCoordinateTransform, QgsProject  # noqa: PLC0415
                canvas = self._iface.mapCanvas()
                bbox = geom.boundingBox()
                layer_crs = layer.crs()
                canvas_crs = canvas.mapSettings().destinationCrs()
                if layer_crs != canvas_crs:
                    transform = QgsCoordinateTransform(
                        layer_crs, canvas_crs, QgsProject.instance()
                    )
                    bbox = transform.transformBoundingBox(bbox)
                bbox.scale(1.5)
                canvas.setExtent(bbox)
                canvas.refresh()

        result = self._feature_reader.read_from_feature(layer, feature)
        self._sync_current_feature(result)

        self._active_storey = None
        if self._dock is not None:
            self._dock.set_active_storey(None)

        if self._viewer_dock is not None and self._current_reference is None:
            self._viewer_dock.clear_reference()
            if self._dock is not None:
                self._dock.clear_model_metrics()

    def _open_viewer_for_feature(self, layer_id: str, feature_id: int) -> None:
        self._select_feature(layer_id, feature_id)
        if self._current_reference is not None and self._viewer_dock is not None:
            self._viewer_dock.open_reference(self._current_reference)
            if self._dock is not None:
                self._dock.switch_to_layer_tab()
            ifc_path = self._current_reference.value
            if not ifc_path.startswith(("http://", "https://")):
                self._extract_and_show_metrics(ifc_path)
            else:
                if self._dock is not None:
                    self._dock.clear_model_metrics()

    def _sync_current_feature(
        self, result: FeatureIfcReferenceReadResult
    ) -> None:
        self._current_reference = result.reference
        message = self._message_for_read_result(result)

        if self._dock is not None:
            self._dock.set_status(message, can_open_viewer=result.reference is not None)
            self._dock.add_user_log(message)
            self._dock.set_ifc_actions_enabled(result.reference is not None)

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
            self._dock.switch_to_layer_tab()

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

        ifc_path = self._current_reference.value
        if not ifc_path.startswith(("http://", "https://")):
            self._extract_and_show_metrics(ifc_path)
        else:
            if self._dock is not None:
                self._dock.clear_model_metrics()

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
            layer_crs = add_footprint_layer(footprint, ifc_path)
        except Exception as exc:  # noqa: BLE001
            self._messages.warning(
                tr("GeoIfcAssets", "Could not create QGIS layer: {error}").format(error=str(exc))
            )
            self._logger.error("Footprint layer creation failed", error=str(exc))
            return

        crs_note = layer_crs
        if layer_crs != footprint.crs_auth_id:
            crs_note = tr(
                "GeoIfcAssets", "{layer_crs}, reprojected from {ifc_crs}"
            ).format(layer_crs=layer_crs, ifc_crs=footprint.crs_auth_id)

        msg = tr(
            "GeoIfcAssets",
            "Floor '{storey}' added as temporary QGIS layer ({crs}).",
        ).format(storey=storey_name, crs=crs_note)
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

    def _extract_and_show_metrics(self, ifc_path: str) -> None:
        """Run model info and quantity extractors and populate the dock metrics panel."""
        from geoifcassets.adapters.ifc.model_info_extractor import extract_model_info  # noqa: PLC0415
        from geoifcassets.adapters.ifc.quantity_extractor import extract_quantities  # noqa: PLC0415

        if ifc_path == self._last_extracted_ifc:
            return

        self._last_extracted_ifc = ifc_path
        if self._dock is not None:
            self._dock.clear_model_metrics()

        metrics = extract_model_info(ifc_path) + extract_quantities(ifc_path)

        if self._dock is not None:
            self._dock.set_model_metrics(metrics)
            if metrics:
                self._dock.add_user_log(
                    tr("GeoIfcAssets", "{count} model metrics extracted.").format(count=len(metrics))
                )
            else:
                self._dock.add_user_log(tr("GeoIfcAssets", "No model metrics could be extracted."))

        self._logger.info("Model metrics extracted", count=len(metrics), ifc_path=ifc_path)
        self._extract_and_show_fields(ifc_path)
        self._discover_and_show_ifc_classes(ifc_path)

    def _extract_and_show_fields(self, ifc_path: str) -> None:
        """Extract core + custom template fields from the IFC and populate the Extract tab."""
        if self._dock is None or self._core_template is None:
            return
        from geoifcassets.adapters.ifc.custom_field_extractor import (  # noqa: PLC0415
            extract_custom_fields,
        )
        from geoifcassets.adapters.ifc.ifc_field_extractor import extract_fields  # noqa: PLC0415

        core_names = [f.name for f in self._core_template.fields]
        values = extract_fields(ifc_path, core_names)

        if self._custom_template is not None:
            values.update(extract_custom_fields(ifc_path, self._custom_template.fields))

        self._last_extracted_fields = values
        self._dock.set_extract_values(values)
        self._logger.info(
            "Extract tab values populated",
            core_fields=len(core_names),
            custom_fields=len(self._custom_template.fields) if self._custom_template else 0,
            non_null=sum(1 for v in values.values() if v is not None),
            ifc_path=ifc_path,
        )

    def _discover_and_show_ifc_classes(self, ifc_path: str) -> None:
        """Discover IFC classes in the model and populate the Properties IFC Classes section."""
        if self._dock is None:
            return
        from geoifcassets.adapters.ifc.class_extractor import discover_ifc_classes  # noqa: PLC0415

        self._last_discoveries = discover_ifc_classes(ifc_path)
        classes_info = [
            {
                "ifc_class": c.ifc_class,
                "count": c.count,
                "available": c.available,
                "values": c.values,
                "sources": c.sources,
            }
            for c in self._last_discoveries
        ]
        self._dock.set_ifc_classes(classes_info)
        self._logger.info(
            "IFC classes discovered", classes=len(self._last_discoveries), ifc_path=ifc_path
        )

    def _qgis_locale(self) -> str:
        """Return the two-letter QGIS UI language code (e.g. 'es'). Falls back to 'en'."""
        try:
            from qgis.core import QgsApplication  # noqa: PLC0415
            raw = QgsApplication.locale() or "en"
            return raw.split("_")[0].lower()
        except Exception:  # noqa: BLE001
            return "en"

    def _load_default_template(self) -> None:
        """Load ifc_core_catalog_v2 as the fixed core template and set it on the dock."""
        from geoifcassets.core.template_loader import load_builtin_template  # noqa: PLC0415

        try:
            template = load_builtin_template("ifc_core_catalog_v2", locale=self._qgis_locale())
        except (ValueError, FileNotFoundError) as exc:
            self._logger.warning("Could not load core template", error=str(exc))
            return

        self._core_template = template
        if self._dock is not None:
            self._dock.set_core_template(template)
        self._logger.info("Core template loaded", template=template.template_name)

    def _load_json_template_file(self) -> None:
        """Open a file dialog and load a custom template JSON to add alongside core fields."""
        from qgis.PyQt.QtWidgets import QFileDialog, QMessageBox  # noqa: PLC0415

        from geoifcassets.core.template_loader import load_template_from_path  # noqa: PLC0415

        path, _ = QFileDialog.getOpenFileName(
            None,
            tr("GeoIfcAssets", "Load custom extraction template"),
            "",
            tr("GeoIfcAssets", "JSON files (*.json);;All files (*)"),
        )
        if not path:
            return

        try:
            template = load_template_from_path(path, locale=self._qgis_locale())
        except ValueError as exc:
            self._messages.warning(
                tr("GeoIfcAssets", "Invalid template file: {error}").format(error=str(exc))
            )
            return

        # Conflict detection: warn if any custom field name duplicates a core field name
        if self._core_template is not None:
            core_names = {f.name for f in self._core_template.fields}
            conflicts = [f.name for f in template.fields if f.name in core_names]
            if conflicts:
                msg = tr(
                    "GeoIfcAssets",
                    "Custom template has {n} field name(s) that conflict with core fields: {names}. "
                    "These fields will be skipped.",
                ).format(n=len(conflicts), names=", ".join(conflicts[:5]))
                QMessageBox.warning(None, tr("GeoIfcAssets", "Field name conflict"), msg)
                self._logger.warning(
                    "Custom template has conflicting field names",
                    conflicts=conflicts,
                )

        self._custom_template = template
        if self._dock is not None:
            self._dock.set_custom_template(template)
            self._dock.add_user_log(
                tr("GeoIfcAssets", "Custom template loaded: {name}").format(
                    name=template.template_name
                )
            )

        if self._last_extracted_ifc:
            self._extract_and_show_fields(self._last_extracted_ifc)

        self._logger.info("Custom template loaded", path=path, template=template.template_name)

    def _handle_load_to_gis(self) -> None:
        """Write selected Extract tab fields to the active GIS feature."""
        from qgis.PyQt.QtCore import QVariant  # noqa: PLC0415
        from qgis.PyQt.QtWidgets import (  # noqa: PLC0415
            QDialog,
            QDialogButtonBox,
            QLabel,
            QVBoxLayout,
        )
        from qgis.core import QgsField  # noqa: PLC0415

        layer = self._selected_layer
        feature = self._selected_feature
        if layer is None or feature is None:
            self._messages.warning(
                tr("GeoIfcAssets", "No GIS feature selected. Select a feature before loading.")
            )
            return

        if self._dock is None:
            return

        selected_field_names = self._dock.get_selected_fields()
        class_pairs = self._dock.get_selected_class_metrics()

        if not selected_field_names and not class_pairs:
            self._messages.warning(
                tr("GeoIfcAssets", "No fields or class metrics selected.")
            )
            return

        if not self._last_extracted_fields and not self._last_extracted_ifc:
            self._messages.warning(
                tr("GeoIfcAssets", "No IFC data extracted yet. Select an IFC feature first.")
            )
            return

        # Build updates from fields tree
        values_to_write: dict[str, Any] = {
            name: self._last_extracted_fields[name]
            for name in selected_field_names
            if name in self._last_extracted_fields
            and self._last_extracted_fields[name] is not None
        }

        # Include class metrics from pre-computed discovery results (no re-read of IFC)
        if class_pairs and self._last_discoveries:
            from geoifcassets.adapters.ifc.class_extractor import discoveries_to_fields  # noqa: PLC0415

            class_values = discoveries_to_fields(self._last_discoveries, class_pairs)
            values_to_write.update(class_values)

        if not values_to_write:
            self._messages.warning(
                tr("GeoIfcAssets", "All selected fields are empty in the current IFC.")
            )
            return

        existing_fields = {f.name() for f in layer.fields()}
        fields_to_create = [n for n in values_to_write if n not in existing_fields]

        if fields_to_create:
            dlg = QDialog()
            dlg.setWindowTitle(tr("GeoIfcAssets", "Create new GIS fields"))
            layout = QVBoxLayout(dlg)
            layout.addWidget(QLabel(
                tr(
                    "GeoIfcAssets",
                    "{n} new field(s) will be created in layer «{layer}». Continue?",
                ).format(n=len(fields_to_create), layer=layer.name())
            ))
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
                return

            layer.startEditing()
            for field_name in fields_to_create:
                val = values_to_write[field_name]
                if isinstance(val, bool):
                    qtype = QVariant.Bool
                elif isinstance(val, int):
                    qtype = QVariant.Int
                elif isinstance(val, float):
                    qtype = QVariant.Double
                else:
                    qtype = QVariant.String
                layer.addAttribute(QgsField(field_name, qtype))
            if not layer.commitChanges():
                self._messages.warning(
                    tr("GeoIfcAssets", "Could not create new fields in layer.")
                )
                return

        feature_id = feature.id()
        layer.startEditing()
        written: list[str] = []
        for field_name, value in values_to_write.items():
            field_index = layer.fields().indexOf(field_name)
            if field_index < 0:
                continue
            str_value = str(value) if not isinstance(value, (int, float, bool)) else value
            if layer.changeAttributeValue(feature_id, field_index, str_value):
                written.append(field_name)

        self._apply_status_updates(layer, feature_id, success=bool(written))
        layer.commitChanges()

        msg = tr(
            "GeoIfcAssets",
            "{n} field(s) written to feature {fid} in layer «{layer}».",
        ).format(n=len(written), fid=feature_id, layer=layer.name())
        self._messages.info(msg)
        if self._dock is not None:
            self._dock.add_user_log(msg)
            self._dock.set_extract_status(msg)
        self._logger.info(
            "Extract batch write complete",
            written=written,
            layer=layer.name(),
            feature_id=feature_id,
        )

    def _on_metric_transfer(self, metric: object) -> None:
        """Forward a model metric to the BIM→GIS transfer dialog."""
        from geoifcassets.core.models import ModelMetric  # noqa: PLC0415

        if not isinstance(metric, ModelMetric):
            return
        self._show_transfer_dialog({
            "pset": "IFC Model",
            "key": metric.label,
            "value": metric.value,
        })

    def _apply_status_updates(
        self,
        layer: Any,
        feature_id: int,
        *,
        success: bool,
        error_message: str = "",
    ) -> None:
        """Write ifc_status, ifc_updated_at and ifc_error to the layer if those fields exist.

        Must be called within an already-open editing session.
        """
        from datetime import datetime, timezone

        from geoifcassets.core.mapping import build_status_updates

        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        field_names = [f.name() for f in layer.fields()]
        updates = build_status_updates(
            field_names, success=success, timestamp=timestamp, error_message=error_message
        )
        for update in updates:
            idx = layer.fields().indexOf(update.field_name)
            if idx >= 0:
                layer.changeAttributeValue(feature_id, idx, update.value)

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
            self._apply_status_updates(layer, feature_id, success=True)
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
            error_msg = tr(
                "GeoIfcAssets", "Could not write value to field «{field}»."
            ).format(field=field_name)
            if layer.startEditing():
                self._apply_status_updates(
                    layer, feature_id, success=False, error_message=error_msg
                )
                layer.commitChanges()
            self._messages.warning(error_msg)

    def _browse_ifc_file(self) -> None:
        """Open a file dialog and load an IFC directly, without a GIS layer."""
        from qgis.PyQt.QtWidgets import QFileDialog  # noqa: PLC0415

        from geoifcassets.core.models import IfcReference, IfcReferenceKind  # noqa: PLC0415

        path, _ = QFileDialog.getOpenFileName(
            None,
            tr("GeoIfcAssets", "Open IFC file"),
            "",
            tr("GeoIfcAssets", "IFC files (*.ifc *.ifczip *.ifcxml);;All files (*)"),
        )
        if not path:
            return

        self._current_reference = IfcReference(kind=IfcReferenceKind.PATH, value=path)
        self._selected_layer = None
        self._selected_feature = None
        self._active_storey = None

        if self._viewer_dock is not None:
            self._viewer_dock.open_reference(self._current_reference)
        if self._dock is not None:
            self._dock.switch_to_layer_tab()
            self._dock.set_active_storey(None)
            self._dock.set_ifc_actions_enabled(True)
            self._dock.add_user_log(
                tr("GeoIfcAssets", "IFC file opened: {name}").format(name=Path(path).name)
            )

        self._logger.info("IFC file opened directly (no GIS layer)", path=path)
        self._extract_and_show_metrics(path)

    def _show_create_temp_layer_dialog(self, geom_type: str) -> None:
        """Create a temporary memory layer and activate digitizing so the user draws the geometry."""
        from qgis.PyQt.QtWidgets import (  # noqa: PLC0415
            QDialog,
            QDialogButtonBox,
            QFormLayout,
            QLabel,
            QLineEdit,
            QVBoxLayout,
        )
        from qgis.core import QgsDefaultValue, QgsProject, QgsVectorLayer  # noqa: PLC0415

        if self._current_reference is None:
            self._messages.warning(tr("GeoIfcAssets", "No IFC file is loaded."))
            return

        ifc_path = self._current_reference.value
        ifc_name = Path(ifc_path).name

        dlg = QDialog()
        dlg.setWindowTitle(
            tr("GeoIfcAssets", "Create temporary {type} layer").format(type=geom_type)
        )
        dlg.setMinimumWidth(420)
        layout = QVBoxLayout(dlg)

        info = QLabel(
            tr(
                "GeoIfcAssets",
                "A temporary {type} layer will be created. After confirming, draw the"
                " geometry on the map canvas.",
            ).format(type=geom_type)
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        form = QFormLayout()
        name_input = QLineEdit(f"GeoIFC — {ifc_name}")
        form.addRow(tr("GeoIfcAssets", "Layer name:"), name_input)
        url_input = QLineEdit(ifc_path)
        form.addRow(tr("GeoIfcAssets", "IFC path:"), url_input)
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
            return

        layer_name = name_input.text().strip() or f"GeoIFC — {ifc_name}"
        ifc_url_value = url_input.text().strip()

        wkb_type = {"Point": "Point", "Line": "LineString", "Polygon": "Polygon"}.get(
            geom_type, "Point"
        )
        try:
            project_crs = QgsProject.instance().crs()
            crs_authid = project_crs.authid() if project_crs.isValid() else "EPSG:4326"
        except Exception:  # noqa: BLE001
            crs_authid = "EPSG:4326"

        uri = f"{wkb_type}?crs={crs_authid}&field=ifc_file:string&field=ifc_url:string"
        layer = QgsVectorLayer(uri, layer_name, "memory")
        if not layer.isValid():
            self._messages.warning(tr("GeoIfcAssets", "Could not create temporary layer."))
            return

        # Pre-fill field defaults so the attribute form shows the IFC reference after drawing
        file_idx = layer.fields().indexOf("ifc_file")
        url_idx = layer.fields().indexOf("ifc_url")
        if file_idx >= 0:
            layer.setDefaultValueDefinition(
                file_idx, QgsDefaultValue(_qgis_literal(ifc_name))
            )
        if url_idx >= 0:
            layer.setDefaultValueDefinition(
                url_idx, QgsDefaultValue(_qgis_literal(ifc_url_value))
            )

        QgsProject.instance().addMapLayer(layer)
        self._iface.setActiveLayer(layer)
        layer.startEditing()
        _trigger_add_feature(self._iface)

        msg = tr(
            "GeoIfcAssets",
            "Layer '{name}' ready. Draw the {type} on the map canvas.",
        ).format(name=layer_name, type=geom_type)
        self._messages.info(msg)
        if self._dock is not None:
            self._dock.add_user_log(msg)
            self._dock.refresh_layers()
        self._logger.info(
            "Temporary GIS layer created, digitizing activated",
            layer_name=layer_name,
            geom_type=geom_type,
            ifc_path=ifc_url_value,
        )

    def _show_add_to_layer_dialog(self) -> None:
        """Activate digitizing on an existing layer; fill IFC fields after the user draws."""
        from qgis.PyQt.QtWidgets import (  # noqa: PLC0415
            QComboBox,
            QDialog,
            QDialogButtonBox,
            QFormLayout,
            QLabel,
            QLineEdit,
            QVBoxLayout,
        )

        if self._current_reference is None:
            self._messages.warning(tr("GeoIfcAssets", "No IFC file is loaded."))
            return

        ifc_path = self._current_reference.value
        ifc_name = Path(ifc_path).name

        canvas = getattr(self._iface, "mapCanvas", lambda: None)()
        all_layers = getattr(canvas, "layers", lambda: [])()
        vector_layers = [layer for layer in all_layers if _is_vector_layer(layer)]

        if not vector_layers:
            self._messages.warning(
                tr("GeoIfcAssets", "No vector layers are loaded in the project.")
            )
            return

        dlg = QDialog()
        dlg.setWindowTitle(tr("GeoIfcAssets", "Add feature to existing GIS layer"))
        dlg.setMinimumWidth(440)
        layout = QVBoxLayout(dlg)

        info = QLabel(
            tr(
                "GeoIfcAssets",
                "Select a layer and confirm the IFC reference. After confirming, draw"
                " the geometry on the map canvas.",
            )
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        form = QFormLayout()
        layer_combo = QComboBox()
        for lyr in vector_layers:
            layer_combo.addItem(lyr.name())
        form.addRow(tr("GeoIfcAssets", "Target layer:"), layer_combo)
        url_input = QLineEdit(ifc_path)
        form.addRow(tr("GeoIfcAssets", "IFC path / URL:"), url_input)
        name_input = QLineEdit(ifc_name)
        form.addRow(tr("GeoIfcAssets", "IFC file name:"), name_input)
        layout.addLayout(form)

        note = QLabel(
            tr(
                "GeoIfcAssets",
                "ifc_path or ifc_url and ifc_file will be filled automatically "
                "after drawing if those fields exist in the layer.",
            )
        )
        note.setWordWrap(True)
        layout.addWidget(note)

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
            return

        target_layer = vector_layers[layer_combo.currentIndex()]
        ifc_path_value = url_input.text().strip()
        ifc_name_value = name_input.text().strip()

        if not target_layer.isEditable():
            if not target_layer.startEditing():
                self._messages.warning(
                    tr("GeoIfcAssets", "Layer '{layer}' cannot be edited.").format(
                        layer=target_layer.name()
                    )
                )
                return

        fields = [f.name() for f in target_layer.fields()]

        def _fill_ifc_on_added(fid: int) -> None:
            try:
                target_layer.featureAdded.disconnect(_fill_ifc_on_added)
            except Exception:  # noqa: BLE001
                pass
            is_local = not ifc_path_value.startswith(("http://", "https://"))
            path_order = ("ifc_path", "ifc_url") if is_local else ("ifc_url", "ifc_path")
            for fname in path_order:
                if fname in fields:
                    idx = target_layer.fields().indexOf(fname)
                    if idx >= 0:
                        target_layer.changeAttributeValue(fid, idx, ifc_path_value)
                    break
            if "ifc_file" in fields:
                idx = target_layer.fields().indexOf("ifc_file")
                if idx >= 0:
                    target_layer.changeAttributeValue(fid, idx, ifc_name_value)
            done_msg = tr(
                "GeoIfcAssets", "Feature added to layer '{layer}' with IFC reference."
            ).format(layer=target_layer.name())
            if self._dock is not None:
                self._dock.add_user_log(done_msg)
            self._logger.info(
                "IFC fields filled after feature draw",
                layer=target_layer.name(),
                fid=fid,
                ifc_path=ifc_path_value,
            )

        target_layer.featureAdded.connect(_fill_ifc_on_added)
        self._iface.setActiveLayer(target_layer)
        _trigger_add_feature(self._iface)

        msg = tr(
            "GeoIfcAssets",
            "Draw the geometry on the map canvas to add the feature to '{layer}'.",
        ).format(layer=target_layer.name())
        self._messages.info(msg)
        if self._dock is not None:
            self._dock.add_user_log(msg)
        self._logger.info(
            "Digitizing activated for existing GIS layer",
            layer=target_layer.name(),
            ifc_path=ifc_path_value,
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


def _feature_label(feature: Any, ifc_source: str = "") -> str:
    for field_name in ("name", "nombre", "Name", "Nombre"):
        try:
            value = str(feature[field_name] or "").strip()
        except Exception:  # noqa: BLE001
            continue
        if value:
            return value
    if ifc_source:
        return Path(ifc_source).name
    return tr("GeoIfcAssets", "Feature {feature_id}").format(
        feature_id=feature.id()
    )


def _qgis_literal(s: str) -> str:
    """Return a QGIS expression string literal for a Python value."""
    return "'" + s.replace("'", "''") + "'"


def _trigger_add_feature(iface: Any) -> None:
    """Trigger the QGIS 'Add Feature' map tool on the active layer, if available."""
    action = getattr(iface, "actionAddFeature", lambda: None)()
    if action is not None:
        action.trigger()
