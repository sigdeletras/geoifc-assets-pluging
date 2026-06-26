"""Initial dock widget for GeoIFC Assets."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from geoifcassets.adapters.qgis.i18n import tr
from geoifcassets.core.models import ModelMetric, PropertyTemplate
from geoifcassets.core.template_loader import group_order_key

# Qt UserRole constants for tree items
_FIELD_NAME_ROLE = 256   # stores IFC field name on Extract tree items
_CLASS_ROLE = 257        # stores IFC class name on Classes tree items
_METRIC_COLS = ("count", "length", "area", "volume")


@dataclass(frozen=True)
class LayerListItem:
    """Layer entry shown in the dock selector."""

    layer_id: str
    name: str


@dataclass(frozen=True)
class FeatureListItem:
    """Feature entry shown in the dock selector."""

    feature_id: int
    label: str
    ifc_source: str


class GeoIfcAssetsDock:
    """Factory wrapper for the QGIS dock widget."""

    def __init__(
        self,
        on_refresh_layers: Callable[[], list[LayerListItem]],
        on_layer_selected: Callable[[str], list[FeatureListItem]],
        on_feature_selected: Callable[[str, int], None],
        on_open_viewer: Callable[[], None],
        viewer_widget: Any | None = None,
        on_generate_footprint: Callable[[], None] | None = None,
        on_metric_transfer: Callable[[ModelMetric], None] | None = None,
        on_browse_ifc: Callable[[], None] | None = None,
        on_create_temp_layer: Callable[[str], None] | None = None,
        on_add_to_layer: Callable[[], None] | None = None,
        on_load_json_template: Callable[[], None] | None = None,
        on_load_to_gis: Callable[[], None] | None = None,
    ) -> None:
        from qgis.PyQt.QtWidgets import (
            QComboBox,
            QDockWidget,
            QFrame,
            QHBoxLayout,
            QLabel,
            QMenu,
            QPushButton,
            QTabWidget,
            QTableWidget,
            QTextEdit,
            QVBoxLayout,
            QWidget,
        )

        self._on_refresh_layers = on_refresh_layers
        self._on_layer_selected = on_layer_selected
        self._on_metric_transfer = on_metric_transfer
        self._on_feature_selected = on_feature_selected
        self._on_load_json_template = on_load_json_template
        self._on_load_to_gis = on_load_to_gis
        self._layer_by_row: dict[int, str] = {}
        self._feature_by_row: dict[int, int] = {}
        self._updating_ui = False
        self._extract_template: PropertyTemplate | None = None

        self.widget = QDockWidget(tr("GeoIfcAssets", "GeoIFC Assets"))
        self.widget.setObjectName("GeoIfcAssetsDock")

        content = QWidget()
        layout = QVBoxLayout(content)

        self._tabs = QTabWidget()
        tabs = self._tabs
        layer_tab = QWidget()
        layer_layout = QVBoxLayout(layer_tab)

        self._browse_ifc_btn = QPushButton(tr("GeoIfcAssets", "Browse IFC file…"))
        self._browse_ifc_btn.setToolTip(
            tr("GeoIfcAssets", "Open an IFC file directly without a GIS layer")
        )
        if on_browse_ifc is not None:
            self._browse_ifc_btn.clicked.connect(on_browse_ifc)
        layer_layout.addWidget(self._browse_ifc_btn)

        _sep = QFrame()
        try:
            _sep.setFrameShape(QFrame.HLine)
            _sep.setFrameShadow(QFrame.Sunken)
        except AttributeError:
            _sep.setFrameShape(QFrame.Shape.HLine)
            _sep.setFrameShadow(QFrame.Shadow.Sunken)
        layer_layout.addWidget(_sep)

        self._layer_combo = QComboBox()
        self._layer_combo.currentIndexChanged.connect(self._select_layer_row)
        layer_layout.addWidget(self._layer_combo)

        self._feature_table = QTableWidget(0, 3)
        self._feature_table.setHorizontalHeaderLabels(
            [
                tr("GeoIfcAssets", "Feature ID"),
                tr("GeoIfcAssets", "Feature"),
                tr("GeoIfcAssets", "IFC source"),
            ]
        )
        self._feature_table.setSelectionBehavior(
            _table_selection_behavior()
        )
        self._feature_table.setSelectionMode(_table_selection_mode())
        self._feature_table.itemSelectionChanged.connect(
            self._select_feature_row
        )
        layer_layout.addWidget(self._feature_table)

        self._refresh_button = QPushButton(tr("GeoIfcAssets", "Refresh layers"))
        self._refresh_button.clicked.connect(self.refresh_layers)
        layer_layout.addWidget(self._refresh_button)

        self._status_label = QLabel(
            tr(
                "GeoIfcAssets",
                "Select a GIS feature with ifc_path or ifc_url to start.",
            )
        )
        self._status_label.setWordWrap(True)
        layer_layout.addWidget(self._status_label)

        self._open_button = QPushButton(tr("GeoIfcAssets", "Open IFC viewer"))
        self._open_button.setEnabled(False)
        self._open_button.clicked.connect(on_open_viewer)
        layer_layout.addWidget(self._open_button)

        if viewer_widget is not None:
            layer_layout.addWidget(viewer_widget)

        footprint_bar = QWidget()
        footprint_bar_layout = QHBoxLayout(footprint_bar)
        footprint_bar_layout.setContentsMargins(4, 4, 4, 4)
        self._storey_label = QLabel(tr("GeoIfcAssets", "No storey selected"))
        self._footprint_btn = QPushButton(tr("GeoIfcAssets", "→ QGIS layer"))
        self._footprint_btn.setEnabled(False)
        self._footprint_btn.setToolTip(
            tr("GeoIfcAssets", "Generate floor footprint as a temporary QGIS layer")
        )
        if on_generate_footprint is not None:
            self._footprint_btn.clicked.connect(on_generate_footprint)
        footprint_bar_layout.addWidget(self._storey_label, 1)
        footprint_bar_layout.addWidget(self._footprint_btn)
        layer_layout.addWidget(footprint_bar)

        gis_actions_bar = QWidget()
        gis_actions_layout = QHBoxLayout(gis_actions_bar)
        gis_actions_layout.setContentsMargins(4, 2, 4, 4)

        self._new_layer_btn = QPushButton(tr("GeoIfcAssets", "New temp layer…"))
        self._new_layer_btn.setEnabled(False)
        self._new_layer_btn.setToolTip(
            tr("GeoIfcAssets", "Create a new temporary GIS layer linked to the current IFC")
        )
        self._new_layer_menu = QMenu()
        for _geom_key, _geom_label in (
            ("Point", tr("GeoIfcAssets", "Point")),
            ("Line", tr("GeoIfcAssets", "Line")),
            ("Polygon", tr("GeoIfcAssets", "Polygon")),
        ):
            _action = self._new_layer_menu.addAction(_geom_label)
            if on_create_temp_layer is not None:
                _action.triggered.connect(
                    lambda checked=False, gt=_geom_key: on_create_temp_layer(gt)
                )
        self._new_layer_btn.setMenu(self._new_layer_menu)

        self._add_to_layer_btn = QPushButton(tr("GeoIfcAssets", "Add to existing layer…"))
        self._add_to_layer_btn.setEnabled(False)
        self._add_to_layer_btn.setToolTip(
            tr("GeoIfcAssets", "Add a new feature to an existing GIS layer with the current IFC")
        )
        if on_add_to_layer is not None:
            self._add_to_layer_btn.clicked.connect(on_add_to_layer)

        gis_actions_layout.addWidget(self._new_layer_btn, 1)
        gis_actions_layout.addWidget(self._add_to_layer_btn, 1)
        layer_layout.addWidget(gis_actions_bar)

        # ── Extract tab ───────────────────────────────────────────────────
        from qgis.PyQt.QtWidgets import (  # noqa: PLC0415
            QHeaderView,
            QSplitter,
            QTreeWidget,
            QTreeWidgetItem,
        )
        from qgis.PyQt.QtCore import Qt  # noqa: PLC0415

        extract_tab = QWidget()
        extract_layout = QVBoxLayout(extract_tab)
        extract_layout.setContentsMargins(4, 4, 4, 4)
        extract_layout.setSpacing(4)

        # Template selector row
        template_bar = QWidget()
        template_bar_layout = QHBoxLayout(template_bar)
        template_bar_layout.setContentsMargins(0, 0, 0, 0)
        self._template_combo = QComboBox()
        self._template_combo.setToolTip(tr("GeoIfcAssets", "Active extraction template"))
        self._load_json_btn = QPushButton(tr("GeoIfcAssets", "Load JSON…"))
        self._load_json_btn.setToolTip(tr("GeoIfcAssets", "Load a custom template from a JSON file"))
        if on_load_json_template is not None:
            self._load_json_btn.clicked.connect(on_load_json_template)
        template_bar_layout.addWidget(self._template_combo, 1)
        template_bar_layout.addWidget(self._load_json_btn)
        extract_layout.addWidget(template_bar)

        # Action row — Select all / Clear / Expand all agrupdos; Load to GIS a la derecha
        action_bar = QWidget()
        action_bar_layout = QHBoxLayout(action_bar)
        action_bar_layout.setContentsMargins(0, 0, 0, 0)
        self._select_all_btn = QPushButton(tr("GeoIfcAssets", "Select all"))
        self._select_all_btn.clicked.connect(self._extract_select_all)
        self._clear_sel_btn = QPushButton(tr("GeoIfcAssets", "Clear"))
        self._clear_sel_btn.clicked.connect(self._extract_clear)
        self._expand_tree_btn = QPushButton(tr("GeoIfcAssets", "Expand all"))
        self._expand_tree_btn.setCheckable(True)
        self._expand_tree_btn.toggled.connect(self._toggle_tree_expand)
        self._load_gis_btn = QPushButton(tr("GeoIfcAssets", "→ Load to GIS"))
        self._load_gis_btn.setEnabled(False)
        self._load_gis_btn.setToolTip(
            tr("GeoIfcAssets", "Write selected fields to the active GIS feature")
        )
        if on_load_to_gis is not None:
            self._load_gis_btn.clicked.connect(on_load_to_gis)
        from qgis.PyQt.QtWidgets import QCheckBox  # noqa: PLC0415

        self._show_with_data_cb = QCheckBox(tr("GeoIfcAssets", "Show only fields with data"))
        self._show_with_data_cb.stateChanged.connect(self._filter_fields_tree)

        action_bar_layout.addWidget(self._select_all_btn)
        action_bar_layout.addWidget(self._clear_sel_btn)
        action_bar_layout.addWidget(self._expand_tree_btn)
        action_bar_layout.addStretch()
        extract_layout.addWidget(action_bar)
        extract_layout.addWidget(self._show_with_data_cb)

        # Fields tree (grupos → campos, 3 columnas) — panel superior del splitter
        self._fields_tree = QTreeWidget()
        self._fields_tree.setColumnCount(4)
        self._fields_tree.setHeaderLabels([
            tr("GeoIfcAssets", "Property"),
            tr("GeoIfcAssets", "GIS field"),
            tr("GeoIfcAssets", "IFC source"),
            tr("GeoIfcAssets", "Value"),
        ])
        try:
            self._fields_tree.header().setSectionResizeMode(0, QHeaderView.Interactive)
            self._fields_tree.header().setSectionResizeMode(1, QHeaderView.Interactive)
            self._fields_tree.header().setSectionResizeMode(2, QHeaderView.Interactive)
            self._fields_tree.header().setSectionResizeMode(3, QHeaderView.Stretch)
        except AttributeError:
            self._fields_tree.header().setSectionResizeMode(
                0, QHeaderView.ResizeMode.Interactive
            )
            self._fields_tree.header().setSectionResizeMode(
                1, QHeaderView.ResizeMode.Interactive
            )
            self._fields_tree.header().setSectionResizeMode(
                2, QHeaderView.ResizeMode.Interactive
            )
            self._fields_tree.header().setSectionResizeMode(
                3, QHeaderView.ResizeMode.Stretch
            )
        self._fields_tree.setColumnWidth(0, 180)
        self._fields_tree.setColumnWidth(1, 120)
        self._fields_tree.setColumnWidth(2, 140)
        self._fields_tree.itemChanged.connect(self._on_tree_item_changed)

        # IFC Classes section — panel inferior del splitter
        _classes_widget = QWidget()
        _classes_vbox = QVBoxLayout(_classes_widget)
        _classes_vbox.setContentsMargins(0, 4, 0, 0)
        _classes_vbox.setSpacing(4)

        _classes_sep = QFrame()
        try:
            _classes_sep.setFrameShape(QFrame.HLine)
            _classes_sep.setFrameShadow(QFrame.Sunken)
        except AttributeError:
            _classes_sep.setFrameShape(QFrame.Shape.HLine)
            _classes_sep.setFrameShadow(QFrame.Shadow.Sunken)
        _classes_vbox.addWidget(_classes_sep)

        _classes_lbl = QLabel(tr("GeoIfcAssets", "IFC Classes"))
        _classes_font = _classes_lbl.font()
        _classes_font.setBold(True)
        _classes_lbl.setFont(_classes_font)
        _classes_vbox.addWidget(_classes_lbl)

        classes_action_bar = QWidget()
        classes_action_layout = QHBoxLayout(classes_action_bar)
        classes_action_layout.setContentsMargins(0, 0, 0, 0)
        self._classes_select_all_btn = QPushButton(tr("GeoIfcAssets", "Select all"))
        self._classes_select_all_btn.clicked.connect(self._classes_select_all)
        self._classes_clear_btn = QPushButton(tr("GeoIfcAssets", "Clear"))
        self._classes_clear_btn.clicked.connect(self._classes_clear)
        classes_action_layout.addWidget(self._classes_select_all_btn)
        classes_action_layout.addWidget(self._classes_clear_btn)
        classes_action_layout.addStretch()
        _classes_vbox.addWidget(classes_action_bar)

        self._classes_tree = QTreeWidget()
        self._classes_tree.setColumnCount(5)
        self._classes_tree.setHeaderLabels([
            tr("GeoIfcAssets", "Class"),
            tr("GeoIfcAssets", "count"),
            tr("GeoIfcAssets", "length"),
            tr("GeoIfcAssets", "area"),
            tr("GeoIfcAssets", "volume"),
        ])
        try:
            for _col in range(5):
                self._classes_tree.header().setSectionResizeMode(_col, QHeaderView.Interactive)
        except AttributeError:
            for _col in range(5):
                self._classes_tree.header().setSectionResizeMode(
                    _col, QHeaderView.ResizeMode.Interactive
                )
        self._classes_tree.setColumnWidth(0, 150)
        for _col in range(1, 5):
            self._classes_tree.setColumnWidth(_col, 80)
        self._classes_tree.setSortingEnabled(True)
        _classes_vbox.addWidget(self._classes_tree, 1)

        # Splitter vertical: fields (arriba, peso 2) + IFC Classes (abajo, peso 1)
        _tree_splitter = QSplitter()
        try:
            _tree_splitter.setOrientation(Qt.Vertical)
        except AttributeError:
            _tree_splitter.setOrientation(Qt.Orientation.Vertical)
        _tree_splitter.addWidget(self._fields_tree)
        _tree_splitter.addWidget(_classes_widget)
        _tree_splitter.setStretchFactor(0, 2)
        _tree_splitter.setStretchFactor(1, 1)
        extract_layout.addWidget(_tree_splitter, 1)

        # Workflow log + extract status
        self._user_log = QTextEdit()
        self._user_log.setReadOnly(True)
        self._user_log.setMaximumHeight(72)
        self._user_log.setPlaceholderText(tr("GeoIfcAssets", "Workflow messages"))
        extract_layout.addWidget(self._user_log)

        self._extract_status = QLabel("")
        self._extract_status.setWordWrap(True)
        extract_layout.addWidget(self._extract_status)

        # Primary action button — ancho completo, negrita, al pie de la pestaña
        _gis_font = self._load_gis_btn.font()
        _gis_font.setBold(True)
        self._load_gis_btn.setFont(_gis_font)
        extract_layout.addWidget(self._load_gis_btn)

        tabs.addTab(layer_tab, tr("GeoIfcAssets", "GeoIFC"))
        tabs.addTab(extract_tab, tr("GeoIfcAssets", "Extract"))
        layout.addWidget(tabs)

        self.widget.setWidget(content)
        self.refresh_layers()

    def qwidget(self) -> Any:
        return self.widget

    def switch_to_layer_tab(self) -> None:
        self._tabs.setCurrentIndex(0)

    def set_status(self, message: str, can_open_viewer: bool = False) -> None:
        self._status_label.setText(message)
        self._open_button.setEnabled(can_open_viewer)

    def add_user_log(self, message: str) -> None:
        self._user_log.append(message)

    def set_active_storey(self, name: str | None) -> None:
        """Update the footprint toolbar to reflect the currently selected storey."""
        if name:
            self._storey_label.setText(
                tr("GeoIfcAssets", "Storey: {name}").format(name=name)
            )
            self._footprint_btn.setEnabled(True)
        else:
            self._storey_label.setText(tr("GeoIfcAssets", "No storey selected"))
            self._footprint_btn.setEnabled(False)

    def set_ifc_actions_enabled(self, enabled: bool) -> None:
        """Enable or disable the IFC-to-GIS action buttons in the viewer tab."""
        self._new_layer_btn.setEnabled(enabled)
        self._add_to_layer_btn.setEnabled(enabled)

    def set_model_metrics(self, metrics: list[ModelMetric]) -> None:
        """No-op: metrics table removed; values shown in Properties tree."""

    def clear_model_metrics(self) -> None:
        """No-op: metrics table removed."""

    # ── Extract tab public API ────────────────────────────────────────────────

    def set_template(self, template: PropertyTemplate, builtin_names: list[str]) -> None:
        """Populate the template combo and rebuild the fields tree."""
        self._extract_template = template

        self._template_combo.blockSignals(True)
        self._template_combo.clear()
        for name in builtin_names:
            self._template_combo.addItem(name)
        self._template_combo.blockSignals(False)

        self._rebuild_fields_tree(template)
        self._load_gis_btn.setEnabled(False)

    def set_extract_values(self, values: dict[str, Any]) -> None:
        """Update the Value column in the fields tree from extracted data."""
        from qgis.PyQt.QtWidgets import QTreeWidgetItem  # noqa: PLC0415

        root = self._fields_tree.invisibleRootItem()
        for g_idx in range(root.childCount()):
            group_item = root.child(g_idx)
            for f_idx in range(group_item.childCount()):
                field_item = group_item.child(f_idx)
                field_name = field_item.data(0, _FIELD_NAME_ROLE)
                if field_name and field_name in values:
                    val = values[field_name]
                    field_item.setText(2, "" if val is None else str(val))

        self._update_extract_status()
        self._load_gis_btn.setEnabled(True)

    def get_selected_fields(self) -> list[str]:
        """Return field names checked in the Extract tree."""
        from qgis.PyQt.QtCore import Qt  # noqa: PLC0415

        selected: list[str] = []
        root = self._fields_tree.invisibleRootItem()
        for g_idx in range(root.childCount()):
            group_item = root.child(g_idx)
            for f_idx in range(group_item.childCount()):
                field_item = group_item.child(f_idx)
                try:
                    checked = field_item.checkState(0) == Qt.Checked
                except AttributeError:
                    checked = field_item.checkState(0) == Qt.CheckState.Checked
                if checked:
                    field_name = field_item.data(0, _FIELD_NAME_ROLE)
                    if field_name:
                        selected.append(field_name)
        return selected

    def set_extract_status(self, message: str) -> None:
        self._extract_status.setText(message)

    def set_template_combo_names(self, names: list[str]) -> None:
        self._template_combo.blockSignals(True)
        self._template_combo.clear()
        for name in names:
            self._template_combo.addItem(name)
        self._template_combo.blockSignals(False)

    # ── Extract tree internals ────────────────────────────────────────────────

    def _rebuild_fields_tree(self, template: PropertyTemplate) -> None:
        from qgis.PyQt.QtCore import Qt  # noqa: PLC0415
        from qgis.PyQt.QtWidgets import QTreeWidgetItem  # noqa: PLC0415

        self._fields_tree.blockSignals(True)
        self._fields_tree.clear()

        # Group fields preserving JSON order within each group
        groups: dict[str, list] = {}
        for field in template.fields:
            groups.setdefault(field.group, []).append(field)

        # Sort groups by canonical order
        for group_name in sorted(groups.keys(), key=group_order_key):
            fields_in_group = groups[group_name]
            group_display = fields_in_group[0].group_label or group_name
            group_item = QTreeWidgetItem([group_display, "", "", ""])
            try:
                group_item.setFlags(
                    group_item.flags()
                    | Qt.ItemIsUserCheckable
                    | Qt.ItemIsAutoTristate
                )
                group_item.setCheckState(0, Qt.Unchecked)
            except AttributeError:
                group_item.setFlags(
                    group_item.flags()
                    | Qt.ItemFlag.ItemIsUserCheckable
                    | Qt.ItemFlag.ItemIsAutoTristate
                )
                group_item.setCheckState(0, Qt.CheckState.Unchecked)

            for field in fields_in_group:
                child = QTreeWidgetItem([field.alias, field.name, field.ifc_source, ""])
                child.setData(0, _FIELD_NAME_ROLE, field.name)
                child.setToolTip(0, field.description)
                try:
                    child.setFlags(child.flags() | Qt.ItemIsUserCheckable)
                    state = Qt.Checked if field.enabled else Qt.Unchecked
                    child.setCheckState(0, state)
                except AttributeError:
                    child.setFlags(child.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                    state = Qt.CheckState.Checked if field.enabled else Qt.CheckState.Unchecked
                    child.setCheckState(0, state)
                group_item.addChild(child)

            self._fields_tree.addTopLevelItem(group_item)
            group_item.setExpanded(False)

        self._fields_tree.blockSignals(False)
        self._sync_group_check_states()

    def _on_tree_item_changed(self, item: Any, column: int) -> None:
        if column != 0:
            return
        from qgis.PyQt.QtCore import Qt  # noqa: PLC0415

        self._fields_tree.blockSignals(True)
        # If a group item toggled, push state to all children
        if item.parent() is None:
            try:
                state = item.checkState(0)
                child_state = (
                    Qt.Checked if state == Qt.Checked else Qt.Unchecked
                )
            except AttributeError:
                state = item.checkState(0)
                child_state = (
                    Qt.CheckState.Checked
                    if state == Qt.CheckState.Checked
                    else Qt.CheckState.Unchecked
                )
            for i in range(item.childCount()):
                item.child(i).setCheckState(0, child_state)
        else:
            self._sync_group_check_states()
        self._fields_tree.blockSignals(False)

    def _sync_group_check_states(self) -> None:
        from qgis.PyQt.QtCore import Qt  # noqa: PLC0415

        root = self._fields_tree.invisibleRootItem()
        for g_idx in range(root.childCount()):
            group_item = root.child(g_idx)
            n = group_item.childCount()
            if n == 0:
                continue
            try:
                checked_count = sum(
                    1 for i in range(n)
                    if group_item.child(i).checkState(0) == Qt.Checked
                )
                if checked_count == 0:
                    group_item.setCheckState(0, Qt.Unchecked)
                elif checked_count == n:
                    group_item.setCheckState(0, Qt.Checked)
                else:
                    group_item.setCheckState(0, Qt.PartiallyChecked)
            except AttributeError:
                checked_count = sum(
                    1 for i in range(n)
                    if group_item.child(i).checkState(0) == Qt.CheckState.Checked
                )
                if checked_count == 0:
                    group_item.setCheckState(0, Qt.CheckState.Unchecked)
                elif checked_count == n:
                    group_item.setCheckState(0, Qt.CheckState.Checked)
                else:
                    group_item.setCheckState(0, Qt.CheckState.PartiallyChecked)

    def _extract_select_all(self) -> None:
        from qgis.PyQt.QtCore import Qt  # noqa: PLC0415

        self._fields_tree.blockSignals(True)
        root = self._fields_tree.invisibleRootItem()
        for g_idx in range(root.childCount()):
            group_item = root.child(g_idx)
            for f_idx in range(group_item.childCount()):
                try:
                    group_item.child(f_idx).setCheckState(0, Qt.Checked)
                except AttributeError:
                    group_item.child(f_idx).setCheckState(0, Qt.CheckState.Checked)
        self._fields_tree.blockSignals(False)
        self._sync_group_check_states()

    def _extract_clear(self) -> None:
        from qgis.PyQt.QtCore import Qt  # noqa: PLC0415

        self._fields_tree.blockSignals(True)
        root = self._fields_tree.invisibleRootItem()
        for g_idx in range(root.childCount()):
            group_item = root.child(g_idx)
            for f_idx in range(group_item.childCount()):
                try:
                    group_item.child(f_idx).setCheckState(0, Qt.Unchecked)
                except AttributeError:
                    group_item.child(f_idx).setCheckState(0, Qt.CheckState.Unchecked)
        self._fields_tree.blockSignals(False)
        self._sync_group_check_states()

    def _update_extract_status(self) -> None:
        selected = len(self.get_selected_fields())
        if selected == 0:
            self._extract_status.setText(tr("GeoIfcAssets", "No fields selected."))
        else:
            self._extract_status.setText(
                tr("GeoIfcAssets", "{n} field(s) selected.").format(n=selected)
            )

    # ── IFC Classes section public API ────────────────────────────────────────

    def set_ifc_classes(self, classes: list[dict]) -> None:
        """Populate the IFC Classes tree with dynamically discovered classes.

        Each dict: ``{ifc_class, count, available, values, sources}``.
        Available metrics are pre-checked and show their extracted value + source tag.
        Unavailable metrics show "—" with no checkbox.
        """
        from qgis.PyQt.QtCore import Qt  # noqa: PLC0415
        from qgis.PyQt.QtWidgets import QTreeWidgetItem  # noqa: PLC0415

        self._classes_tree.blockSignals(True)
        self._classes_tree.clear()

        for cls_info in sorted(classes, key=lambda x: -x.get("count", 0)):
            ifc_class = cls_info.get("ifc_class", "")
            count = cls_info.get("count", 0)
            available: set = cls_info.get("available", set())
            values: dict = cls_info.get("values", {})
            sources: dict = cls_info.get("sources", {})

            item = QTreeWidgetItem([f"{ifc_class}", "", "", "", ""])
            item.setData(0, _CLASS_ROLE, ifc_class)

            for col_i, metric in enumerate(_METRIC_COLS, start=1):
                is_avail = (metric == "count" and count > 0) or (metric in available)
                if is_avail:
                    val = values.get(metric)
                    source = sources.get(metric, "calc" if metric == "count" else "Qto")
                    if val is None:
                        val_str = "?"
                    elif metric == "count":
                        val_str = str(int(val))
                    else:
                        val_str = f"{val:.1f}"
                    try:
                        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                        item.setCheckState(col_i, Qt.Checked)
                    except AttributeError:
                        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                        item.setCheckState(col_i, Qt.CheckState.Checked)
                    item.setText(col_i, f"{val_str} [{source}]")
                else:
                    item.setText(col_i, "—")

            self._classes_tree.addTopLevelItem(item)

        self._classes_tree.blockSignals(False)

    def get_selected_class_metrics(self) -> list[tuple[str, list[str]]]:
        """Return ``[(ifc_class, [metrics])]`` for classes with ≥1 checked metric."""
        from qgis.PyQt.QtCore import Qt  # noqa: PLC0415

        result = []
        root = self._classes_tree.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            ifc_class = item.data(0, _CLASS_ROLE)
            if not ifc_class:
                continue
            selected: list[str] = []
            for col_i, metric in enumerate(_METRIC_COLS, start=1):
                try:
                    checked = item.checkState(col_i) == Qt.Checked
                except AttributeError:
                    checked = item.checkState(col_i) == Qt.CheckState.Checked
                if checked:
                    selected.append(metric)
            if selected:
                result.append((ifc_class, selected))
        return result

    def _filter_fields_tree(self, state: int) -> None:
        """Hide/show field rows based on whether the Value column is populated."""
        show_only = bool(state)  # 0=unchecked → False, 2=checked → True

        root = self._fields_tree.invisibleRootItem()
        for g_idx in range(root.childCount()):
            group_item = root.child(g_idx)
            any_visible = False
            for f_idx in range(group_item.childCount()):
                field_item = group_item.child(f_idx)
                has_value = bool(field_item.text(2).strip())
                should_show = (not show_only) or has_value
                field_item.setHidden(not should_show)
                if should_show:
                    any_visible = True
            group_item.setHidden(not any_visible)

    def _toggle_tree_expand(self, expanded: bool) -> None:
        """Expand or collapse all group nodes in the fields tree."""
        if expanded:
            self._fields_tree.expandAll()
            self._expand_tree_btn.setText(tr("GeoIfcAssets", "Collapse all"))
        else:
            self._fields_tree.collapseAll()
            self._expand_tree_btn.setText(tr("GeoIfcAssets", "Expand all"))

    def _classes_select_all(self) -> None:
        """Check all available metric columns in the IFC Classes tree."""
        from qgis.PyQt.QtCore import Qt  # noqa: PLC0415

        root = self._classes_tree.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            for col_i in range(1, 5):
                if item.text(col_i) != "—":
                    try:
                        item.setCheckState(col_i, Qt.Checked)
                    except AttributeError:
                        item.setCheckState(col_i, Qt.CheckState.Checked)

    def _classes_clear(self) -> None:
        """Uncheck all metric columns in the IFC Classes tree."""
        from qgis.PyQt.QtCore import Qt  # noqa: PLC0415

        root = self._classes_tree.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            for col_i in range(1, 5):
                if item.text(col_i) != "—":
                    try:
                        item.setCheckState(col_i, Qt.Unchecked)
                    except AttributeError:
                        item.setCheckState(col_i, Qt.CheckState.Unchecked)

    def refresh_layers(self) -> None:
        self._updating_ui = True
        self._layer_combo.clear()
        self._layer_by_row.clear()
        for row, item in enumerate(self._on_refresh_layers()):
            self._layer_combo.addItem(item.name)
            self._layer_by_row[row] = item.layer_id
        self._updating_ui = False
        if not self._layer_by_row:
            self._set_feature_rows([])
            self._on_feature_selected("", -1)
            return
        self._select_layer_row(self._layer_combo.currentIndex())

    def _select_layer_row(self, row: int) -> None:
        if self._updating_ui:
            return
        layer_id = self._layer_by_row.get(row)
        if layer_id is None:
            self._set_feature_rows([])
            return
        self._set_feature_rows(self._on_layer_selected(layer_id))

    def _set_feature_rows(self, features: list[FeatureListItem]) -> None:
        self._updating_ui = True
        self._feature_by_row.clear()
        self._feature_table.setRowCount(len(features))
        for row, feature in enumerate(features):
            self._feature_by_row[row] = feature.feature_id
            self._feature_table.setItem(
                row, 0, self._table_item(str(feature.feature_id))
            )
            self._feature_table.setItem(row, 1, self._table_item(feature.label))
            self._feature_table.setItem(
                row, 2, self._table_item(feature.ifc_source)
            )
        self._updating_ui = False

    def _select_feature_row(self) -> None:
        if self._updating_ui:
            return
        layer_id = self._layer_by_row.get(self._layer_combo.currentIndex())
        selected_rows = self._feature_table.selectionModel().selectedRows()
        if layer_id is None or not selected_rows:
            return
        feature_id = self._feature_by_row.get(selected_rows[0].row())
        if feature_id is None:
            return
        self._on_feature_selected(layer_id, feature_id)

    def _table_item(self, value: str) -> Any:
        from qgis.PyQt.QtCore import Qt
        from qgis.PyQt.QtWidgets import QTableWidgetItem

        item = QTableWidgetItem(value)
        try:
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        except AttributeError:
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        return item


def _table_selection_behavior() -> Any:
    from qgis.PyQt.QtWidgets import QAbstractItemView

    old_value = getattr(QAbstractItemView, "SelectRows", None)
    if old_value is not None:
        return old_value
    return QAbstractItemView.SelectionBehavior.SelectRows


def _table_selection_mode() -> Any:
    from qgis.PyQt.QtWidgets import QAbstractItemView

    old_value = getattr(QAbstractItemView, "SingleSelection", None)
    if old_value is not None:
        return old_value
    return QAbstractItemView.SelectionMode.SingleSelection
