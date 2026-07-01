"""Embedded IFC viewer dock for QGIS."""

from __future__ import annotations

import http.server
import json
import logging
import os
import sys
import threading
from pathlib import Path
from typing import Any

from geoifcassets.adapters.qgis.i18n import tr
from geoifcassets.adapters.qgis.python_runtime import find_python_executable
from geoifcassets.core.models import IfcReference

_log = logging.getLogger("geoifcassets")
_QGIS_LOG_TAG = "GeoIFC Assets"


def _qlog(message: str, level: str = "Info") -> None:
    """Log to QGIS Log Messages panel (visible without Python console)."""
    try:
        from qgis.core import Qgis, QgsMessageLog

        qgis_level = {
            "Info": Qgis.Info,
            "Warning": Qgis.Warning,
            "Critical": Qgis.Critical,
        }.get(level, Qgis.Info)
        QgsMessageLog.logMessage(message, _QGIS_LOG_TAG, qgis_level)
    except Exception:  # noqa: BLE001
        pass  # QGIS not available (unit tests)


def _ensure_swiftshader_flag() -> None:
    """Request SwiftShader software WebGL before QWebEngineView is created.

    ``QTWEBENGINE_CHROMIUM_FLAGS`` is read when the Chromium render process
    starts. If QWebEngine is already running (e.g. another QGIS component
    created a view first), this call has no effect and the user must restart
    QGIS for the flag to apply.

    Call this from ``initGui()`` (plugin startup) not from the dock constructor,
    so it runs before QGIS creates any QWebEngineView.
    """
    key = "QTWEBENGINE_CHROMIUM_FLAGS"
    flags_to_add = ["--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]
    existing = os.environ.get(key, "")
    missing = [f for f in flags_to_add if f not in existing]
    if missing:
        os.environ[key] = (existing + " " + " ".join(missing)).strip()
        _log.info("Set %s += %s", key, " ".join(missing))
        _qlog(
            "WebGL flags set (SwiftShader + GPU blocklist override). "
            "Restart QGIS if '3D renderer unavailable' persists.",
            level="Warning",
        )
    else:
        _log.debug("SwiftShader/GPU flags already present in %s", key)


def iter_subprocess_stdout_lines(raw: bytes) -> list[str]:
    """Split subprocess stdout chunks into non-empty lines."""
    text = raw.decode("utf-8", errors="replace")
    return [line for line in text.splitlines() if line.strip()]


def classify_subprocess_stdout_line(line: str) -> tuple[str, str]:
    """Classify one subprocess stdout line.

    Returns ``(kind, payload)`` where *kind* is one of:
    ``binding``, ``binding_fallback``, ``binding_error``, ``ready``,
    ``renderer_crash``, ``other``.
    """
    stripped = line.strip()
    if stripped.startswith("QT_BINDING:"):
        return ("binding", stripped.split(":", 1)[1])
    if stripped.startswith("QT_BINDING_FALLBACK:"):
        return ("binding_fallback", stripped.split(":", 1)[1])
    if stripped.startswith("QT_BINDING_ERROR:"):
        return ("binding_error", stripped.split(":", 1)[1])
    if stripped.startswith("READY:"):
        return ("ready", stripped.split(":", 1)[1])
    if stripped.startswith("RENDERER_CRASH:"):
        return ("renderer_crash", stripped.split(":", 1)[1])
    return ("other", stripped)


def _local_path_from_reference(reference: IfcReference) -> str:
    """Return the local filesystem path for a reference, or '' for remote URLs.

    Both ``ifc_path`` and ``ifc_url`` fields can contain local Windows/POSIX
    paths. We only treat the value as a remote URL when it starts with
    ``http://`` or ``https://``.
    """
    value = reference.value
    if value.startswith("http://") or value.startswith("https://"):
        return ""
    return value


class IfcHttpServer:
    """Concurrent HTTP server for webviewer assets and the active IFC file.

    Serves static files from ``webviewer_dir`` and additionally:
    - ``/modelo.ifc``     — streams the active IFC file set via :meth:`set_ifc_path`
    - ``/current.json``   — returns ``{"version": N, "ifc_url": "/modelo.ifc" | null}``
                            polled by the viewer JS to detect IFC changes without
                            restarting the subprocess.
    - ``POST /transfer``  — receives a BIM→GIS transfer request from the viewer JS;
                            stored in a queue and consumed by :meth:`pop_pending_transfer`.
    """

    def __init__(self, webviewer_dir: Path) -> None:
        self._webviewer_dir = webviewer_dir
        self._server: http.server.ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._ifc_path: str = ""
        self._version: int = 0
        self._pending_transfers: list[dict] = []
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
                        _log.warning("HTTP request for /modelo.ifc but no IFC path is set")
                        self.send_error(404, "No IFC loaded")
                        return
                    _log.debug("HTTP serving IFC: %s", path)
                    self._serve_ifc(path)
                elif self.path == "/current.json":
                    self._serve_current()
                else:
                    super().do_GET()

            def do_POST(self) -> None:  # noqa: N802
                if self.path == "/transfer":
                    self._receive_transfer()
                else:
                    self.send_error(404)

            def _serve_current(self) -> None:
                with server_self._lock:
                    version = server_self._version
                    ifc_path = server_self._ifc_path
                payload = json.dumps({
                    "version": version,
                    "ifc_url": "/modelo.ifc" if ifc_path else None,
                    "ifc_name": Path(ifc_path).name if ifc_path else None,
                }).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(payload)

            def _receive_transfer(self) -> None:
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                try:
                    data = json.loads(body)
                except json.JSONDecodeError as exc:
                    _log.warning("Invalid JSON in /transfer body: %s", exc)
                    self.send_error(400, "Bad JSON")
                    return
                _log.info("BIM→GIS transfer queued: %s", data)
                with server_self._lock:
                    server_self._pending_transfers.append(data)
                payload = b'{"ok":true}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(payload)

            def _serve_ifc(self, path: str) -> None:
                ifc_file = Path(path)
                if not ifc_file.exists():
                    _log.error("HTTP IFC file not found on disk: %s", path)
                    self.send_error(404, "IFC file not found")
                    return
                size = ifc_file.stat().st_size
                _log.debug("HTTP streaming IFC (%d bytes): %s", size, path)
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(size))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                with open(ifc_file, "rb") as f:
                    self.wfile.write(f.read())

            def log_message(self, format, *args) -> None:  # noqa: A002
                _log.debug("HTTP %s", format % args)

        self._server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        _log.info("IFC HTTP server started on port %d, serving: %s", self.port, webviewer_dir)
        _qlog(f"HTTP server started on port {self.port}")

    def set_ifc_path(self, path: str) -> None:
        with self._lock:
            self._ifc_path = path
            self._version += 1
        _log.info("IFC HTTP server path set (version %d): %s", self._version, path)

    def pop_pending_transfer(self) -> dict | None:
        """Return and remove the oldest queued BIM→GIS transfer, or None."""
        with self._lock:
            return self._pending_transfers.pop(0) if self._pending_transfers else None

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
            _log.info("IFC HTTP server stopped")


