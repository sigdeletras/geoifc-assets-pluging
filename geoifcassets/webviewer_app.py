"""Standalone IFC viewer subprocess.

Runs QWebEngineView in its own QApplication so Chromium starts a fresh
render process that reads QTWEBENGINE_CHROMIUM_FLAGS inherited from the
parent QGIS process (set by _ensure_swiftshader_flag in initGui).

Usage:
    python webviewer_app.py <http_port> [viewer_url]

The subprocess logs status to stdout:
    READY:<win_id>          — window is visible and ready
    RENDERER_CRASH:<status> — WebEngine renderer crashed (page auto-reloads)
    QT_BINDING:PyQt6        — subprocess loaded PyQt6 (QGIS 4 / Qt6)
    QT_BINDING:PyQt5        — subprocess loaded PyQt5 (QGIS 3 / Qt5)
    QT_BINDING_ERROR:<msg>  — both bindings failed; subprocess will exit
"""

from __future__ import annotations

import sys


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: webviewer_app.py <http_port> [viewer_url]", file=sys.stderr, flush=True)
        return 1

    port = int(sys.argv[1])
    url = sys.argv[2] if len(sys.argv) > 2 else f"http://127.0.0.1:{port}/index.html"

    # Import Qt directly — not via qgis.PyQt which requires a running QGIS context.
    # Try Qt6 first (QGIS 4), fall back to Qt5 (QGIS 3).
    _pyqt6_err: str = ""
    try:
        from PyQt6.QtCore import QTimer, QUrl
        from PyQt6.QtWebEngineWidgets import QWebEngineView
        from PyQt6.QtWidgets import QApplication

        def exec_app(app: QApplication) -> int:
            return app.exec()

        print("QT_BINDING:PyQt6", flush=True)

    except ImportError as _exc:
        _pyqt6_err = str(_exc)
        print(f"QT_BINDING_FALLBACK:PyQt6 unavailable ({_pyqt6_err})", flush=True)
        try:
            from PyQt5.QtCore import QTimer, QUrl  # type: ignore[no-redef]
            from PyQt5.QtWebEngineWidgets import QWebEngineView  # type: ignore[no-redef]
            from PyQt5.QtWidgets import QApplication  # type: ignore[no-redef]

            def exec_app(app: QApplication) -> int:  # type: ignore[misc]
                return app.exec_()

            print("QT_BINDING:PyQt5", flush=True)

        except ImportError as _exc5:
            print(
                f"QT_BINDING_ERROR:PyQt5 unavailable ({_exc5})",
                flush=True,
            )
            print(
                "QT_BINDING_ERROR: no Qt WebEngine binding found — install "
                "python3-pyqtwebengine via OSGeo4W Setup (QGIS 3) or "
                "python3-pyqt6-webengine (QGIS 4).",
                file=sys.stderr,
                flush=True,
            )
            return 1

    app = QApplication(sys.argv[:1])

    # Do NOT quit automatically when the last window closes: this prevents
    # the app from exiting when the WebEngine renderer process crashes (which
    # can temporarily close the view). User-initiated close is handled via the
    # closeEvent override below, which explicitly calls app.quit().
    app.setQuitOnLastWindowClosed(False)

    # Subclass defined inside main() so closeEvent can capture `app` via closure.
    class _ViewerWindow(QWebEngineView):
        def closeEvent(self, event: object) -> None:  # noqa: N802
            event.accept()  # type: ignore[attr-defined]
            app.quit()

    view = _ViewerWindow()
    view.setWindowTitle("GeoIFC Assets — IFC Viewer")
    view.resize(1280, 800)
    view.load(QUrl(url))
    view.show()

    # Enable file downloads (JSON/CSV export from the viewer).
    try:
        from PyQt6.QtWidgets import QFileDialog as _QFD
    except ImportError:
        from PyQt5.QtWidgets import QFileDialog as _QFD  # type: ignore[no-redef]

    def _on_download_requested(download: object) -> None:
        import os

        try:
            suggested = download.suggestedFileName()  # type: ignore[attr-defined]
        except AttributeError:
            suggested = "export"

        path, _ = _QFD.getSaveFileName(view, "Save export", suggested)
        if not path:
            download.cancel()  # type: ignore[attr-defined]
            return

        try:
            # PyQt6 API
            download.setDownloadDirectory(os.path.dirname(os.path.abspath(path)))  # type: ignore[attr-defined]
            download.setDownloadFileName(os.path.basename(path))  # type: ignore[attr-defined]
        except AttributeError:
            # PyQt5 API
            download.setPath(path)  # type: ignore[attr-defined]

        download.accept()  # type: ignore[attr-defined]

    try:
        view.page().profile().downloadRequested.connect(_on_download_requested)
    except Exception:
        pass

    # Signal to parent that the window is ready (readiness check only).
    win_id = int(view.winId())
    print(f"READY:{win_id}", flush=True)

    # Log and auto-recover from renderer process crashes.
    def _on_render_process_terminated(status: object, exit_code: int) -> None:
        print(f"RENDERER_CRASH:{status}", flush=True)
        # Reload the page to restart the Chromium renderer automatically.
        view.load(QUrl(url))

    try:
        view.page().renderProcessTerminated.connect(_on_render_process_terminated)
    except AttributeError:
        pass  # signal not available in all Qt builds

    # Poll stdin for commands from the parent process (QTimer avoids blocking).
    def _check_stdin() -> None:
        import select

        ready, _, _ = select.select([sys.stdin], [], [], 0)
        if not ready:
            return
        line = sys.stdin.readline().strip()
        if line == "reload":
            view.load(QUrl(url))
            print("RELOADED", flush=True)
        elif line == "quit":
            app.quit()

    # stdin polling is only available on POSIX; skip silently on Windows.
    try:
        import select as _sel

        _sel.select([sys.stdin], [], [], 0)  # probe — raises on Windows
        stdin_timer = QTimer()
        stdin_timer.timeout.connect(_check_stdin)
        stdin_timer.start(300)
    except (OSError, ValueError):
        pass  # Windows: stdin select not supported; rely on process termination

    return exec_app(app)


if __name__ == "__main__":
    sys.exit(main())
