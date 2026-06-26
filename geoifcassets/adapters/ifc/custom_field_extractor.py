"""Extract custom fields declared via ``ifc_source`` in a user template.

ifc_source notation:
    Pset_Name.PropName            → PropertySet on any IfcElement
    Qto_Name.PropName             → QuantitySet on any IfcElement
    IfcClass:Pset_Name.PropName   → PropertySet scoped to one IFC class
    IfcClass:Qto_Name.PropName    → QuantitySet scoped to one IFC class
    IfcClass                      → class name only, used with aggregate "entity_count"

aggregate strategies:
    count        → number of elements that have the property/quantity with a non-null value;
                   returns None when the ifc_class is absent from the model, 0 when present
                   but no elements have the property set
    entity_count → total number of elements of the given IFC class (no property check);
                   ifc_source must be just the class name, e.g. "IfcWall"
    sum          → numeric sum of the property/quantity value across all matching elements;
                   returns None when no element has the value
    first        → first non-null value found; useful for project-level string/boolean properties

Loading more than one custom JSON simultaneously is a documented future evolution.
"""

from __future__ import annotations

import logging
from typing import Any

from geoifcassets.core.models import TemplateField

_log = logging.getLogger("geoifcassets")


def is_dynamic_source(ifc_source: str) -> bool:
    """True when ``ifc_source`` references a PropertySet (Pset_) or QuantitySet (Qto_)."""
    if not ifc_source:
        return False
    rest = ifc_source.split(":", 1)[-1]
    return rest.startswith("Pset_") or rest.startswith("Qto_")


def extract_custom_fields(
    ifc_path: str,
    fields: list[TemplateField],
) -> dict[str, Any]:
    """Return ``{field.name: value}`` for all enabled custom fields.

    Handles all aggregate strategies: count, entity_count, sum, first.
    Returns None for fields whose IFC class is absent from the model.
    Returns 0 for count/entity_count when the class is present but no elements
    match the property criterion.
    """
    active = [f for f in fields if f.enabled]
    if not active:
        return {}

    import ifcopenshell  # noqa: PLC0415

    try:
        ifc = ifcopenshell.open(ifc_path)
    except Exception as exc:  # noqa: BLE001
        _log.warning("custom_field_extractor: cannot open %s: %s", ifc_path, exc)
        return {f.name: None for f in active}

    result: dict[str, Any] = {}
    for field in active:
        try:
            result[field.name] = _extract_one(ifc, field.ifc_source, field.aggregate)
        except Exception as exc:  # noqa: BLE001
            _log.debug("custom_field_extractor: field %r failed: %s", field.name, exc)
            result[field.name] = None

    _log.info(
        "custom_field_extractor: extracted %d/%d custom fields from %s",
        sum(1 for v in result.values() if v is not None),
        len(active),
        ifc_path,
    )
    return result


# ── Internal ──────────────────────────────────────────────────────────────────


def _parse_source(ifc_source: str) -> tuple[str | None, str, str, str]:
    """Parse ifc_source → ``(ifc_class, container_name, prop_name, source_type)``.

    ``source_type`` is ``"pset"`` or ``"qto"``.
    """
    ifc_class: str | None = None
    if ":" in ifc_source:
        ifc_class, rest = ifc_source.split(":", 1)
    else:
        rest = ifc_source

    if "." not in rest:
        return ifc_class, rest, "", "pset"

    container, prop = rest.rsplit(".", 1)
    source_type = "qto" if container.startswith("Qto_") else "pset"
    return ifc_class, container, prop, source_type


def _safe_by_type(ifc: Any, ifc_class: str) -> list:
    """Return elements by IFC class; empty list on any error."""
    try:
        return ifc.by_type(ifc_class) or []
    except Exception:  # noqa: BLE001
        return []


def _extract_one(ifc: Any, ifc_source: str, aggregate: str) -> Any:
    """Dispatch to the correct aggregate strategy and return the result."""
    if aggregate == "entity_count":
        ifc_class = ifc_source.strip()
        if not ifc_class:
            return None
        return len(_safe_by_type(ifc, ifc_class))

    ifc_class, container, prop, source_type = _parse_source(ifc_source)
    if not container or not prop:
        _log.debug("custom_field_extractor: unparseable ifc_source %r", ifc_source)
        return None

    if ifc_class:
        elements = _safe_by_type(ifc, ifc_class)
        if not elements:
            return None  # class absent from model → N/A
    else:
        elements = _safe_by_type(ifc, "IfcElement")

    if aggregate == "count":
        return _aggregate_count(elements, container, prop, source_type)
    if aggregate == "sum":
        return _aggregate_sum(elements, container, prop, source_type)
    if aggregate == "first":
        return _aggregate_first(elements, container, prop, source_type)

    _log.debug("custom_field_extractor: unknown aggregate %r, falling back to count", aggregate)
    return _aggregate_count(elements, container, prop, source_type)


