"""Core data structures that do not depend on QGIS."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class IfcReferenceKind(StrEnum):
    """Supported ways to reference an IFC file from a GIS feature."""

    PATH = "ifc_path"
    URL = "ifc_url"


@dataclass(frozen=True)
class IfcReference:
    """Reference to an IFC resource stored in a GIS feature."""

    kind: IfcReferenceKind
    value: str


@dataclass(frozen=True)
class LayerRequirementResult:
    """Result of validating the minimum GIS layer contract."""

    is_valid: bool
    available_fields: tuple[str, ...]
    missing_fields: tuple[str, ...]


@dataclass(frozen=True)
class IfcReferenceResolution:
    """Result of reading IFC reference values from GIS attributes."""

    reference: IfcReference | None
    populated_fields: tuple[str, ...]
    has_conflict: bool


@dataclass(frozen=True)
class IfcModelSummary:
    """Minimal information read from an IFC model."""

    source: str
    schema: str | None
