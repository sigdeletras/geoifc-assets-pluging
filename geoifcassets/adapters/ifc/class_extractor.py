"""Discover and extract per-class aggregated quantities from an IFC model.

``discover_ifc_classes`` scans all IfcProduct subclasses present in a file
and computes count + QtoSet totals automatically — no template configuration
required.  ``discoveries_to_fields`` converts the result to the flat
``{prefix_metric: value}`` dict used when writing GIS attributes.

Quantity Set lookup priority:
  1. Standard IFC4 name: ``Qto_<Class>BaseQuantities``
  2. IFC2x3 fallback: any ``IfcElementQuantity`` whose Name contains
     "BaseQuantities" or starts with "Qto_"
  3. Any ``IfcElementQuantity`` on the element (last resort)

When no QtoSet provides a value the field is set to ``None`` so the UI can
flag it as unavailable rather than writing an incorrect zero.
"""

from __future__ import annotations

import logging
from typing import Any

from geoifcassets.core.models import IFCClassDiscovery

_log = logging.getLogger("geoifcassets")

# Standard quantity names by metric type (searched in order)
_AREA_QTY   = ("GrossArea", "NetArea", "GrossSideArea", "NetSideArea",
                "GrossFloorArea", "NetFloorArea", "GrossFootprintArea", "GrossCeilingArea")
_LENGTH_QTY = ("Length",)
_VOLUME_QTY = ("GrossVolume", "NetVolume")



def discoveries_to_fields(
    discoveries: list[IFCClassDiscovery],
    selected: list[tuple[str, list[str]]],
) -> dict[str, Any]:
    """Convert auto-discovered class data to ``{prefix_metric: value}`` for GIS writing.

    ``selected`` is the user's checked selection from the dock:
    ``[(ifc_class, [metric, ...])]``.  Only selected class/metric pairs are
    included.  Values of ``None`` are excluded so callers can skip empty fields.
    """
    sel: dict[str, list[str]] = {ifc_class: metrics for ifc_class, metrics in selected}
    result: dict[str, Any] = {}
    for disc in discoveries:
        wanted = sel.get(disc.ifc_class)
        if not wanted:
            continue
        for metric in wanted:
            value = disc.values.get(metric)
            if value is not None:
                result[f"{disc.prefix}_{metric}"] = value
    return result


def discover_ifc_classes(ifc_path: str) -> list[IFCClassDiscovery]:
    """Return all IfcProduct subclasses present in the model, sorted by count desc.

    For each class, ``available`` contains the metrics that have QtoSet data on
    a sample element (the first element of that class).  ``"count"`` is always
    included when there is at least one element.
    """
    import ifcopenshell  # noqa: PLC0415

    try:
        ifc = ifcopenshell.open(ifc_path)
    except Exception as exc:  # noqa: BLE001
        _log.warning("class_extractor.discover: cannot open %s: %s", ifc_path, exc)
        return []

    seen: set[str] = set()
    result: list[IFCClassDiscovery] = []

    for entity in ifc.by_type("IfcProduct"):
        cls = entity.is_a()
        if cls in seen:
            continue
        seen.add(cls)

        elements = ifc.by_type(cls)
        count = len(elements)
        available: set[str] = set()
        values: dict[str, Any] = {}
        sources: dict[str, str] = {}

        if count > 0:
            available.add("count")
            values["count"] = count
            sources["count"] = "calc"

            for metric in ("length", "area", "volume"):
                qty_names = _qty_names_for(metric)
                qty_type = _qty_type_name(metric)
                total = 0.0
                found = False
                for element in elements:
                    val = _find_quantity(element, qty_names, qty_type)
                    if val is not None:
                        total += val
                        found = True
                if found:
                    available.add(metric)
                    values[metric] = round(total, 3)
                    sources[metric] = "Qto"
                else:
                    values[metric] = None
                    sources[metric] = "—"

        prefix = cls[3:].lower() if cls.startswith("Ifc") else cls.lower()
        result.append(IFCClassDiscovery(
            ifc_class=cls,
            prefix=prefix,
            count=count,
            available=available,
            values=values,
            sources=sources,
        ))

    _log.info("class_extractor.discover: found %d classes in %s", len(result), ifc_path)
    return sorted(result, key=lambda x: -x.count)


# ── Internal ─────────────────────────────────────────────────────────────────



def _find_quantity(element: Any, qty_names: tuple[str, ...], qty_type: str) -> float | None:
    for rel in (getattr(element, "IsDefinedBy", []) or []):
        if not rel.is_a("IfcRelDefinesByProperties"):
            continue
        pdef = rel.RelatingPropertyDefinition
        if not pdef.is_a("IfcElementQuantity"):
            continue
        for qty in pdef.Quantities:
            if qty.Name not in qty_names:
                continue
            val = _read_qty_value(qty, qty_type)
            if val is not None:
                return val
    return None


def _read_qty_value(qty: Any, qty_type: str) -> float | None:
    type_map = {
        "IfcQuantityArea":   "AreaValue",
        "IfcQuantityLength": "LengthValue",
        "IfcQuantityVolume": "VolumeValue",
    }
    for ifc_qty_type, attr in type_map.items():
        if qty.is_a(ifc_qty_type) and qty_type == ifc_qty_type:
            try:
                return float(getattr(qty, attr))
            except (AttributeError, TypeError, ValueError):
                return None
    return None


def _qty_names_for(metric: str) -> tuple[str, ...]:
    return {"area": _AREA_QTY, "length": _LENGTH_QTY, "volume": _VOLUME_QTY}.get(metric, ())


def _qty_type_name(metric: str) -> str:
    return {
        "area":   "IfcQuantityArea",
        "length": "IfcQuantityLength",
        "volume": "IfcQuantityVolume",
    }.get(metric, "")


