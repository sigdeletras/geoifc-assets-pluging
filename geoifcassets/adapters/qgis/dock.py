"""Initial dock widget for GeoIFC Assets."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from geoifcassets.adapters.qgis.i18n import tr


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
    ) -> None:
        from qgis.PyQt.QtWidgets import (
            QComboBox,
            QDockWidget,
            QHBoxLayout,
            QLabel,
            QPushButton,
            QTabWidget,
            QTableWidget,
            QTextEdit,
            QVBoxLayout,
            QWidget,
        )

        self._on_refresh_layers = on_refresh_layers
        self._on_layer_selected = on_layer_selected
        self._on_feature_selected = on_feature_selected
        self._layer_by_row: dict[int, str] = {}
        self._feature_by_row: dict[int, int] = {}
        self._updating_ui = False

        self.widget = QDockWidget(tr("GeoIfcAssets", "GeoIFC Assets"))
        self.widget.setObjectName("GeoIfcAssetsDock")

        content = QWidget()
        layout = QVBoxLayout(content)

        self._tabs = QTabWidget()
        tabs = self._tabs
        layer_tab = QWidget()
        layer_layout = QVBoxLayout(layer_tab)
        properties_tab = QWidget()
        properties_layout = QVBoxLayout(properties_tab)
        viewer_tab = QWidget()
        viewer_layout = QVBoxLayout(viewer_tab)
        viewer_layout.setContentsMargins(0, 0, 0, 0)

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
        properties_layout.addWidget(self._status_label)

        self._user_log = QTextEdit()
        self._user_log.setReadOnly(True)
        self._user_log.setPlaceholderText(tr("GeoIfcAssets", "Workflow messages"))
        properties_layout.addWidget(self._user_log)

        self._open_button = QPushButton(tr("GeoIfcAssets", "Open IFC viewer"))
        self._open_button.setEnabled(False)
        self._open_button.clicked.connect(on_open_viewer)
        layer_layout.addWidget(self._open_button)

        if viewer_widget is not None:
            viewer_layout.addWidget(viewer_widget)
        else:
            viewer_layout.addStretch(1)

        tabs.addTab(layer_tab, tr("GeoIfcAssets", "Layer/Features"))
        tabs.addTab(properties_tab, tr("GeoIfcAssets", "Properties"))
        tabs.addTab(viewer_tab, tr("GeoIfcAssets", "IFC Viewer"))
        layout.addWidget(tabs)

        self.widget.setWidget(content)
        self.refresh_layers()

    def qwidget(self) -> Any:
        return self.widget

    def switch_to_viewer_tab(self) -> None:
        self._tabs.setCurrentIndex(2)

    def set_status(self, message: str, can_open_viewer: bool = False) -> None:
        self._status_label.setText(message)
        self._open_button.setEnabled(can_open_viewer)

    def add_user_log(self, message: str) -> None:
        self._user_log.append(message)

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
        if features:
            self._feature_table.selectRow(0)
        self._updating_ui = False
        self._select_feature_row()

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
