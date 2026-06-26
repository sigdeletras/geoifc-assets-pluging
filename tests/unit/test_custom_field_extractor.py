"""Unit tests for adapters/ifc/custom_field_extractor.py.

Tests that don't require ifcopenshell cover parsing, is_dynamic_source, and
the pure-Python aggregate helpers via simple mock element objects.
"""

from __future__ import annotations

import pytest

from geoifcassets.adapters.ifc.custom_field_extractor import (
    _aggregate_count,
    _aggregate_first,
    _aggregate_sum,
    _element_has_value,
    _element_numeric_value,
    _element_raw_value,
    _extract_one,
    _parse_source,
    is_dynamic_source,
)
from geoifcassets.core.models import TemplateField


# ── is_dynamic_source ────────────────────────────────────────────────────────

def test_is_dynamic_pset_bare():
    assert is_dynamic_source("Pset_WallCommon.IsExternal") is True


def test_is_dynamic_qto_bare():
    assert is_dynamic_source("Qto_WallBaseQuantities.GrossArea") is True


def test_is_dynamic_pset_with_class():
    assert is_dynamic_source("IfcWall:Pset_WallCommon.IsExternal") is True


def test_is_dynamic_qto_with_class():
    assert is_dynamic_source("IfcWall:Qto_WallBaseQuantities.GrossArea") is True


def test_is_dynamic_false_for_core_source():
    assert is_dynamic_source("file.path") is False
    assert is_dynamic_source("header.project_name") is False


def test_is_dynamic_false_for_class_only():
    assert is_dynamic_source("IfcWall") is False


def test_is_dynamic_false_for_empty():
    assert is_dynamic_source("") is False


# ── _parse_source ─────────────────────────────────────────────────────────────

def test_parse_scoped_pset():
    ifc_class, container, prop, source_type = _parse_source("IfcWall:Pset_WallCommon.IsExternal")
    assert ifc_class == "IfcWall"
    assert container == "Pset_WallCommon"
    assert prop == "IsExternal"
    assert source_type == "pset"


def test_parse_scoped_qto():
    ifc_class, container, prop, source_type = _parse_source("IfcWall:Qto_WallBaseQuantities.GrossArea")
    assert ifc_class == "IfcWall"
    assert container == "Qto_WallBaseQuantities"
    assert prop == "GrossArea"
    assert source_type == "qto"


def test_parse_bare_pset():
    ifc_class, container, prop, source_type = _parse_source("Pset_SpaceCommon.OccupancyType")
    assert ifc_class is None
    assert container == "Pset_SpaceCommon"
    assert prop == "OccupancyType"
    assert source_type == "pset"


def test_parse_class_only_no_dot():
    ifc_class, container, prop, _ = _parse_source("IfcWall")
    assert ifc_class is None
    assert container == "IfcWall"
    assert prop == ""


# ── Mock element helpers ──────────────────────────────────────────────────────

class _MockNominalValue:
    def __init__(self, v):
        self.wrappedValue = v


class _MockProp:
    def __init__(self, name, value=None):
        self.Name = name
        self.NominalValue = _MockNominalValue(value) if value is not None else None

    def is_a(self, ifc_type):
        return ifc_type == "IfcPropertySingleValue"


class _MockPset:
    def __init__(self, name, props):
        self.Name = name
        self.Properties = props

    def is_a(self, ifc_type):
        return ifc_type == "IfcPropertySet"


class _MockQuantity:
    def __init__(self, name, length=None, area=None):
        self.Name = name
        self.LengthValue = length
        self.AreaValue = area
        self.VolumeValue = None
        self.WeightValue = None
        self.CountValue = None
        self.TimeValue = None

    def is_a(self, _):
        return False


class _MockElementQuantity:
    def __init__(self, name, quantities):
        self.Name = name
        self.Quantities = quantities

    def is_a(self, ifc_type):
        return ifc_type == "IfcElementQuantity"


class _MockRel:
    def __init__(self, pdef):
        self.RelatingPropertyDefinition = pdef

    def is_a(self, ifc_type):
        return ifc_type == "IfcRelDefinesByProperties"


class _MockElement:
    def __init__(self, rels):
        self.IsDefinedBy = rels


def _wall_with_pset(prop_name, value):
    prop = _MockProp(prop_name, value)
    pset = _MockPset("Pset_WallCommon", [prop])
    rel = _MockRel(pset)
    return _MockElement([rel])


def _wall_with_qto(qty_name, length=None, area=None):
    qty = _MockQuantity(qty_name, length=length, area=area)
    eqty = _MockElementQuantity("Qto_WallBaseQuantities", [qty])
    rel = _MockRel(eqty)
    return _MockElement([rel])


# ── _element_has_value ────────────────────────────────────────────────────────

