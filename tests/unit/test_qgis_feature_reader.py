from __future__ import annotations

from typing import Any

from geoifcassets.adapters.qgis.feature_reader import (
    FeatureReadStatus,
    SelectedFeatureIfcReferenceReader,
)
from geoifcassets.core.models import IfcReferenceKind


class FakeField:
    def __init__(self, name: str) -> None:
        self._name = name

    def name(self) -> str:
        return self._name


class FakeFeature:
    def __init__(self, attributes: dict[str, object]) -> None:
        self._attributes = attributes

    def __getitem__(self, field_name: str) -> object:
        return self._attributes.get(field_name)


class FakeLayer:
    def __init__(self, field_names: list[str], selected_features: list[FakeFeature]) -> None:
        self._fields = [FakeField(name) for name in field_names]
        self._selected_features = selected_features

    def fields(self) -> list[FakeField]:
        return self._fields

    def selectedFeatures(self) -> list[FakeFeature]:  # noqa: N802
        return self._selected_features


def test_reader_reports_no_layer() -> None:
    result = SelectedFeatureIfcReferenceReader().read_from_layer(None)

    assert result.status is FeatureReadStatus.NO_LAYER


def test_reader_reports_invalid_layer_without_ifc_fields() -> None:
    layer = FakeLayer(["id", "name"], [])

    result = SelectedFeatureIfcReferenceReader().read_from_layer(layer)

    assert result.status is FeatureReadStatus.INVALID_LAYER


def test_reader_reports_no_selection() -> None:
    layer = FakeLayer(["id", "ifc_path"], [])

    result = SelectedFeatureIfcReferenceReader().read_from_layer(layer)

    assert result.status is FeatureReadStatus.NO_SELECTION
    assert result.available_fields == ("ifc_path",)


def test_reader_resolves_selected_feature_reference() -> None:
    layer = FakeLayer(["id", "ifc_url"], [FakeFeature({"ifc_url": "https://example.test/a.ifc"})])

    result = SelectedFeatureIfcReferenceReader().read_from_layer(layer)

    assert result.status is FeatureReadStatus.OK
    assert result.reference is not None
    assert result.reference.kind is IfcReferenceKind.URL
    assert result.reference.value == "https://example.test/a.ifc"


def test_reader_resolves_explicit_feature_reference() -> None:
    feature = FakeFeature({"ifc_path": "models/a.ifc"})
    layer = FakeLayer(["id", "ifc_path"], [])

    result = SelectedFeatureIfcReferenceReader().read_from_feature(layer, feature)

    assert result.status is FeatureReadStatus.OK
    assert result.reference is not None
    assert result.reference.kind is IfcReferenceKind.PATH
    assert result.reference.value == "models/a.ifc"


def test_reader_detects_populated_path_and_url() -> None:
    layer = FakeLayer(
        ["ifc_path", "ifc_url"],
        [FakeFeature({"ifc_path": "local.ifc", "ifc_url": "https://example.test/a.ifc"})],
    )

    result = SelectedFeatureIfcReferenceReader().read_from_layer(layer)

    assert result.status is FeatureReadStatus.OK
    assert result.reference is not None
    assert result.reference.kind is IfcReferenceKind.PATH
    assert result.populated_fields == ("ifc_path", "ifc_url")
    assert result.has_conflict is True


def accepts_any_layer(layer: Any) -> object:
    return SelectedFeatureIfcReferenceReader().read_from_layer(layer)
