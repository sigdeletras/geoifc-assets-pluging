"""Validation rules for the MVP layer contract."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from geoifcassets.core.models import (
    IfcReference,
    IfcReferenceKind,
    IfcReferenceResolution,
    LayerRequirementResult,
)

REQUIRED_IFC_FIELD_NAMES: tuple[str, str] = (
    IfcReferenceKind.PATH.value,
    IfcReferenceKind.URL.value,
)


def validate_ifc_reference_fields(field_names: Iterable[str]) -> LayerRequirementResult:
    """Validate that a layer exposes at least one supported IFC reference field."""
    available = tuple(name for name in field_names if name in REQUIRED_IFC_FIELD_NAMES)
    missing = tuple(name for name in REQUIRED_IFC_FIELD_NAMES if name not in available)
    return LayerRequirementResult(
        is_valid=bool(available),
        available_fields=available,
        missing_fields=missing,
    )


def resolve_ifc_reference(attributes: Mapping[str, object]) -> IfcReference | None:
    """Resolve the IFC reference from feature attributes.

    `ifc_path` takes precedence over `ifc_url` when both have values. The UI can still
    ask the user to confirm when both fields are populated.
    """
    path_value = _clean_attribute_value(attributes.get(IfcReferenceKind.PATH.value))
    if path_value:
        return IfcReference(kind=IfcReferenceKind.PATH, value=path_value)

    url_value = _clean_attribute_value(attributes.get(IfcReferenceKind.URL.value))
    if url_value:
        return IfcReference(kind=IfcReferenceKind.URL, value=url_value)

    return None


def resolve_ifc_reference_with_details(
    attributes: Mapping[str, object],
) -> IfcReferenceResolution:
    """Resolve an IFC reference and expose whether both supported fields are populated."""
    populated_fields = tuple(
        field_name
        for field_name in REQUIRED_IFC_FIELD_NAMES
        if _clean_attribute_value(attributes.get(field_name))
    )
    return IfcReferenceResolution(
        reference=resolve_ifc_reference(attributes),
        populated_fields=populated_fields,
        has_conflict=len(populated_fields) > 1,
    )


def _clean_attribute_value(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()
