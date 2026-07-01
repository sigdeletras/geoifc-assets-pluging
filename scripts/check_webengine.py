"""
check_webengine.py — Diagnostic script for QtWebEngine availability.

Run from the QGIS Python Console (Plugins → Python Console):
    exec(open(r"<path>\scripts\check_webengine.py").read())

Or from OSGeo4W Shell / QGIS 4 terminal:
    python scripts/check_webengine.py
"""

from __future__ import annotations

import importlib
import os
import subprocess
import sys
from pathlib import Path

try:
    from geoifcassets.adapters.qgis.python_runtime import find_python_executable
except ImportError:
    find_python_executable = None  # type: ignore[assignment,misc]


SEP = "-" * 60


def _header(title: str) -> None:
    print(f"\n{SEP}")
    print(f"  {title}")
    print(SEP)


def _ok(msg: str) -> None:
    print(f"  [OK]   {msg}")


def _fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")


def _warn(msg: str) -> None:
    print(f"  [WARN] {msg}")


def _info(msg: str) -> None:
    print(f"  [INFO] {msg}")


# ------------------------------------------------------------------
# 1. Entorno Python
# ------------------------------------------------------------------
_header("1. Entorno Python")
_info(f"sys.executable : {sys.executable}")
_info(f"sys.version    : {sys.version.split()[0]}")

# Detectar si estamos dentro de QGIS
_inside_qgis = "qgis" in sys.executable.lower() or "qgis" in str(sys.path).lower()
try:
    import qgis.core as _qc  # noqa: F401
    _qgis_version = _qc.Qgis.QGIS_VERSION
    _inside_qgis = True
except ImportError:
    _qgis_version = "N/A (ejecutando fuera de QGIS)"
_info(f"QGIS version   : {_qgis_version}")
_info(f"Dentro de QGIS : {_inside_qgis}")


# ------------------------------------------------------------------
# 2. Import directo en el proceso actual
# ------------------------------------------------------------------
_header("2. Import directo (proceso actual)")

_pyqt6_web_ok = False
_pyqt5_web_ok = False

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView as _Q6  # noqa: F401
    _ok("PyQt6.QtWebEngineWidgets → disponible")
    _pyqt6_web_ok = True
except ImportError as e:
    _fail(f"PyQt6.QtWebEngineWidgets → {e}")

try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView as _Q5  # noqa: F401
    _ok("PyQt5.QtWebEngineWidgets → disponible")
    _pyqt5_web_ok = True
except ImportError as e:
    _fail(f"PyQt5.QtWebEngineWidgets → {e}")

if not _pyqt6_web_ok and not _pyqt5_web_ok:
    _warn("Ningún binding de QtWebEngine disponible en este proceso.")


# ------------------------------------------------------------------
# 3. Import vía subprocess (mismo ejecutable que usará el plugin)
# ------------------------------------------------------------------
_header("3. Import vía subprocess (simula webviewer_app.py)")

_subprocess_python = (
    find_python_executable() if find_python_executable is not None else sys.executable
)
_info(f"Python subprocess : {_subprocess_python}")

_test_script = (
    "import sys\n"
    "results = []\n"
    "try:\n"
    "    from PyQt6.QtWebEngineWidgets import QWebEngineView\n"
    "    results.append('PyQt6:OK')\n"
    "except ImportError as e:\n"
    "    results.append(f'PyQt6:FAIL:{e}')\n"
    "try:\n"
    "    from PyQt5.QtWebEngineWidgets import QWebEngineView\n"
    "    results.append('PyQt5:OK')\n"
    "except ImportError as e:\n"
    "    results.append(f'PyQt5:FAIL:{e}')\n"
    "print('\\n'.join(results))\n"
)

_proc = subprocess.run(
    [find_python_executable(), "-c", _test_script],
    capture_output=True,
    text=True,
    timeout=15,
)

if _proc.returncode == 0:
    for line in _proc.stdout.strip().splitlines():
        if ":OK" in line:
            _ok(f"subprocess → {line}")
        else:
            _fail(f"subprocess → {line}")
