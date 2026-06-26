"""Core data structures that do not depend on QGIS."""

from __future__ import annotations

from dataclasses import dataclass, field
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


class MetricSource(StrEnum):
    """How a ModelMetric value was obtained."""

    QTO = "qto"           # read from a formal QuantitySet (Qto_*)
    CALCULATED = "calculated"  # derived because formal QtoSet was absent


@dataclass(frozen=True)
class ModelMetric:
    """A single extracted IFC metric ready to be mapped to a GIS field.

    ``suggested_field`` is the recommended GIS field name.  It uses the
    ``ifc_`` prefix for formal QtoSet values and ``ifc_calc_`` for computed
    fallbacks so the user can distinguish origins at a glance.
    """

    label: str            # human-readable display name
    suggested_field: str  # suggested GIS field name (ifc_* or ifc_calc_*)
    value: object         # scalar: str | int | float | None
    unit: str             # "", "m²", "m", "count", etc.
    source: MetricSource


# ── Template-based extraction ────────────────────────────────────────────────


@dataclass
class TemplateField:
    """One field entry from a property extraction template."""

    name: str
    enabled: bool
    group: str = ""        # canonical English key — used for ordering
    alias: str = ""
    description: str = ""
    ifc_source: str = ""
    aggregate: str = "count"   # "count" | "first" | "all" — strategy for custom fields
    group_label: str = ""  # localized display name; falls back to group when empty


@dataclass
class PropertyTemplate:
    """A fully loaded and enriched property extraction template."""

    template_name: str
    extractor_version: str
    description: str
    fields: list[TemplateField]


@dataclass
class IFCClassDiscovery:
    """Discovered IFC class info for the Properties → IFC Classes section."""

    ifc_class: str
    prefix: str       # class name without "Ifc", lowercase  (IfcWall → "wall")
    count: int
    available: set    # subset of {"count", "length", "area", "volume"} with QtoSet data
    values: dict = field(default_factory=dict)   # {metric: extracted_value_or_None}
    sources: dict = field(default_factory=dict)  # {metric: "Qto" | "calc" | "—"}
