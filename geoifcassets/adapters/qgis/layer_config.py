"""Layer validation adapter for the MVP field contract."""

from __future__ import annotations

from typing import Any

from geoifcassets.core.models import LayerRequirementResult
from geoifcassets.core.validation import validate_ifc_reference_fields


class QgisLayerContractValidator:
    """Validate that a QGIS layer can be used by the MVP."""

    def validate(self, layer: Any) -> LayerRequirementResult:
        fields = [field.name() for field in layer.fields()]
        return validate_ifc_reference_fields(fields)
