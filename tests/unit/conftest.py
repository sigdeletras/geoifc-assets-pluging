"""Shared fake IFC object helpers for unit tests.

These classes mimic the IfcOpenShell entity API without any real IFC dependency.
Used to unit-test adapters/ifc/* extractors by injecting a mock ifcopenshell
module into sys.modules before each test.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Fake IFC entity hierarchy
# ---------------------------------------------------------------------------

class FakeValue:
    """Mimics IfcLabel / IfcText / IfcReal .wrappedValue pattern."""

    def __init__(self, value: object) -> None:
        self.wrappedValue = value

    def __str__(self) -> str:
        return str(self.wrappedValue)


class FakeProperty:
    def __init__(self, name: str, value: object) -> None:
        self.Name = name
        self.NominalValue = FakeValue(value)


class FakePropertySet:
    def __init__(self, name: str, properties: list[FakeProperty]) -> None:
        self.Name = name
        self.HasProperties = properties

    def is_a(self, type_name: str) -> bool:
        return type_name == "IfcPropertySet"


class FakeQuantityArea:
    def __init__(self, name: str, area_value: float) -> None:
        self.Name = name
        self.AreaValue = area_value

    def is_a(self, type_name: str) -> bool:
        return type_name == "IfcQuantityArea"


class FakeElementQuantity:
    def __init__(self, name: str, quantities: list) -> None:
        self.Name = name
        self.Quantities = quantities

    def is_a(self, type_name: str) -> bool:
        return type_name == "IfcElementQuantity"


class FakeRel:
    """Mimics IfcRelDefinesByProperties."""

    def __init__(self, pdef: object) -> None:
        self.RelatingPropertyDefinition = pdef

    def is_a(self, type_name: str) -> bool:
        return type_name == "IfcRelDefinesByProperties"


class FakeEntity:
    """Generic fake IFC entity with optional IsDefinedBy relations."""

    def __init__(self, ifc_type: str, **attrs: object) -> None:
        self._ifc_type = ifc_type
        for k, v in attrs.items():
            setattr(self, k, v)
        if not hasattr(self, "IsDefinedBy"):
            self.IsDefinedBy = []

    def is_a(self, type_name: str) -> bool:
        return self._ifc_type == type_name


class FakeIfcModel:
    """Fake IFC model returned by ifcopenshell.open()."""

    def __init__(self, entities_by_type: dict[str, list], schema: str = "IFC4") -> None:
        self._entities = entities_by_type
        self.schema = schema

    def by_type(self, type_name: str) -> list:
        return self._entities.get(type_name, [])


# ---------------------------------------------------------------------------
# Pytest fixture: inject fake ifcopenshell into sys.modules
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_ifcopenshell(monkeypatch):
    """Return a callable that installs a fake ifcopenshell module.

    Usage::

        def test_something(fake_ifcopenshell):
            model = FakeIfcModel({"IfcProject": [FakeEntity("IfcProject", Name="X")]})
            fake_ifcopenshell(model)
            result = extract_model_info("irrelevant.ifc")
    """
    mock_module = MagicMock()

    def _install(model: FakeIfcModel) -> None:
        mock_module.open.return_value = model
        monkeypatch.setitem(sys.modules, "ifcopenshell", mock_module)
        monkeypatch.setitem(sys.modules, "ifcopenshell.util", MagicMock())
        monkeypatch.setitem(sys.modules, "ifcopenshell.util.geolocation", MagicMock())

    return _install