def _aggregate_count(elements: list, container: str, prop: str, source_type: str) -> int:
    """Count elements that have a non-null value for ``container.prop``."""
    return sum(1 for el in elements if _element_has_value(el, container, prop, source_type))


def _aggregate_sum(
    elements: list, container: str, prop: str, source_type: str
) -> float | None:
    """Sum numeric values for ``container.prop`` across all elements."""
    total = 0.0
    found = False
    for el in elements:
        val = _element_numeric_value(el, container, prop, source_type)
        if val is not None:
            total += val
            found = True
    return round(total, 4) if found else None


def _aggregate_first(elements: list, container: str, prop: str, source_type: str) -> Any:
    """Return the first non-null value found for ``container.prop``."""
    for el in elements:
        val = _element_raw_value(el, container, prop, source_type)
        if val is not None:
            return val
    return None


def _element_has_value(element: Any, container: str, prop: str, source_type: str) -> bool:
    """True when the element has a non-null value in the named Pset/Qto."""
    for rel in (getattr(element, "IsDefinedBy", []) or []):
        if not rel.is_a("IfcRelDefinesByProperties"):
            continue
        pdef = rel.RelatingPropertyDefinition

        if source_type == "pset" and pdef.is_a("IfcPropertySet"):
            if getattr(pdef, "Name", "") != container:
                continue
            for p in (getattr(pdef, "Properties", []) or []):
                if getattr(p, "Name", "") != prop:
                    continue
                if p.is_a("IfcPropertySingleValue"):
                    return getattr(p, "NominalValue", None) is not None
                return True  # enumerated / bounded / list — presence counts

        elif source_type == "qto" and pdef.is_a("IfcElementQuantity"):
            if getattr(pdef, "Name", "") != container:
                continue
            for q in (getattr(pdef, "Quantities", []) or []):
                if getattr(q, "Name", "") != prop:
                    continue
                for attr in ("LengthValue", "AreaValue", "VolumeValue",
                             "WeightValue", "CountValue", "TimeValue"):
                    if getattr(q, attr, None) is not None:
                        return True
    return False


def _element_numeric_value(
    element: Any, container: str, prop: str, source_type: str
) -> float | None:
    """Return the numeric value of ``container.prop`` for this element, or None."""
    for rel in (getattr(element, "IsDefinedBy", []) or []):
        if not rel.is_a("IfcRelDefinesByProperties"):
            continue
        pdef = rel.RelatingPropertyDefinition

        if source_type == "pset" and pdef.is_a("IfcPropertySet"):
            if getattr(pdef, "Name", "") != container:
                continue
            for p in (getattr(pdef, "Properties", []) or []):
                if getattr(p, "Name", "") != prop:
                    continue
                if p.is_a("IfcPropertySingleValue"):
                    nv = getattr(p, "NominalValue", None)
                    if nv is not None:
                        try:
                            return float(nv.wrappedValue)
                        except (AttributeError, TypeError, ValueError):
                            return None

        elif source_type == "qto" and pdef.is_a("IfcElementQuantity"):
            if getattr(pdef, "Name", "") != container:
                continue
            for q in (getattr(pdef, "Quantities", []) or []):
                if getattr(q, "Name", "") != prop:
                    continue
                for attr in ("LengthValue", "AreaValue", "VolumeValue",
                             "WeightValue", "CountValue", "TimeValue"):
                    v = getattr(q, attr, None)
                    if v is not None:
                        try:
                            return float(v)
                        except (TypeError, ValueError):
                            return None
    return None


def _element_raw_value(element: Any, container: str, prop: str, source_type: str) -> Any:
    """Return the raw value of ``container.prop`` for this element, or None."""
    for rel in (getattr(element, "IsDefinedBy", []) or []):
        if not rel.is_a("IfcRelDefinesByProperties"):
            continue
        pdef = rel.RelatingPropertyDefinition

        if source_type == "pset" and pdef.is_a("IfcPropertySet"):
            if getattr(pdef, "Name", "") != container:
                continue
            for p in (getattr(pdef, "Properties", []) or []):
                if getattr(p, "Name", "") != prop:
                    continue
                if p.is_a("IfcPropertySingleValue"):
                    nv = getattr(p, "NominalValue", None)
                    if nv is not None:
                        try:
                            return nv.wrappedValue
                        except AttributeError:
                            return str(nv)
                return True  # enumerated / bounded / list — presence

        elif source_type == "qto" and pdef.is_a("IfcElementQuantity"):
            if getattr(pdef, "Name", "") != container:
                continue
            for q in (getattr(pdef, "Quantities", []) or []):
                if getattr(q, "Name", "") != prop:
                    continue
                for attr in ("LengthValue", "AreaValue", "VolumeValue",
                             "WeightValue", "CountValue", "TimeValue"):
                    v = getattr(q, attr, None)
                    if v is not None:
                        return v
    return None
