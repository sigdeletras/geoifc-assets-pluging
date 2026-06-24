from __future__ import annotations

import pytest

from tests.unit.conftest import (
    FakeElementQuantity,
    FakeEntity,
    FakeIfcModel,
    FakeQuantityArea,
    FakeRel,
)
from geoifcassets.core.models import MetricSource


def test_counts_walls_doors_windows(fake_ifcopenshell) -> None:
    from geoifcassets.adapters.ifc.quantity_extractor import extract_quantities

    model = FakeIfcModel({
        "IfcWall": [FakeEntity("IfcWall") for _ in range(5)],
        "IfcDoor": [FakeEntity("IfcDoor") for _ in range(3)],
        "IfcWindow": [FakeEntity("IfcWindow") for _ in range(8)],
    })
    fake_ifcopenshell(model)

    metrics = extract_quantities("test.ifc")

    by_field = {m.suggested_field: m.value for m in metrics}
    assert by_field["ifc_wall_count"] == 5
    assert by_field["ifc_door_count"] == 3
    assert by_field["ifc_window_count"] == 8


def test_counts_storeys(fake_ifcopenshell) -> None:
    from geoifcassets.adapters.ifc.quantity_extractor import extract_quantities

    storeys = [
        FakeEntity("IfcBuildingStorey", Name="PB", Elevation=0.0),
        FakeEntity("IfcBuildingStorey", Name="P1", Elevation=3.1),
    ]
    model = FakeIfcModel({"IfcBuildingStorey": storeys})
    fake_ifcopenshell(model)

    metrics = extract_quantities("test.ifc")

    by_field = {m.suggested_field: m.value for m in metrics}
    assert by_field["ifc_storey_count"] == 2


def test_sums_floor_area_from_qto(fake_ifcopenshell) -> None:
    from geoifcassets.adapters.ifc.quantity_extractor import extract_quantities

    def _storey_with_area(name, elevation, area):
        qto = FakeElementQuantity(
            "Qto_BuildingStoreyBaseQuantities",
            [FakeQuantityArea("GrossFloorArea", area)],
        )
        storey = FakeEntity("IfcBuildingStorey", Name=name, Elevation=elevation)
        storey.IsDefinedBy = [FakeRel(qto)]
        return storey

    model = FakeIfcModel({
        "IfcBuildingStorey": [
            _storey_with_area("PB", 0.0, 250.5),
            _storey_with_area("P1", 3.1, 242.0),
        ],
    })
    fake_ifcopenshell(model)

    metrics = extract_quantities("test.ifc")

    gross = next(m for m in metrics if m.suggested_field == "ifc_gross_floor_area")
    assert gross.value == pytest.approx(492.5)
    assert gross.source is MetricSource.QTO
    assert gross.unit == "m²"


def test_floor_area_absent_when_no_qto(fake_ifcopenshell) -> None:
    from geoifcassets.adapters.ifc.quantity_extractor import extract_quantities

    model = FakeIfcModel({
        "IfcBuildingStorey": [FakeEntity("IfcBuildingStorey", Name="PB", Elevation=0.0)],
    })
    fake_ifcopenshell(model)

    metrics = extract_quantities("test.ifc")

    fields = {m.suggested_field for m in metrics}
    assert "ifc_gross_floor_area" not in fields
    assert "ifc_calc_gross_floor_area" not in fields


def test_sums_wall_area_from_qto(fake_ifcopenshell) -> None:
    from geoifcassets.adapters.ifc.quantity_extractor import extract_quantities

    def _wall_with_area(area):
        qto = FakeElementQuantity(
            "Qto_WallBaseQuantities",
            [FakeQuantityArea("GrossSideArea", area)],
        )
        wall = FakeEntity("IfcWall")
        wall.IsDefinedBy = [FakeRel(qto)]
        return wall

    model = FakeIfcModel({
        "IfcWall": [_wall_with_area(30.0), _wall_with_area(25.5)],
    })
    fake_ifcopenshell(model)

    metrics = extract_quantities("test.ifc")

    wall_area = next(m for m in metrics if m.suggested_field == "ifc_gross_wall_area")
    assert wall_area.value == pytest.approx(55.5)
    assert wall_area.source is MetricSource.QTO


def test_wall_area_absent_when_no_qto(fake_ifcopenshell) -> None:
    from geoifcassets.adapters.ifc.quantity_extractor import extract_quantities

    model = FakeIfcModel({"IfcWall": [FakeEntity("IfcWall")]})
    fake_ifcopenshell(model)

    metrics = extract_quantities("test.ifc")

    fields = {m.suggested_field for m in metrics}
    assert "ifc_gross_wall_area" not in fields


def test_returns_empty_on_bad_file(fake_ifcopenshell, monkeypatch) -> None:
    import sys
    from unittest.mock import MagicMock

    from geoifcassets.adapters.ifc.quantity_extractor import extract_quantities

    broken = MagicMock()
    broken.open.side_effect = OSError("not found")
    monkeypatch.setitem(sys.modules, "ifcopenshell", broken)

    assert extract_quantities("missing.ifc") == []
