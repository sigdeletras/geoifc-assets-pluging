from __future__ import annotations

from pathlib import Path

from geoifcassets.adapters.ifc.reader import IfcReader, IfcReadStatus


def test_ifc_reader_detects_schema_from_local_file(tmp_path: Path) -> None:
    ifc_file = tmp_path / "asset.ifc"
    ifc_file.write_text(
        "ISO-10303-21;\nHEADER;\nFILE_SCHEMA(('IFC4X3'));\nENDSEC;\n",
        encoding="utf-8",
    )

    result = IfcReader().read_summary(str(ifc_file))

    assert result.status is IfcReadStatus.OK
    assert result.summary is not None
    assert result.summary.schema == "IFC4X3"


def test_ifc_reader_detects_schema_with_double_quotes(tmp_path: Path) -> None:
    ifc_file = tmp_path / "asset.ifc"
    ifc_file.write_text(
        'ISO-10303-21;\nHEADER;\nFILE_SCHEMA(("IFC4"));\nENDSEC;\n',
        encoding="utf-8",
    )

    result = IfcReader().read_summary(str(ifc_file))

    assert result.status is IfcReadStatus.OK
    assert result.summary is not None
    assert result.summary.schema == "IFC4"


def test_ifc_reader_reports_missing_file() -> None:
    result = IfcReader().read_summary("missing.ifc")

    assert result.status is IfcReadStatus.FILE_NOT_FOUND


def test_ifc_reader_reports_url_as_not_local_file() -> None:
    result = IfcReader().read_summary("https://example.test/model.ifc")

    assert result.status is IfcReadStatus.NOT_LOCAL_FILE


def test_ifc_reader_reports_html_saved_as_ifc(tmp_path: Path) -> None:
    ifc_file = tmp_path / "asset.ifc"
    ifc_file.write_text("<!DOCTYPE html><html><body>GitHub page</body></html>", encoding="utf-8")

    result = IfcReader().read_summary(str(ifc_file))

    assert result.status is IfcReadStatus.NOT_IFC_FILE
