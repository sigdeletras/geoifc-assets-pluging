import logging
import os
import re
import subprocess
import sys

from qgis.PyQt import QtWidgets
from qgis.core import QgsSettings

_log = logging.getLogger("geoifcassets")

# Suppress console window on Windows when spawning subprocesses.
_SUBPROCESS_FLAGS: dict = (
    {"creationflags": 0x08000000} if sys.platform == "win32" else {}
)

path_requirements = os.path.dirname(__file__)
requirements_file = os.path.join(path_requirements, 'requirements.txt')
plugin_root = os.path.abspath(os.path.join(path_requirements, '..', '..'))
metadata_file = os.path.join(plugin_root, 'metadata.txt')
SETTINGS_KEY_REQUIREMENTS_VERSION = "geoifcassets/requirements_installed_version"


def _get_python_executable() -> str:
    """Return the Python interpreter path.

    On Windows, sys.executable is qgis.exe (not python.exe). Launching a
    subprocess with qgis.exe opens a new QGIS window instead of running pip.
    This function searches several candidate locations to find python.exe:
      - exe's directory (qgis.exe is in bin/)
      - parent of exe's directory (QGIS root, where apps/ lives)
      - sys.exec_prefix (may point directly at the Python root)
    """
    exe = sys.executable
    if "python" in os.path.basename(exe).lower():
        return exe

    exe_dir = os.path.dirname(exe)
    search_roots = [exe_dir, os.path.dirname(exe_dir), sys.exec_prefix]

    for root in search_roots:
        # Direct python.exe at root level (matches exec_prefix pointing at Python dir)
        candidate = os.path.join(root, "python.exe")
        if os.path.isfile(candidate):
            _log.info("_get_python_executable: resolved %s → %s", exe, candidate)
            return candidate
        # QGIS layout: apps/Python*/python.exe
        apps_dir = os.path.join(root, "apps")
        if os.path.isdir(apps_dir):
            for entry in sorted(os.listdir(apps_dir), reverse=True):
                if entry.lower().startswith("python"):
                    candidate = os.path.join(apps_dir, entry, "python.exe")
                    if os.path.isfile(candidate):
                        _log.info("_get_python_executable: resolved %s → %s", exe, candidate)
                        return candidate

    _log.warning("_get_python_executable: could not resolve python.exe, using %s", exe)
    return exe


def _read_plugin_version() -> str:
    """Lee la versión del complemento desde metadata.txt."""
    try:
        with open(metadata_file, encoding="utf-8") as file:
            match = re.search(r"^version=(.+)$", file.read(), re.MULTILINE)
            if match:
                return match.group(1).strip()
    except OSError:
        pass
    return "0.0.0"


def _requirements_already_installed() -> bool:
    """Comprueba si los requisitos ya se instalaron para la versión actual del plugin."""
    settings = QgsSettings()
    stored_version = settings.value(SETTINGS_KEY_REQUIREMENTS_VERSION, "", type=str)
    return stored_version == _read_plugin_version()


def _mark_requirements_installed() -> None:
    """Registra que los requisitos de la versión actual ya están instalados."""
    QgsSettings().setValue(SETTINGS_KEY_REQUIREMENTS_VERSION, _read_plugin_version())


def _extract_package_name(requirement: str) -> str:
    """Extrae el nombre del paquete ignorando restricciones de versión (==, >=, etc.)."""
    return re.split(r'[<>=!~\[]', requirement.strip())[0].strip()


def _is_package_installed(package_name: str) -> bool:
    """Comprueba si un paquete está instalado en el intérprete de QGIS."""
    from importlib.metadata import PackageNotFoundError, distribution

    try:
        distribution(package_name)
        return True
    except PackageNotFoundError:
        return False