def test_element_has_value_pset_true():
    el = _wall_with_pset("IsExternal", True)
    assert _element_has_value(el, "Pset_WallCommon", "IsExternal", "pset") is True


def test_element_has_value_pset_false_when_null():
    el = _wall_with_pset("IsExternal", None)
    assert _element_has_value(el, "Pset_WallCommon", "IsExternal", "pset") is False


def test_element_has_value_qto_true():
    el = _wall_with_qto("GrossArea", area=25.0)
    assert _element_has_value(el, "Qto_WallBaseQuantities", "GrossArea", "qto") is True


def test_element_has_value_wrong_container():
    el = _wall_with_pset("IsExternal", True)
    assert _element_has_value(el, "Pset_SlabCommon", "IsExternal", "pset") is False


def test_element_has_value_wrong_prop():
    el = _wall_with_pset("IsExternal", True)
    assert _element_has_value(el, "Pset_WallCommon", "FireRating", "pset") is False


# ── _element_numeric_value ────────────────────────────────────────────────────

def test_element_numeric_value_pset():
    el = _wall_with_pset("Height", 3.2)
    assert _element_numeric_value(el, "Pset_WallCommon", "Height", "pset") == pytest.approx(3.2)


def test_element_numeric_value_qto_area():
    el = _wall_with_qto("GrossArea", area=42.5)
    assert _element_numeric_value(el, "Qto_WallBaseQuantities", "GrossArea", "qto") == pytest.approx(42.5)


def test_element_numeric_value_none_when_absent():
    el = _wall_with_pset("IsExternal", True)
    assert _element_numeric_value(el, "Pset_WallCommon", "FireRating", "pset") is None


# ── _aggregate_count ──────────────────────────────────────────────────────────

def test_aggregate_count_all_have_value():
    elements = [_wall_with_pset("IsExternal", True), _wall_with_pset("IsExternal", False)]
    assert _aggregate_count(elements, "Pset_WallCommon", "IsExternal", "pset") == 2


def test_aggregate_count_some_missing():
    elements = [
        _wall_with_pset("IsExternal", True),
        _wall_with_pset("FireRating", "60"),   # has a different prop
    ]
    assert _aggregate_count(elements, "Pset_WallCommon", "IsExternal", "pset") == 1


def test_aggregate_count_returns_zero_not_none():
    elements = [_wall_with_pset("FireRating", "60")]
    result = _aggregate_count(elements, "Pset_WallCommon", "IsExternal", "pset")
    assert result == 0
    assert result is not None


# ── _aggregate_sum ────────────────────────────────────────────────────────────

def test_aggregate_sum_qto():
    elements = [
        _wall_with_qto("GrossArea", area=10.0),
        _wall_with_qto("GrossArea", area=15.0),
    ]
    assert _aggregate_sum(elements, "Qto_WallBaseQuantities", "GrossArea", "qto") == pytest.approx(25.0)


def test_aggregate_sum_none_when_no_values():
    elements = [_wall_with_pset("IsExternal", True)]
    assert _aggregate_sum(elements, "Qto_WallBaseQuantities", "GrossArea", "qto") is None


# ── _aggregate_first ──────────────────────────────────────────────────────────

def test_aggregate_first_returns_first():
    elements = [
        _wall_with_pset("FireRating", "60"),
        _wall_with_pset("FireRating", "90"),
    ]
    result = _aggregate_first(elements, "Pset_WallCommon", "FireRating", "pset")
    assert result == "60"


def test_aggregate_first_returns_none_when_absent():
    elements = [_wall_with_pset("IsExternal", True)]
    assert _aggregate_first(elements, "Pset_WallCommon", "FireRating", "pset") is None


# ── _extract_one with entity_count ────────────────────────────────────────────

class _MockIfc:
    def __init__(self, elements_by_type):
        self._elements_by_type = elements_by_type

    def by_type(self, ifc_class):
        return self._elements_by_type.get(ifc_class, [])


def test_extract_one_entity_count():
    ifc = _MockIfc({"IfcWall": ["w1", "w2", "w3"]})
    result = _extract_one(ifc, "IfcWall", "entity_count")
    assert result == 3


def test_extract_one_entity_count_zero_is_valid():
    ifc = _MockIfc({})
    result = _extract_one(ifc, "IfcWall", "entity_count")
    assert result == 0
    assert result is not None


def test_extract_one_count_returns_none_when_class_absent():
    ifc = _MockIfc({})
    result = _extract_one(ifc, "IfcWall:Pset_WallCommon.IsExternal", "count")

    # IfcWall not in model → None
    assert result is None


def test_extract_one_count_returns_zero_when_class_present_no_pset():
    wall = _wall_with_pset("FireRating", "60")
    ifc = _MockIfc({"IfcWall": [wall]})
    result = _extract_one(ifc, "IfcWall:Pset_WallCommon.IsExternal", "count")
    assert result == 0
    assert result is not None
