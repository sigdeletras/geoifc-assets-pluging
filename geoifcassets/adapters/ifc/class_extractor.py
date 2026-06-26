"""Extract per-class aggregated quantities from an IFC model.

Driven by a list of ``ClassMetricSpec`` from the template, this extractor
generates GIS field names following the ``<prefix>_<metric>`` convention
(e.g. ``wall_count``, ``wall_area``) and returns a dict ready for attribute
writing.

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

from geoifcassets.core.models import ClassMetricSpec, IFCClassDiscovery, MetricSource, ModelMetric

_log = logging.getLogger("geoifcassets")

# Standard quantity names by metric type (searched in order)
_AREA_QTY   = ("GrossArea", "NetArea", "GrossSideArea", "NetSideArea",
                "GrossFloorArea", "NetFloorArea", "GrossFootprintArea", "GrossCeilingArea")
_LENGTH_QTY = ("Length",)
_VOLUME_QTY = ("GrossVolume", "NetVolume")


def extract_class_metrics(
    ifc_path: str,
    specs: list[ClassMetricSpec],
) -> dict[str, Any]:
    """Return {field_name: value} for all enabled class metric specs.

    ``field_name`` follows ``<prefix>_<metric>``  (e.g. ``wall_count``).
    Values are ``None`` when the quantity is not present in the model.
    """
    import ifcopenshell  # noqa: PLC0415

    try:
        ifc = ifcopenshell.open(ifc_path)
    except Exception as exc:  # noqa: BLE001
        _log.warning("class_extractor: cannot open %s: %s", ifc_path, exc)
        return {}

    result: dict[str, Any] = {}
    for spec in specs:
        if not spec.enabled:
            continue
        _extract_spec(ifc, spec, result)

    _log.info(
        "class_extractor: extracted %d class metric fields from %s",
        len(result),
        ifc_path,
    )
    return result


def extract_class_metrics_as_model_metrics(
    ifc_path: str,
    specs: list[ClassMetricSpec],
) -> list[ModelMetric]:
    """Same extraction, returned as ``ModelMetric`` list for the dock table."""
    raw = extract_class_metrics(ifc_path, specs)
    metrics: list[ModelMetric] = []
    for spec in specs:
        if not spec.enabled:
            continue
        for metric in spec.metrics:
            field = f"{spec.prefix}_{metric}"
            value = raw.get(field)
            unit = _unit_for(metric)
            source = MetricSource.QTO if value is not None else MetricSource.CALCULATED
            metrics.append(ModelMetric(
                label=f"{spec.ifc_class} — {metric}",
                suggested_field=field,
                value=value,
                unit=unit,
                source=source,
            ))
    return metrics


def probe_available_metrics(ifc_path: str, specs: list[ClassMetricSpec]) -> dict[str, set[str]]:
    """Return {ifc_class: set_of_available_metrics} for UI column state.

    A metric is "available" when at least one element of the class has a
    matching QtoSet entry.  "count" is always available.
    """
    import ifcopenshell  # noqa: PLC0415

    try:
        ifc = ifcopenshell.open(ifc_path)
    except Exception as exc:  # noqa: BLE001
        _log.warning("class_extractor.probe: cannot open %s: %s", ifc_path, exc)
        return {}

    result: dict[str, set[str]] = {}
    for spec in specs:
        if not spec.enabled:
            continue
        available: set[str] = set()
        elements = ifc.by_type(spec.ifc_class)
        if elements:
            available.add("count")
        for metric in ("length", "area", "volume"):
            if metric not in spec.metrics:
                continue
            qty_names = _qty_names_for(metric)
            for element in elements:
                if _find_quantity(element, qty_names, _qty_type_name(metric)) is not None:
                    available.add(metric)
                    break
        result[spec.ifc_class] = available

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


def _extract_spec(ifc: Any, spec: ClassMetricSpec, result: dict[str, Any]) -> None:
    elements = ifc.by_type(spec.ifc_class)
    count = len(elements)

    if "count" in spec.metrics:
        result[f"{spec.prefix}_count"] = count if count > 0 else None

    if count == 0:
        for metric in ("length", "area", "volume"):
            if metric in spec.metrics:
                result[f"{spec.prefix}_{metric}"] = None
        return

    for metric in ("length", "area", "volume"):
        if metric not in spec.metrics:
            continue
        qty_names = _qty_names_for(metric)
        qty_type  = _qty_type_name(metric)
        total = 0.0
        found = False
        for element in elements:
            val = _find_quantity(element, qty_names, qty_type)
            if val is not None:
                total += val
                found = True
        result[f"{spec.prefix}_{metric}"] = round(total, 3) if found else None
        if not found:
            _log.debug(
                "class_extractor: no %s QtoSet found for %s (%d elements)",
                metric, spec.ifc_class, count,
            )


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


def _unit_for(metric: str) -> str:
    return {"count": "count", "length": "m", "area": "m²", "volume": "m³"}.get(metric, "")
