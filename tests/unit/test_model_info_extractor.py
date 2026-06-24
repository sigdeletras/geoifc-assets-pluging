from __future__ import annotations

import pytest

from tests.unit.conftest import (
    FakeEntity,
    FakeIfcModel,
    FakeProperty,
    FakePropertySet,
    FakeRel,
)


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def test_parse_epsg_finds_5_digit_code() -> None:
    from geoifcassets.adapters.ifc.model_info_extractor import _parse_epsg

    assert _parse_epsg("ETRS89 / UTM zone 30N (EPSG:25830)") == "25830"


def test_parse_epsg_finds_bare_4_digit_code() -> None:
    from geoifcassets.adapters.ifc.model_info_extractor import _parse_epsg

    assert _parse_epsg("4326") == "4326"


def test_parse_epsg_returns_none_when_absent() -> None:
    from geoifcassets.adapters.ifc.model_info_extractor import _parse_epsg

    assert _parse_epsg("WGS 84") is None


def test_str_or_none_strips_whitespace() -> None:
    from geoifcassets.adapters.ifc.model_info_extractor import _str_or_none

    assert _str_or_none("  hello  ") == "hello"


def test_str_or_none_returns_none_for_empty() -> None:
    from geoifcassets.adapters.ifc.model_info_extractor import _str_or_none

    assert _str_or_none("") is None
    assert _str_or_none("   ") is None
    assert _str_or_none(None) is None


# ---------------------------------------------------------------------------
# extract_model_info — using fake_ifcopenshell fixture
# ---------------------------------------------------------------------------

def test_extract_project_name(fake_ifcopenshell) -> None:
    from geoifcassets.adapters.ifc.model_info_extractor import extract_model_info

    model = FakeIfcModel({
        "IfcProject": [FakeEntity("IfcProject", Name="Hospital Central", Description=None, Phase=None)],
    })
    fake_ifcopenshell(model)

    metrics = extract_model_info("test.ifc")

    by_field = {m.suggested_field: m.value for m in metrics}
    assert by_field["ifc_project_name"] == "Hospital Central"
    assert "ifc_project_description" not in by_field


def test_extract_project_description_and_phase(fake_ifcopenshell) -> None:
    from geoifcassets.adapters.ifc.model_info_extractor import extract_model_info

    model = FakeIfcModel({
        "IfcProject": [FakeEntity(
            "IfcProject",
            Name="P",
            Description="Main building",
            Phase="Construction",
        )],
    })
    fake_ifcopenshell(model)

    metrics = extract_model_info("test.ifc")

    by_field = {m.suggested_field: m.value for m in metrics}
    assert by_field["ifc_project_description"] == "Main building"
    assert by_field["ifc_project_phase"] == "Construction"


def test_extract_schema(fake_ifcopenshell) -> None:
    from geoifcassets.adapters.ifc.model_info_extractor import extract_model_info

    model = FakeIfcModel({"IfcProject": []}, schema="IFC4X3")
    fake_ifcopenshell(model)

    metrics = extract_model_info("test.ifc")

    by_field = {m.suggested_field: m.value for m in metrics}
    assert by_field["ifc_schema"] == "IFC4X3"


def test_extract_building_name(fake_ifcopenshell) -> None:
    from geoifcassets.adapters.ifc.model_info_extractor import extract_model_info

    model = FakeIfcModel({
        "IfcBuilding": [FakeEntity("IfcBuilding", Name="Block A")],
    })
    fake_ifcopenshell(model)

    metrics = extract_model_info("test.ifc")

    by_field = {m.suggested_field: m.value for m in metrics}
    assert by_field["ifc_building_name"] == "Block A"


def test_extract_occupancy_type_from_pset(fake_ifcopenshell) -> None:
    from geoifcassets.adapters.ifc.model_info_extractor import extract_model_info

    pset = FakePropertySet(
        "Pset_BuildingCommon",
        [FakeProperty("OccupancyType", "Residential")],
    )
    building = FakeEntity("IfcBuilding", Name=None)
    building.IsDefinedBy = [FakeRel(pset)]

    model = FakeIfcModel({"IfcBuilding": [building]})
    fake_ifcopenshell(model)

    metrics = extract_model_info("test.ifc")

    by_field = {m.suggested_field: m.value for m in metrics}
    assert by_field["ifc_occupancy_type"] == "Residential"


def test_extract_crs_with_epsg(fake_ifcopenshell) -> None:
    from geoifcassets.adapters.ifc.model_info_extractor import extract_model_info

    crs = FakeEntity("IfcCoordinateReferenceSystem", Name="ETRS89 / UTM 30N (25830)")
    model = FakeIfcModel({"IfcCoordinateReferenceSystem": [crs]})
    fake_ifcopenshell(model)

    metrics = extract_model_info("test.ifc")

    by_field = {m.suggested_field: m.value for m in metrics}
    assert by_field["ifc_crs"] == "EPSG:25830"


def test_returns_empty_list_when_ifc_cannot_be_opened(fake_ifcopenshell, monkeypatch) -> None:
    import sys
    from unittest.mock import MagicMock

    from geoifcassets.adapters.ifc.model_info_extractor import extract_model_info

    broken = MagicMock()
    broken.open.side_effect = OSError("file not found")
    monkeypatch.setitem(sys.modules, "ifcopenshell", broken)

    result = extract_model_info("missing.ifc")

    assert result == []
