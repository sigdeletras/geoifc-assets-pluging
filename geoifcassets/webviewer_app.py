"""Standalone IFC viewer subprocess.

Runs QWebEngineView in its own QApplication so Chromium starts a fresh
render process that reads QTWEBENGINE_CHROMIUM_FLAGS inherited from the
parent QGIS process (set by _ensure_swiftshader_flag in initGui).

Usage:
    python webviewer_app.py <http_port> [viewer_url]

The subprocess logs status to stdout:
    READY:<win_id>          — window is visible and ready
    RENDERER_CRASH:<status> — WebEngine renderer crashed (page auto-reloads)
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
    try:
        from PyQt6.QtCore import QTimer, QUrl
        from PyQt6.QtWebEngineWidgets import QWebEngineView
        from PyQt6.QtWidgets import QApplication

        def exec_app(app: QApplication) -> int:
            return app.exec()

    except ImportError:
        from PyQt5.QtCore import QTimer, QUrl  # type: ignore[no-redef]
        from PyQt5.QtWebEngineWidgets import QWebEngineView  # type: ignore[no-redef]
        from PyQt5.QtWidgets import QApplication  # type: ignore[no-redef]

        def exec_app(app: QApplication) -> int:  # type: ignore[misc]
            return app.exec_()

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

    # Signal to parent that the window is ready (win_id for future embedding).
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
