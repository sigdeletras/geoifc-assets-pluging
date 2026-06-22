"""Embedded IFC viewer dock for QGIS."""

from __future__ import annotations

import http.server
import json
import threading
from pathlib import Path
from typing import Any

from geoifcassets.adapters.qgis.i18n import tr
from geoifcassets.core.models import IfcReference, IfcReferenceKind


class IfcHttpServer:
    """Concurrent HTTP server for webviewer assets and the active IFC file.

    Serves static files from ``webviewer_dir`` and intercepts ``/modelo.ifc``
    to stream the IFC file set via :meth:`set_ifc_path` directly from disk.
    """

    def __init__(self, webviewer_dir: Path) -> None:
        self._webviewer_dir = webviewer_dir
        self._server: http.server.ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._ifc_path: str = ""
        self._lock: threading.Lock = threading.Lock()
        self.port: int = 0

    def start(self) -> None:
        server_self = self
        webviewer_dir = str(self._webviewer_dir)

        class _Handler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                super().__init__(*args, directory=webviewer_dir, **kwargs)

            def do_GET(self) -> None:  # noqa: N802
                if self.path == "/modelo.ifc":
                    with server_self._lock:
                        path = server_self._ifc_path
                    if not path:
                        self.send_error(404, "No IFC loaded")
                        return
                    self._serve_ifc(path)
                else:
                    super().do_GET()

            def _serve_ifc(self, path: str) -> None:
                ifc_file = Path(path)
                if not ifc_file.exists():
                    self.send_error(404, "IFC file not found")
                    return
                size = ifc_file.stat().st_size
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(size))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                with open(ifc_file, "rb") as f:
                    self.wfile.write(f.read())

            def log_message(self, format, *args) -> None:  # noqa: A002
                pass

        self._server = http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0), _Handler
        )
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(
            target=self._server.serve_forever, daemon=True
        )
        self._thread.start()

    def set_ifc_path(self, path: str) -> None:
        with self._lock:
            self._ifc_path = path

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None


class IfcViewerDock:
    """Embedded IFC viewer dock backed by a local HTTP server."""

    def __init__(self) -> None:
        from qgis.PyQt.QtWidgets import QLabel, QVBoxLayout, QWidget

        self._pending_reference: IfcReference | None = None

        webviewer_dir = Path(__file__).resolve().parents[2] / "webviewer"
        self._http_server = IfcHttpServer(webviewer_dir)
        self._http_server.start()

        self.widget = QWidget()
        layout = QVBoxLayout(self.widget)
        layout.setContentsMargins(0, 0, 0, 0)

        self._source_label = QLabel(tr("GeoIfcAssets", "No IFC selected."))
        self._source_label.setWordWrap(True)
        layout.addWidget(self._source_label)

        self._web_view: Any | None = None
        try:
            from qgis.PyQt.QtWebEngineWidgets import QWebEngineView

            self._web_view = QWebEngineView()
            self._load_viewer_page()
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

    def qwidget(self) -> Any:
        return self.widget

    def destroy(self) -> None:
        """Stop the HTTP server. Call before closing the dock widget."""
        self._http_server.stop()

    def open_reference(self, reference: IfcReference) -> None:
        self._pending_reference = reference
        self._source_label.setText(
            tr("GeoIfcAssets", "IFC source: {source}").format(
                source=reference.value
            )
        )
        self._send_reference_to_webviewer(reference)

    def clear_reference(self) -> None:
        self._pending_reference = None
        self._source_label.setText(tr("GeoIfcAssets", "No IFC selected."))
        self._http_server.set_ifc_path("")
        self._load_viewer_page()

    def _load_viewer_page(self) -> None:
        from qgis.PyQt.QtCore import QUrl

        if self._web_view is not None:
            url = QUrl(f"http://127.0.0.1:{self._http_server.port}/index.html")
            self._web_view.setUrl(url)

    def _on_viewer_loaded(self, ok: bool) -> None:
        if ok and self._pending_reference is not None:
            self._send_reference_to_webviewer(self._pending_reference)

    def _send_reference_to_webviewer(self, reference: IfcReference) -> None:
        if self._web_view is None:
            return
        payload: dict[str, str] = {
            "kind": reference.kind.value,
            "source": reference.value,
        }
        if reference.kind is IfcReferenceKind.PATH:
            self._http_server.set_ifc_path(reference.value)
            payload["modelUrl"] = "/modelo.ifc"
        script = (
            f"window.GeoIfcViewer && "
            f"window.GeoIfcViewer.openReference({json.dumps(payload)});"
        )
        self._web_view.page().runJavaScript(script)