else:
    _fail(f"subprocess terminó con RC={_proc.returncode}")
    if _proc.stderr.strip():
        print(f"    STDERR: {_proc.stderr.strip()[:300]}")


# ------------------------------------------------------------------
# 4. Archivos .pyd / .so en site-packages
# ------------------------------------------------------------------
_header("4. Archivos QtWebEngine en site-packages")

_site_packages = [Path(p) for p in sys.path if "site-packages" in p and Path(p).exists()]
_found_files: list[str] = []

for _sp in _site_packages:
    for _pattern in ("**/Qt*WebEngine*.pyd", "**/Qt*WebEngine*.so", "**/QtWebEngine*.pyd"):
        for _f in _sp.glob(_pattern):
            _found_files.append(str(_f))

if _found_files:
    for _f in _found_files:
        _ok(_f)
else:
    _fail("No se encontraron archivos QtWebEngine*.pyd en site-packages")
    _info("Rutas buscadas:")
    for _sp in _site_packages:
        _info(f"  {_sp}")


# ------------------------------------------------------------------
# 5. Variables de entorno relevantes
# ------------------------------------------------------------------
_header("5. Variables de entorno")

_env_vars = [
    "QTWEBENGINE_CHROMIUM_FLAGS",
    "QTWEBENGINE_DISABLE_SANDBOX",
    "OSGEO4W_ROOT",
    "PYTHONPATH",
    "QT_PLUGIN_PATH",
    "PATH",
]

for _var in _env_vars:
    _val = os.environ.get(_var)
    if _var == "PATH":
        # PATH puede ser muy largo; mostrar solo entradas Qt/QGIS
        if _val:
            _qt_paths = [p for p in _val.split(os.pathsep) if any(k in p.lower() for k in ("qt", "qgis", "osgeo"))]
            _info(f"PATH (entradas Qt/QGIS): {_qt_paths[:5]}")
        else:
            _info("PATH: no definido")
    elif _val:
        _ok(f"{_var} = {_val[:120]}")
    else:
        _warn(f"{_var} = NO DEFINIDO")


# ------------------------------------------------------------------
# 6. QtWebEngineProcess.exe (necesario para Chromium)
# ------------------------------------------------------------------
_header("6. QtWebEngineProcess.exe")

_qwep_candidates: list[Path] = []

_osgeo_root = os.environ.get("OSGEO4W_ROOT")
if _osgeo_root:
    _qwep_candidates += list(Path(_osgeo_root).rglob("QtWebEngineProcess.exe"))

# Buscar también relativo al ejecutable Python
_exe_dir = Path(sys.executable).parent
_qwep_candidates += list(_exe_dir.rglob("QtWebEngineProcess.exe"))

if _qwep_candidates:
    for _p in _qwep_candidates:
        _ok(str(_p))
else:
    _warn("QtWebEngineProcess.exe no encontrado — Chromium puede no arrancar")
    if sys.platform != "win32":
        _info("(en Linux/macOS el binario se llama QtWebEngineProcess sin .exe)")


# ------------------------------------------------------------------
# 7. Resumen
# ------------------------------------------------------------------
_header("7. Resumen")

_issues: list[str] = []

if not _pyqt6_web_ok and not _pyqt5_web_ok:
    _issues.append("Ningún binding QtWebEngine disponible en el proceso actual.")

if _proc.returncode != 0 or (":FAIL:" in _proc.stdout):
    _issues.append("El subprocess no puede importar QtWebEngine → el visor no arrancará.")

if not _found_files:
    _issues.append("No se encontraron archivos .pyd de QtWebEngine en site-packages.")

if not os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS"):
    _issues.append("QTWEBENGINE_CHROMIUM_FLAGS no definido (puede ser problema en VM/sin GPU).")

if not _qwep_candidates:
    _issues.append("QtWebEngineProcess.exe no encontrado (Chromium no arrancará).")

if _issues:
    print()
    _warn("Problemas detectados:")
    for _i, _issue in enumerate(_issues, 1):
        print(f"  {_i}. {_issue}")
else:
    print()
    _ok("Todo OK — QtWebEngine disponible y operativo.")

print(f"\n{SEP}\n")
