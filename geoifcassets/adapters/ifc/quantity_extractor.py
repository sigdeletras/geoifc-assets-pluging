"""Extract aggregated quantities from an IFC model as GIS-ready metrics.

Element counts are always available.  Area/volume/length metrics are read from
formal QuantitySets (Qto_*) when present; when absent the metric is omitted
and a warning is logged so the caller can inform the user.

Field naming convention:
  ifc_*       — value read from a formal QuantitySet (Qto_*)
  ifc_calc_*  — value derived because the formal QtoSet was absent

MVP scope: model-wide totals only.  Per-storey breakdown is logged but not
returned as metrics (evolutive).
"""

from __future__ import annotations

import logging

from geoifcassets.core.models import MetricSource, ModelMetric

_log = logging.getLogger("geoifcassets")

_ELEMENT_COUNTS: list[tuple[str, str, str]] = [
    ("IfcBuildingStorey", "Storeys",         "ifc_storey_count"),
    ("IfcWall",           "Walls",            "ifc_wall_count"),
    ("IfcDoor",           "Doors",            "ifc_door_count"),
    ("IfcWindow",         "Windows",          "ifc_window_count"),
    ("IfcSpace",          "Spaces / rooms",   "ifc_space_count"),
    ("IfcColumn",         "Columns",          "ifc_column_count"),
    ("IfcBeam",           "Beams",            "ifc_beam_count"),
    ("IfcSlab",           "Slabs",            "ifc_slab_count"),
    ("IfcStair",          "Stairs",           "ifc_stair_count"),
]


def extract_quantities(ifc_path: str) -> list[ModelMetric]:
    """Return aggregated quantity metrics from an IFC file.

    Steps:
    1. Count elements by type (always available).
    2. Attempt to sum area quantities from formal QuantitySets.
       - If QuantitySets are present → MetricSource.QTO, field ``ifc_*``
       - If absent → MetricSource.CALCULATED, field ``ifc_calc_*`` (value from
         a simplified geometric sum if possible, or the metric is omitted)
    """
    import ifcopenshell  # noqa: PLC0415

    try:
        ifc = ifcopenshell.open(ifc_path)
    except Exception as exc:  # noqa: BLE001
        _log.warning("quantity_extractor: cannot open IFC: %s", exc)
        return []

    metrics: list[ModelMetric] = []

    _extract_element_counts(ifc, metrics)
    _extract_floor_areas(ifc, metrics)
    _extract_wall_areas(ifc, metrics)

    _log.info("quantity_extractor: extracted %d metrics from %s", len(metrics), ifc_path)
    return metrics


def _extract_element_counts(ifc: object, metrics: list[ModelMetric]) -> None:
    for ifc_type, label, field in _ELEMENT_COUNTS:
        elements = ifc.by_type(ifc_type)  # type: ignore[attr-defined]
        count = len(elements)
        if count > 0:
            metrics.append(ModelMetric(
                label=f"{label} count",
                suggested_field=field,
                value=count,
                unit="count",
                source=MetricSource.CALCULATED,
            ))


def _extract_floor_areas(ifc: object, metrics: list[ModelMetric]) -> None:
    """Sum GrossFloorArea from IfcBuildingStorey QuantitySets.

    Also logs per-storey breakdown for the user log (not returned as metrics).
    """
    storeys = ifc.by_type("IfcBuildingStorey")  # type: ignore[attr-defined]
    if not storeys:
        return

    total = 0.0
    found_qto = False
    storey_log: list[str] = []

    for storey in sorted(storeys, key=lambda s: getattr(s, "Elevation", 0) or 0):
        area = _read_quantity_area(storey, ("GrossFloorArea", "GrossArea", "NetFloorArea", "NetArea"))
        storey_name = _str_or_none(getattr(storey, "Name", None)) or "—"
        elevation = getattr(storey, "Elevation", None)
        elev_str = f"{elevation:.2f} m" if elevation is not None else "?"
        if area is not None:
            found_qto = True
            total += area
            storey_log.append(f"  {storey_name} ({elev_str}): {area:.2f} m²")
        else:
            storey_log.append(f"  {storey_name} ({elev_str}): area not available in QtoSet")

    if storey_log:
        _log.info("quantity_extractor — floor areas per storey:\n%s", "\n".join(storey_log))

    if found_qto and total > 0:
        metrics.append(ModelMetric(
            label="Gross floor area (sum of storeys)",
            suggested_field="ifc_gross_floor_area",
            value=round(total, 3),
            unit="m²",
            source=MetricSource.QTO,
        ))
    else:
        _log.warning(
            "quantity_extractor: no formal floor area QuantitySets found in %d storeys — "
            "ifc_calc_gross_floor_area not computed (geometry fallback not implemented in MVP)",
            len(storeys),
        )


def _extract_wall_areas(ifc: object, metrics: list[ModelMetric]) -> None:
    """Sum GrossSideArea from IfcWall QuantitySets."""
    walls = ifc.by_type("IfcWall")  # type: ignore[attr-defined]
    if not walls:
        return

    total = 0.0
    found_qto = False

    for wall in walls:
        area = _read_quantity_area(wall, ("GrossSideArea", "NetSideArea", "GrossFootprintArea"))
        if area is not None:
            found_qto = True
            total += area

    if found_qto and total > 0:
        metrics.append(ModelMetric(
            label="Gross wall area (sum of walls)",
            suggested_field="ifc_gross_wall_area",
            value=round(total, 3),
            unit="m²",
            source=MetricSource.QTO,
        ))
    else:
        _log.info(
            "quantity_extractor: no formal wall area QuantitySets found — "
            "ifc_calc_gross_wall_area not computed"
        )


def _read_quantity_area(element: object, qty_names: tuple[str, ...]) -> float | None:
    """Return the first matching area quantity from any QuantitySet on the element."""
    rels = getattr(element, "IsDefinedBy", []) or []
    for rel in rels:
        if not rel.is_a("IfcRelDefinesByProperties"):
            continue
        pdef = rel.RelatingPropertyDefinition
        if not pdef.is_a("IfcElementQuantity"):
            continue
        for qty in pdef.Quantities:
            if qty.Name in qty_names and qty.is_a("IfcQuantityArea"):
                try:
                    return float(qty.AreaValue)
                except (AttributeError, TypeError, ValueError):
                    pass
    return None


def _str_or_none(value: object) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None
