from __future__ import annotations

from pathlib import Path

from geoifcassets.adapters.qgis.viewer import _viewer_open_reference_script
from geoifcassets.core.models import IfcReference, IfcReferenceKind


def test_viewer_open_reference_script_escapes_windows_paths() -> None:
    script = _viewer_open_reference_script(
        IfcReference(
            kind=IfcReferenceKind.PATH,
            value=r"D:\models\Building-Architecture.ifc",
        )
    )

    assert "window.GeoIfcViewer.openReference" in script
    assert '"kind": "ifc_path"' in script
    assert r"D:\\models\\Building-Architecture.ifc" in script


def test_viewer_open_reference_script_embeds_local_ifc_bytes(tmp_path: Path) -> None:
    ifc_file = tmp_path / "sample.ifc"
    ifc_file.write_text("ISO-10303-21;", encoding="utf-8")

    script = _viewer_open_reference_script(
        IfcReference(kind=IfcReferenceKind.PATH, value=str(ifc_file))
    )

    assert '"dataBase64": "SVNPLTEwMzAzLTIxOw=="' in script
