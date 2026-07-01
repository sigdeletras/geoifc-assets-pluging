"""QGIS Python interpreter discovery for subprocesses and pip."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_log = logging.getLogger("geoifcassets")


def find_python_executable() -> str:
    """Return the Python interpreter bundled with the active QGIS install.

    In QGIS, ``sys.executable`` points at the QGIS binary (``qgis-bin.exe`` /
    ``qgis.exe``), not at ``python.exe``. Passing it to ``QProcess`` or pip
    subprocesses fails or opens another QGIS window.

    Search order:
      1. ``sys.executable`` when it is already a Python binary
      2. ``python.exe`` / ``apps/Python*`` under QGIS install roots
      3. Fixed candidates next to the QGIS binary and under ``sys.prefix``
      4. ``python3`` / ``python`` on ``PATH`` (last resort)
    """
    exe = Path(sys.executable)
    if "python" in exe.name.lower():
        return str(exe)

    from shutil import which

    _log.info(
        "find_python_executable: sys.executable=%s sys.prefix=%s sys.version=%s",
        sys.executable,
        sys.prefix,
        sys.version.split()[0],
    )

    qgis_bin = exe.parent
    qgis_root = qgis_bin.parent
    search_roots = [qgis_root, qgis_bin, Path(sys.exec_prefix)]

    for root in search_roots:
        direct = root / "python.exe"
        if direct.is_file():
            _log.info("Python interpreter resolved: %s", direct)
            return str(direct)

        apps_dir = root / "apps"
        if not apps_dir.is_dir():
            continue

        for entry in sorted(apps_dir.iterdir(), reverse=True):
            if not entry.is_dir() or not entry.name.lower().startswith("python"):
                continue

            for relative in ("python.exe", "bin/python3", "bin/python"):
                candidate = entry / relative
                if candidate.is_file():
                    _log.info("Python interpreter resolved via apps/: %s", candidate)
                    return str(candidate)

    candidates = [
        qgis_bin / "python3.exe",
        qgis_bin / "python.exe",
        Path(sys.prefix) / "python.exe",
        Path(sys.prefix) / "bin" / "python3",
        Path(sys.prefix) / "bin" / "python",
    ]
    for path in candidates:
        if path.is_file():
            _log.info("Python interpreter resolved: %s", path)
            return str(path)

    fallback = which("python3") or which("python") or str(exe)
    _log.warning(
        "Python interpreter not found via QGIS layout (sys.executable=%s); fallback: %s",
        sys.executable,
        fallback,
    )
    return fallback
