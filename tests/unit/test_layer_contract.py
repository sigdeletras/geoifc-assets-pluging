from __future__ import annotations

from geoifcassets.core.models import IfcReferenceKind
from geoifcassets.core.validation import (
    resolve_ifc_reference,
    resolve_ifc_reference_with_details,
    validate_ifc_reference_fields,
)


def test_layer_is_valid_with_ifc_path() -> None:
    result = validate_ifc_reference_fields(["name", "ifc_path"])

    assert result.is_valid is True
    assert result.available_fields == ("ifc_path",)


def test_layer_is_valid_with_ifc_url() -> None:
    result = validate_ifc_reference_fields(["id", "ifc_url"])

    assert result.is_valid is True
    assert result.available_fields == ("ifc_url",)


def test_layer_is_invalid_without_ifc_reference_fields() -> None:
    result = validate_ifc_reference_fields(["id", "name"])

    assert result.is_valid is False
    assert result.missing_fields == ("ifc_path", "ifc_url")


def test_resolve_ifc_reference_prefers_path() -> None:
    reference = resolve_ifc_reference(
        {
            "ifc_path": "models/asset.ifc",
            "ifc_url": "https://example.test/asset.ifc",
        }
    )

    assert reference is not None
    assert reference.kind is IfcReferenceKind.PATH
    assert reference.value == "models/asset.ifc"


def test_resolve_ifc_reference_uses_url_when_path_is_empty() -> None:
    reference = resolve_ifc_reference(
        {
            "ifc_path": " ",
            "ifc_url": "https://example.test/asset.ifc",
        }
    )

    assert reference is not None
    assert reference.kind is IfcReferenceKind.URL
    assert reference.value == "https://example.test/asset.ifc"


def test_resolve_ifc_reference_details_detects_conflict() -> None:
    resolution = resolve_ifc_reference_with_details(
        {
            "ifc_path": "models/asset.ifc",
            "ifc_url": "https://example.test/asset.ifc",
        }
    )

    assert resolution.reference is not None
    assert resolution.reference.kind is IfcReferenceKind.PATH
    assert resolution.populated_fields == ("ifc_path", "ifc_url")
    assert resolution.has_conflict is True
