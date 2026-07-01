from __future__ import annotations

import sys
from pathlib import Path

from geoifcassets.adapters.qgis.python_runtime import find_python_executable


def test_find_python_executable_when_sys_executable_is_python() -> None:
    assert find_python_executable() == sys.executable


def test_find_python_executable_resolves_apps_python_layout(
    tmp_path: Path, monkeypatch: object
) -> None:
    qgis_bin = tmp_path / "bin"
    qgis_bin.mkdir()
    python_home = tmp_path / "apps" / "Python312"
    python_exe = python_home / "python.exe"
    python_exe.parent.mkdir(parents=True)
    python_exe.write_text("", encoding="utf-8")

    monkeypatch.setattr(sys, "executable", str(qgis_bin / "qgis-bin.exe"))  # type: ignore[attr-defined]
    monkeypatch.setattr(sys, "prefix", str(tmp_path))  # type: ignore[attr-defined]
    monkeypatch.setattr(sys, "exec_prefix", str(tmp_path))  # type: ignore[attr-defined]

    assert find_python_executable() == str(python_exe)


def test_find_python_executable_prefers_newer_apps_python(
    tmp_path: Path, monkeypatch: object
) -> None:
    qgis_bin = tmp_path / "bin"
    qgis_bin.mkdir()

    older = tmp_path / "apps" / "Python310" / "python.exe"
    newer = tmp_path / "apps" / "Python311" / "python.exe"
    for path in (older, newer):
        path.parent.mkdir(parents=True)
        path.write_text("", encoding="utf-8")

    monkeypatch.setattr(sys, "executable", str(qgis_bin / "qgis.exe"))  # type: ignore[attr-defined]
    monkeypatch.setattr(sys, "prefix", str(tmp_path))  # type: ignore[attr-defined]
    monkeypatch.setattr(sys, "exec_prefix", str(tmp_path))  # type: ignore[attr-defined]

    assert find_python_executable() == str(newer)


def test_find_python_executable_linux_apps_layout(
    tmp_path: Path, monkeypatch: object
) -> None:
    qgis_bin = tmp_path / "bin"
    qgis_bin.mkdir()
    python_bin = tmp_path / "apps" / "Python312" / "bin" / "python3"
    python_bin.parent.mkdir(parents=True)
    python_bin.write_text("", encoding="utf-8")

    monkeypatch.setattr(sys, "executable", str(qgis_bin / "qgis"))  # type: ignore[attr-defined]
    monkeypatch.setattr(sys, "prefix", str(tmp_path))  # type: ignore[attr-defined]
    monkeypatch.setattr(sys, "exec_prefix", str(tmp_path))  # type: ignore[attr-defined]

    assert find_python_executable() == str(python_bin)
