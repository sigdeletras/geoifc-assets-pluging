"""Read IFC references from QGIS features."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from geoifcassets.core.models import IfcReference
from geoifcassets.core.validation import (
    resolve_ifc_reference_with_details,
    validate_ifc_reference_fields,
)


class FeatureReadStatus(StrEnum):
    """Possible results when reading the selected feature."""

    OK = "ok"
    NO_LAYER = "no_layer"
    INVALID_LAYER = "invalid_layer"
    NO_SELECTION = "no_selection"
    EMPTY_REFERENCE = "empty_reference"


@dataclass(frozen=True)
class FeatureIfcReferenceReadResult:
    """Result of reading the IFC reference from QGIS selection."""

    status: FeatureReadStatus
    reference: IfcReference | None = None
    available_fields: tuple[str, ...] = ()
    populated_fields: tuple[str, ...] = ()
    has_conflict: bool = False


class SelectedFeatureIfcReferenceReader:
    """Reads the IFC reference from the active selected feature."""

    def read_from_layer(self, layer: Any | None) -> FeatureIfcReferenceReadResult:
        if layer is None:
            return FeatureIfcReferenceReadResult(status=FeatureReadStatus.NO_LAYER)

        fields = [field.name() for field in layer.fields()]
        contract = validate_ifc_reference_fields(fields)
        if not contract.is_valid:
            return FeatureIfcReferenceReadResult(
                status=FeatureReadStatus.INVALID_LAYER,
                available_fields=contract.available_fields,
            )

        selected_features = layer.selectedFeatures()
        if not selected_features:
            return FeatureIfcReferenceReadResult(
                status=FeatureReadStatus.NO_SELECTION,
                available_fields=contract.available_fields,
            )

        feature = selected_features[0]
        attributes = {field_name: feature[field_name] for field_name in fields}
        resolution = resolve_ifc_reference_with_details(attributes)
        if resolution.reference is None:
            return FeatureIfcReferenceReadResult(
                status=FeatureReadStatus.EMPTY_REFERENCE,
                available_fields=contract.available_fields,
                populated_fields=resolution.populated_fields,
            )

        return FeatureIfcReferenceReadResult(
            status=FeatureReadStatus.OK,
            reference=resolution.reference,
            available_fields=contract.available_fields,
            populated_fields=resolution.populated_fields,
            has_conflict=resolution.has_conflict,
        )

    def read_from_feature(
        self, layer: Any | None, feature: Any | None
    ) -> FeatureIfcReferenceReadResult:
        """Read the IFC reference from an explicit layer feature."""
        if layer is None:
            return FeatureIfcReferenceReadResult(status=FeatureReadStatus.NO_LAYER)

        fields = [field.name() for field in layer.fields()]
        contract = validate_ifc_reference_fields(fields)
        if not contract.is_valid:
            return FeatureIfcReferenceReadResult(
                status=FeatureReadStatus.INVALID_LAYER,
                available_fields=contract.available_fields,
            )

        if feature is None:
            return FeatureIfcReferenceReadResult(
                status=FeatureReadStatus.NO_SELECTION,
                available_fields=contract.available_fields,
            )

        attributes = {field_name: feature[field_name] for field_name in fields}
        resolution = resolve_ifc_reference_with_details(attributes)
        if resolution.reference is None:
            return FeatureIfcReferenceReadResult(
                status=FeatureReadStatus.EMPTY_REFERENCE,
                available_fields=contract.available_fields,
                populated_fields=resolution.populated_fields,
            )

        return FeatureIfcReferenceReadResult(
            status=FeatureReadStatus.OK,
            reference=resolution.reference,
            available_fields=contract.available_fields,
            populated_fields=resolution.populated_fields,
            has_conflict=resolution.has_conflict,
        )
