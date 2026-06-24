"""Extract project-level metadata from an IFC model as GIS-ready metrics."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from geoifcassets.core.models import MetricSource, ModelMetric

if TYPE_CHECKING:
    pass

_log = logging.getLogger("geoifcassets")


def _by_type_safe(ifc: object, type_name: str) -> list:
    """Call ifc.by_type() and return [] when the entity is absent from the schema.

    IFC2X3 does not have IfcCoordinateReferenceSystem, IfcMapConversion, etc.
    IfcOpenShell raises RuntimeError in that case instead of returning an empty list.
    """
    try:
        return ifc.by_type(type_name)  # type: ignore[attr-defined]
    except RuntimeError:
        _log.debug("IFC entity %r not present in schema — skipped", type_name)
        return []


def extract_model_info(ifc_path: str) -> list[ModelMetric]:
    """Return project/building/CRS metadata from an IFC file.

    All returned metrics use MetricSource.CALCULATED because project
    attributes are read directly from IFC entities, not from QuantitySets.
    The ``ifc_`` prefix (no ``calc``) is used because these are authoritative
    IFC header/entity values, not derived quantities.
    """
    import ifcopenshell  # noqa: PLC0415

    try:
        ifc = ifcopenshell.open(ifc_path)
    except Exception as exc:  # noqa: BLE001
        _log.warning("model_info_extractor: cannot open IFC: %s", exc)
        return []

    metrics: list[ModelMetric] = []

    _extract_project_info(ifc, metrics)
    _extract_building_info(ifc, metrics)
    _extract_crs_info(ifc, metrics)
    _extract_schema_info(ifc, metrics)

    _log.info("model_info_extractor: extracted %d metrics from %s", len(metrics), ifc_path)
    return metrics


def _str_or_none(value: object) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def _extract_project_info(ifc: object, metrics: list[ModelMetric]) -> None:
    projects = ifc.by_type("IfcProject")  # type: ignore[attr-defined]
    if not projects:
        return
    project = projects[0]

    name = _str_or_none(getattr(project, "Name", None))
    if name:
        metrics.append(ModelMetric(
            label="Project name",
            suggested_field="ifc_project_name",
            value=name,
            unit="",
            source=MetricSource.CALCULATED,
        ))

    description = _str_or_none(getattr(project, "Description", None))
    if description:
        metrics.append(ModelMetric(
            label="Project description",
            suggested_field="ifc_project_description",
            value=description,
            unit="",
            source=MetricSource.CALCULATED,
        ))

    phase = _str_or_none(getattr(project, "Phase", None))
    if phase:
        metrics.append(ModelMetric(
            label="Project phase",
            suggested_field="ifc_project_phase",
            value=phase,
            unit="",
            source=MetricSource.CALCULATED,
        ))


def _extract_building_info(ifc: object, metrics: list[ModelMetric]) -> None:
    buildings = ifc.by_type("IfcBuilding")  # type: ignore[attr-defined]
    if not buildings:
        return
    building = buildings[0]

    name = _str_or_none(getattr(building, "Name", None))
    if name:
        metrics.append(ModelMetric(
            label="Building name",
            suggested_field="ifc_building_name",
            value=name,
            unit="",
            source=MetricSource.CALCULATED,
        ))

    occupancy = _read_pset_property(ifc, building, "Pset_BuildingCommon", "OccupancyType")
    if occupancy is not None:
        metrics.append(ModelMetric(
            label="Occupancy type",
            suggested_field="ifc_occupancy_type",
            value=str(occupancy),
            unit="",
            source=MetricSource.QTO,
        ))

    gross_area = _read_pset_property(ifc, building, "Pset_BuildingCommon", "GrossPlannedArea")
    if gross_area is not None:
        try:
            metrics.append(ModelMetric(
                label="Gross planned area (Pset_BuildingCommon)",
                suggested_field="ifc_gross_planned_area",
                value=round(float(gross_area), 3),
                unit="m²",
                source=MetricSource.QTO,
            ))
        except (TypeError, ValueError):
            pass


def _extract_crs_info(ifc: object, metrics: list[ModelMetric]) -> None:
    crs_entities = ifc.by_type("IfcCoordinateReferenceSystem")  # type: ignore[attr-defined]
    if not crs_entities:
        return
    crs = crs_entities[0]

    crs_name = _str_or_none(getattr(crs, "Name", None))
    if not crs_name:
        return

    epsg = _parse_epsg(crs_name)
    display = f"EPSG:{epsg}" if epsg else crs_name
    metrics.append(ModelMetric(
        label="Coordinate reference system",
        suggested_field="ifc_crs",
        value=display,
        unit="",
        source=MetricSource.CALCULATED,
    ))


def _extract_schema_info(ifc: object, metrics: list[ModelMetric]) -> None:
    schema = getattr(ifc, "schema", None)
    if schema:
        metrics.append(ModelMetric(
            label="IFC schema",
            suggested_field="ifc_schema",
            value=str(schema),
            unit="",
            source=MetricSource.CALCULATED,
        ))


def _read_pset_property(
    ifc: object,
    element: object,
    pset_name: str,
    property_name: str,
) -> object:
    """Return the value of a named property inside a named PropertySet, or None."""
    rels = getattr(element, "IsDefinedBy", []) or []
    for rel in rels:
        if not rel.is_a("IfcRelDefinesByProperties"):
            continue
        pdef = rel.RelatingPropertyDefinition
        if not pdef.is_a("IfcPropertySet"):
            continue
        if pdef.Name != pset_name:
            continue
        for prop in pdef.HasProperties:
            if prop.Name == property_name:
                return getattr(prop, "NominalValue", None) and getattr(
                    prop.NominalValue, "wrappedValue", prop.NominalValue
                )
    return None


def _parse_epsg(name: str) -> str | None:
    match = re.search(r"\b(\d{4,6})\b", name)
    return match.group(1) if match else None