def _missing_packages() -> list[str]:
    """Devuelve los nombres de paquetes de requirements.txt que no están instalados."""
    try:
        with open(requirements_file, 'r', encoding='utf-8') as file:
            lines = file.readlines()
    except FileNotFoundError:
        return []
    missing = []
    for line in lines:
        package = line.strip()
        if not package or package.startswith('#'):
            continue
        name = _extract_package_name(package)
        if name and not _is_package_installed(name):
            missing.append(package)
    return missing


def check_and_install_requirements():
    python_exe = _get_python_executable()
    _log.info(
        "requirements check — sys.executable=%s  python_exe=%s  sys.version=%s",
        sys.executable,
        python_exe,
        sys.version.split()[0],
    )

    # Always verify actual packages first — the version flag can be stale if a
    # previous install attempt failed silently (e.g. wrong subprocess executable).
    missing = _missing_packages()
    _log.info("missing packages: %s", missing if missing else "none")
    if not missing:
        _mark_requirements_installed()
        _log.debug("all requirements satisfied")
        return True

    # Packages are genuinely missing — ignore the version flag and install.
    _log.info("requirements version flag ignored: packages are missing")

    packages_list = "\n".join(f"  • {p}" for p in missing)
    reply = QtWidgets.QMessageBox.question(
        None,
        "GeoIFC Assets — Dependencias requeridas",
        (
            "GeoIFC Assets necesita instalar las siguientes librerías Python:\n\n"
            f"{packages_list}\n\n"
            "⚠️ La instalación puede tardar varios minutos dependiendo de la conexión a Internet.\n"
            "QGIS puede parecer bloqueado durante el proceso — espere hasta que aparezca\n"
            "el aviso de finalización.\n\n"
            "¿Desea instalar ahora?"
        ),
        QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        QtWidgets.QMessageBox.Yes,
    )
    if reply == QtWidgets.QMessageBox.No:
        return False

    try:
        import pip  # noqa: F401
    except ImportError:
        reply = QtWidgets.QMessageBox.question(
            None,
            "Instalación de PIP",
            "Pip no está instalado. ¿Desea instalar pip?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )

        if reply == QtWidgets.QMessageBox.No:
            return False

        try:
            pip_file = os.path.join(path_requirements, 'get-pip.py')
            subprocess.run([python_exe, pip_file], check=True, **_SUBPROCESS_FLAGS)
        except subprocess.CalledProcessError as error:
            QtWidgets.QMessageBox.warning(
                None,
                "❌ Error al instalar PIP",
                f"❌ Error al intentar instalar pip: {error}"
            )
            return False

    for package in missing:
        _log.info("installing package: %s (using %s)", package, python_exe)
        try:
            result = subprocess.run(
                [python_exe, '-m', 'pip', 'install', '--user', package],
                check=True,
                capture_output=True,
                text=True,
                **_SUBPROCESS_FLAGS,
            )
            _log.info("pip install %s succeeded: %s", package, result.stdout.strip()[:200])
        except subprocess.CalledProcessError as error:
            _log.error(
                "pip install %s failed (RC=%s): stdout=%s stderr=%s",
                package,
                error.returncode,
                getattr(error, "stdout", ""),
                getattr(error, "stderr", ""),
            )
            QtWidgets.QMessageBox.warning(
                None,
                "❌ Error de instalación",
                f"❌ Error al instalar {package}: {error}"
            )
            return False

    _mark_requirements_installed()

    # Make freshly installed --user packages importable in this session
    # without requiring a QGIS restart.
    import site  # noqa: PLC0415
    user_site = site.getusersitepackages() if hasattr(site, "getusersitepackages") else None
    if isinstance(user_site, str) and user_site not in sys.path:
        sys.path.insert(0, user_site)
        _log.info("added user site-packages to sys.path: %s", user_site)

    QtWidgets.QMessageBox.information(
        None,
        "GeoIFC Assets — Instalación completada",
        "Las dependencias se han instalado correctamente.\n\n"
        "Si el plugin no responde, reinicie QGIS para activarlas.",
    )

    return True