class IfcViewerDock:
    """IFC viewer dock backed by a subprocess QWebEngineView + local HTTP server.

    The viewer runs in a separate process so Chromium starts fresh and reads
    ``QTWEBENGINE_CHROMIUM_FLAGS`` (SwiftShader) without interference from
    any QWebEngineView already alive in the QGIS main process.

    The subprocess communicates with the HTTP server via polling ``/current.json``
    every 1.5 s, so selecting a new feature updates the viewer without restarting
    the subprocess.

    The JS viewer POSTs BIM→GIS transfer requests to ``/transfer``. The dock polls
    for them every 250 ms and calls *on_transfer* (if provided) on the Qt main thread.
    """

    def __init__(
        self,
        on_transfer: Any | None = None,  # Callable[[dict], None] | None
    ) -> None:
        from qgis.PyQt.QtCore import QTimer
        from qgis.PyQt.QtWidgets import QLabel, QVBoxLayout, QWidget

        self._pending_reference: IfcReference | None = None
        self._proc: Any | None = None  # QProcess
        self._on_transfer = on_transfer

        webviewer_dir = Path(__file__).resolve().parents[2] / "webviewer"
        _log.info("Webviewer directory: %s (exists=%s)", webviewer_dir, webviewer_dir.exists())

        self._http_server = IfcHttpServer(webviewer_dir)
        self._http_server.start()

        self.widget = QWidget()
        self._transfer_timer = QTimer(self.widget)
        self._transfer_timer.timeout.connect(self._poll_transfers)
        self._transfer_timer.start(250)
        layout = QVBoxLayout(self.widget)
        layout.setContentsMargins(8, 8, 8, 8)

        self._source_label = QLabel(tr("GeoIfcAssets", "No IFC selected."))
        self._source_label.setWordWrap(True)
        layout.addWidget(self._source_label)

        self._status_label = QLabel(tr("GeoIfcAssets", "Select a feature to start the IFC viewer."))
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        layout.addStretch(1)

    def qwidget(self) -> Any:
        return self.widget

    def destroy(self) -> None:
        """Stop the subprocess and HTTP server. Call before closing the dock."""
        self._stop_subprocess()
        self._http_server.stop()

    def open_reference(self, reference: IfcReference) -> None:
        self._pending_reference = reference
        self._source_label.setText(
            tr("GeoIfcAssets", "IFC source: {source}").format(source=reference.value)
        )

        # Both ifc_path and ifc_url can contain local filesystem paths.
        # Only treat the value as a remote URL when it starts with http(s)://.
        local_path = _local_path_from_reference(reference)
        if local_path:
            self._http_server.set_ifc_path(local_path)
        else:
            _log.warning(
                "Remote IFC URL not yet supported in subprocess viewer: %s", reference.value
            )
            self._http_server.set_ifc_path("")

        _log.info("open_reference: kind=%s source=%s", reference.kind.value, reference.value)

        # Restart subprocess if it exited unexpectedly (e.g., renderer crash).
        if self._proc is None:
            _log.info("open_reference: subprocess not running — restarting")
            _qlog("IFC viewer subprocess was stopped — restarting now")
            self._launch_subprocess()

    def clear_reference(self) -> None:
        self._pending_reference = None
        self._source_label.setText(tr("GeoIfcAssets", "No IFC selected."))
        self._http_server.set_ifc_path("")

    # ------------------------------------------------------------------
    # Subprocess management
    # ------------------------------------------------------------------

    def _launch_subprocess(self) -> None:
        from qgis.PyQt.QtCore import QProcess, QProcessEnvironment

        self._stop_subprocess()

        script_path = str(Path(__file__).resolve().parents[2] / "webviewer_app.py")
        viewer_url = f"http://127.0.0.1:{self._http_server.port}/index.html"

        # Build environment: system env overridden by os.environ so that
        # QTWEBENGINE_CHROMIUM_FLAGS set by _ensure_swiftshader_flag() is inherited.
        qenv = QProcessEnvironment.systemEnvironment()
        for key, value in os.environ.items():
            qenv.insert(key, value)

        # Pass QGIS's sys.path to the subprocess so PyQt5/PyQt6 and their
        # WebEngine extensions are importable even when the standalone Python
        # binary does not carry those paths by default.
        import sys as _sys  # noqa: PLC0415
        pythonpath_parts = [p for p in _sys.path if p]
        existing = qenv.value("PYTHONPATH")
        if existing:
            pythonpath_parts.append(existing)
        qenv.insert("PYTHONPATH", os.pathsep.join(pythonpath_parts))
        _log.info("subprocess PYTHONPATH set (%d entries)", len(pythonpath_parts))

        proc = QProcess()
        proc.setProcessEnvironment(qenv)
        proc.readyReadStandardOutput.connect(self._on_proc_stdout)
        proc.readyReadStandardError.connect(self._on_proc_stderr)
        proc.finished.connect(self._on_proc_finished)

        python_exe = find_python_executable()
        proc.start(python_exe, [script_path, str(self._http_server.port), viewer_url])
        self._proc = proc

        _log.info(
            "Subprocess viewer launched: %s %s port=%d",
            python_exe,
            script_path,
            self._http_server.port,
        )
        _qlog(f"IFC viewer subprocess started (port {self._http_server.port})")
        self._status_label.setText(
            tr("GeoIfcAssets", "IFC viewer subprocess starting...")
        )

    def _stop_subprocess(self) -> None:
        if self._proc is None:
            return
        self._proc.kill()
        self._proc.waitForFinished(2000)
        self._proc = None
        _log.info("Subprocess viewer stopped")

    def _on_proc_stdout(self) -> None:
        if self._proc is None:
            return
        raw = bytes(self._proc.readAllStandardOutput())
        for line in iter_subprocess_stdout_lines(raw):
            self._handle_subprocess_stdout_line(line)

    def _handle_subprocess_stdout_line(self, line: str) -> None:
        _log.info("Subprocess stdout: %s", line)
        _qlog(f"Viewer subprocess: {line}")
        kind, payload = classify_subprocess_stdout_line(line)
        if kind == "binding":
            _log.info("Subprocess loaded Qt binding: %s", payload)
            _qlog(f"IFC viewer using {payload} WebEngine", level="Info")
        elif kind == "binding_fallback":
            _log.warning("Subprocess Qt binding fallback: %s", line)
            _qlog(line, level="Warning")
        elif kind == "binding_error":
            _log.error("Subprocess Qt binding error: %s", line)
            _qlog(line, level="Critical")
            self._status_label.setText(
                tr("GeoIfcAssets", "IFC viewer error: QtWebEngine not available. "
                   "Install python3-pyqtwebengine via OSGeo4W Setup.")
            )
        elif kind == "ready":
            _log.info("Subprocess viewer ready (win_id=%s)", payload)
            self._status_label.setText(
                tr("GeoIfcAssets", "IFC viewer window open — select a feature to load IFC.")
            )
        elif kind == "renderer_crash":
            _log.warning("Subprocess renderer crash: %s", payload)
            _qlog(f"Viewer renderer crash: {payload}", level="Warning")

    def _on_proc_stderr(self) -> None:
        if self._proc is None:
            return
        raw = bytes(self._proc.readAllStandardError())
        line = raw.decode("utf-8", errors="replace").strip()
        if line:
            _log.warning("Subprocess stderr: %s", line)
            _qlog(f"Viewer subprocess error: {line}", level="Warning")

    def _on_proc_finished(self, exit_code: int, exit_status: Any) -> None:
        _log.info("Subprocess viewer exited with code %d status %s", exit_code, exit_status)
        _qlog(f"IFC viewer subprocess exited (code {exit_code})")
        self._proc = None
        self._status_label.setText(
            tr("GeoIfcAssets", "IFC viewer subprocess stopped (code {code}).").format(
                code=exit_code
            )
        )

    # ------------------------------------------------------------------
    # BIM→GIS transfer polling
    # ------------------------------------------------------------------

    def _poll_transfers(self) -> None:
        """Called every 250 ms by QTimer; forwards queued transfers to on_transfer."""
        transfer = self._http_server.pop_pending_transfer()
        if transfer is not None and self._on_transfer is not None:
            self._on_transfer(transfer)
