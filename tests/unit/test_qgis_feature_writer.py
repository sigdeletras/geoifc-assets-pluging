from __future__ import annotations

from geoifcassets.adapters.qgis.feature_writer import (
    FeatureWriteStatus,
    SelectedFeatureAttributeWriter,
)
from geoifcassets.core.mapping import AttributeUpdate


class FakeField:
    def __init__(self, name: str) -> None:
        self._name = name

    def name(self) -> str:
        return self._name


class FakeWritableFeature:
    def __init__(self, feature_id: int) -> None:
        self._feature_id = feature_id

    def id(self) -> int:
        return self._feature_id


class FakeWritableLayer:
    def __init__(
        self,
        field_names: list[str],
        selected_features: list[FakeWritableFeature],
        *,
        editable: bool = True,
        can_start_editing: bool = True,
        can_write: bool = True,
    ) -> None:
        self._fields = [FakeField(name) for name in field_names]
        self._selected_features = selected_features
        self._editable = editable
        self._can_start_editing = can_start_editing
        self._can_write = can_write
        self.changes: list[tuple[int, int, object]] = []

    def fields(self) -> list[FakeField]:
        return self._fields

    def selectedFeatures(self) -> list[FakeWritableFeature]:  # noqa: N802
        return self._selected_features

    def isEditable(self) -> bool:  # noqa: N802
        return self._editable

    def startEditing(self) -> bool:  # noqa: N802
        self._editable = self._can_start_editing
        return self._can_start_editing

    def changeAttributeValue(  # noqa: N802
        self,
        feature_id: int,
        field_index: int,
        value: object,
    ) -> bool:
        if not self._can_write:
            return False
        self.changes.append((feature_id, field_index, value))
        return True


def test_writer_updates_existing_fields_on_selected_feature() -> None:
    layer = FakeWritableLayer(["asset_name"], [FakeWritableFeature(10)])

    result = SelectedFeatureAttributeWriter().write_to_layer(
        layer,
        (AttributeUpdate(field_name="asset_name", value="Bridge"),),
    )

    assert result.status is FeatureWriteStatus.OK
    assert result.updated_fields == ("asset_name",)
    assert layer.changes == [(10, 0, "Bridge")]


def test_writer_reports_missing_fields() -> None:
    layer = FakeWritableLayer(["name"], [FakeWritableFeature(10)])

    result = SelectedFeatureAttributeWriter().write_to_layer(
        layer,
        (AttributeUpdate(field_name="asset_name", value="Bridge"),),
    )

    assert result.status is FeatureWriteStatus.FIELD_NOT_FOUND
    assert result.missing_fields == ("asset_name",)


def test_writer_reports_layer_not_editable() -> None:
    layer = FakeWritableLayer(
        ["asset_name"],
        [FakeWritableFeature(10)],
        editable=False,
        can_start_editing=False,
    )

    result = SelectedFeatureAttributeWriter().write_to_layer(
        layer,
        (AttributeUpdate(field_name="asset_name", value="Bridge"),),
    )

    assert result.status is FeatureWriteStatus.LAYER_NOT_EDITABLE
