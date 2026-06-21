"""Write prepared IFC values into selected QGIS feature attributes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from geoifcassets.core.mapping import AttributeUpdate


class FeatureWriteStatus(StrEnum):
    """Possible results when writing attributes to a selected feature."""

    OK = "ok"
    NO_LAYER = "no_layer"
    NO_SELECTION = "no_selection"
    FIELD_NOT_FOUND = "field_not_found"
    LAYER_NOT_EDITABLE = "layer_not_editable"
    WRITE_FAILED = "write_failed"


@dataclass(frozen=True)
class FeatureWriteResult:
    """Result of writing attributes into a selected feature."""

    status: FeatureWriteStatus
    updated_fields: tuple[str, ...] = ()
    missing_fields: tuple[str, ...] = ()


class SelectedFeatureAttributeWriter:
    """Apply attribute updates to the first selected feature of a QGIS layer."""

    def write_to_layer(
        self,
        layer: Any | None,
        updates: tuple[AttributeUpdate, ...],
    ) -> FeatureWriteResult:
        if layer is None:
            return FeatureWriteResult(status=FeatureWriteStatus.NO_LAYER)

        selected_features = layer.selectedFeatures()
        if not selected_features:
            return FeatureWriteResult(status=FeatureWriteStatus.NO_SELECTION)

        field_names = [field.name() for field in layer.fields()]
        missing_fields = tuple(
            update.field_name for update in updates if update.field_name not in field_names
        )
        if missing_fields:
            return FeatureWriteResult(
                status=FeatureWriteStatus.FIELD_NOT_FOUND,
                missing_fields=missing_fields,
            )

        if not layer.isEditable() and not layer.startEditing():
            return FeatureWriteResult(status=FeatureWriteStatus.LAYER_NOT_EDITABLE)

        feature = selected_features[0]
        feature_id = feature.id()
        updated_fields: list[str] = []
        for update in updates:
            field_index = field_names.index(update.field_name)
            if not layer.changeAttributeValue(feature_id, field_index, update.value):
                return FeatureWriteResult(
                    status=FeatureWriteStatus.WRITE_FAILED,
                    updated_fields=tuple(updated_fields),
                )
            updated_fields.append(update.field_name)

        return FeatureWriteResult(
            status=FeatureWriteStatus.OK,
            updated_fields=tuple(updated_fields),
        )
