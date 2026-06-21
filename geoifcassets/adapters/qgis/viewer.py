"""Embedded IFC viewer dock for QGIS."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from geoifcassets.adapters.qgis.i18n import tr
from geoifcassets.core.models import IfcReference


class IfcViewerDock:
    """Initial embedded viewer surface.

    Phase 2 wires the selected GIS feature to a viewer dock. Full IFC rendering and
    property inspection will be added on top of this boundary.
    """

    def __init__(self) -> None:
        from qgis.PyQt.QtCore import QUrl
        from qgis.PyQt.QtWidgets import QDockWidget, QLabel, QVBoxLayout, QWidget

        self.widget = QDockWidget(tr("GeoIfcAssets", "GeoIFC Assets IFC Viewer"))
        self.widget.setObjectName("GeoIfcAssetsViewerDock")
        self._pending_reference: IfcReference | None = None

        content = QWidget()
        layout = QVBoxLayout(content)
        self._source_label = QLabel(tr("GeoIfcAssets", "No IFC selected."))
        self._source_label.setWordWrap(True)
        layout.addWidget(self._source_label)

        self._web_view: Any | None = None
        try:
            from qgis.PyQt.QtWebEngineWidgets import QWebEngineView

            self._web_view = QWebEngineView()
            viewer_html = Path(__file__).resolve().parents[2] / "webviewer" / "index.html"
            self._web_view.setUrl(QUrl.fromLocalFile(str(viewer_html)))
            self._web_view.loadFinished.connect(self._on_viewer_loaded)
            layout.addWidget(self._web_view)
        except ImportError:
            fallback = QLabel(
                tr(
                    "GeoIfcAssets",
                    "Qt WebEngine is not available in this QGIS environment.",
                )
            )
            fallback.setWordWrap(True)
            layout.addWidget(fallback)

        self.widget.setWidget(content)

    def qwidget(self) -> Any:
        return self.widget

    def open_reference(self, reference: IfcReference) -> None:
        self._pending_reference = reference
        self._source_label.setText(
            tr("GeoIfcAssets", "IFC source: {source}").format(source=reference.value)
        )
        self._send_reference_to_webviewer(reference)

    def _on_viewer_loaded(self, ok: bool) -> None:
        if ok and self._pending_reference is not None:
            self._send_reference_to_webviewer(self._pending_reference)

    def _send_reference_to_webviewer(self, reference: IfcReference) -> None:
        if self._web_view is None:
            return
        self._web_view.page().runJavaScript(_viewer_open_reference_script(reference))


def _viewer_open_reference_script(reference: IfcReference) -> str:
    payload = {
        "kind": reference.kind.value,
        "source": reference.value,
    }
    data_base64 = _read_local_ifc_as_base64(reference.value)
    if data_base64 is not None:
        payload["dataBase64"] = data_base64
    return f"window.GeoIfcViewer && window.GeoIfcViewer.openReference({json.dumps(payload)});"


def _read_local_ifc_as_base64(source: str) -> str | None:
    path = Path(source)
    if not path.exists() or not path.is_file():
        return None
    try:
        return base64.b64encode(path.read_bytes()).decode("ascii")
    except OSError:
        return None
