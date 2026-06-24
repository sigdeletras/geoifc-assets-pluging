"""IFC footprint extraction with georeferencing via IfcMapConversion."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

_log = logging.getLogger("geoifcassets")


@dataclass(frozen=True)
class GeorefInfo:
    """Georeferencing parameters extracted from IfcMapConversion + IfcCoordinateReferenceSystem."""

    eastings: float
    northings: float
    orthogonal_height: float
    x_axis_abscissa: float   # cos(rotation angle toward CRS north)
    x_axis_ordinate: float   # sin(rotation angle toward CRS north)
    scale: float
    crs_name: str            # raw Name from IfcCoordinateReferenceSystem
    epsg: str | None         # digits only, e.g. "25830", or None if not parseable


@dataclass(frozen=True)
class StoreyFootprint:
    """2D footprint polygon of an IfcBuildingStorey in real-world CRS coordinates."""

    wkt: str            # WKT polygon or multipolygon in CRS coordinates
    crs_auth_id: str    # authority:code string, e.g. "EPSG:25830"
    storey_name: str
    element_count: int  # number of source elements with valid geometry
    used_fallback: bool # True when no IfcSlab found and all elements were used


class FootprintExtractError(Exception):
    """Raised when footprint extraction cannot proceed."""


def diagnose_georef(ifc_path: str) -> str:
    """Return a human-readable diagnostic of the georef entities present in an IFC file.

    Used to explain to the user why georeferencing was not detected, listing
    which entities exist and which are missing or incomplete.
    """
    import ifcopenshell  # noqa: PLC0415

    try:
        ifc = ifcopenshell.open(ifc_path)
    except Exception as exc:  # noqa: BLE001
        return f"Cannot open IFC file: {exc}"

    lines: list[str] = []

    try:
        conversions = ifc.by_type("IfcMapConversion")
    except RuntimeError:
        conversions = []
    if conversions:
        conv = conversions[0]
        e = getattr(conv, "Eastings", None)
        n = getattr(conv, "Northings", None)
        lines.append(f"IfcMapConversion found — Eastings={e}, Northings={n}")
    else:
        lines.append("IfcMapConversion: NOT FOUND")

    try:
        crss = ifc.by_type("IfcCoordinateReferenceSystem")
    except RuntimeError:
        crss = []
    if crss:
        crs_name = getattr(crss[0], "Name", None) or ""
        entity_type = crss[0].is_a()
        if crs_name:
            lines.append(f"{entity_type} found — Name='{crs_name}'")
        else:
            lines.append(f"{entity_type} found — Name is EMPTY (required)")
    else:
        lines.append("IfcCoordinateReferenceSystem / IfcProjectedCRS: NOT FOUND")

    sites = ifc.by_type("IfcSite")
    if sites:
        site = sites[0]
        lat = getattr(site, "RefLatitude", None)
        lon = getattr(site, "RefLongitude", None)
        if lat and lon:
            lines.append(
                "IfcSite has RefLatitude/RefLongitude (IFC2x3 style — "
                "not sufficient for footprint generation)"
            )

    return " | ".join(lines)


def detect_georef(ifc_path: str) -> GeorefInfo | None:
    """Return georef info from IfcMapConversion + IfcCoordinateReferenceSystem, or None.

    Returns None when either entity is absent or the CRS name is empty.
    Logs the reason at INFO/WARNING level but never raises.
    """
    import ifcopenshell  # noqa: PLC0415

    try:
        ifc = ifcopenshell.open(ifc_path)
    except Exception as exc:  # noqa: BLE001
        _log.error("Cannot open IFC for georef detection: %s", exc)
        return None

    try:
        conversions = ifc.by_type("IfcMapConversion")
    except RuntimeError:
        _log.info("IfcMapConversion not in schema %s: %s", ifc.schema, ifc_path)
        return None
    if not conversions:
        _log.info("No IfcMapConversion found in: %s", ifc_path)
        return None

    conv = conversions[0]

    try:
        crss = ifc.by_type("IfcCoordinateReferenceSystem")
    except RuntimeError:
        _log.info("IfcCoordinateReferenceSystem not in schema %s: %s", ifc.schema, ifc_path)
        return None
    if not crss:
        _log.info("No IfcCoordinateReferenceSystem found in: %s", ifc_path)
        return None

    crs_name: str = getattr(crss[0], "Name", None) or ""
    if not crs_name:
        _log.warning("IfcCoordinateReferenceSystem.Name is empty in: %s", ifc_path)
        return None

    def _f(attr: str, default: float) -> float:
        return float(getattr(conv, attr, None) or default)

    georef = GeorefInfo(
        eastings=_f("Eastings", 0.0),
        northings=_f("Northings", 0.0),
        orthogonal_height=_f("OrthogonalHeight", 0.0),
        x_axis_abscissa=_f("XAxisAbscissa", 1.0),
        x_axis_ordinate=_f("XAxisOrdinate", 0.0),
        scale=_f("Scale", 1.0),
        crs_name=crs_name,
        epsg=_parse_epsg(crs_name),
    )

    _log.info(
        "Georef detected: crs=%s epsg=%s E=%.2f N=%.2f scale=%.6f",
        crs_name,
        georef.epsg,
        georef.eastings,
        georef.northings,
        georef.scale,
    )
    return georef


def extract_storey_footprint(
    ifc_path: str,
    storey_express_id: int,
    storey_name: str,
    georef: GeorefInfo,
) -> StoreyFootprint:
    """Extract 2D footprint of an IfcBuildingStorey in real-world CRS coordinates.

    Uses IfcSlab elements as primary source; falls back to all contained elements
    when no IfcSlab is found. Geometry per element is the convex hull of its vertices
    projected to the XY plane; all per-element hulls are merged via unary_union.

    Raises FootprintExtractError when extraction cannot produce a valid polygon.
    """
    import ifcopenshell  # noqa: PLC0415
    import ifcopenshell.geom  # noqa: PLC0415

    try:
        from shapely.geometry import Polygon  # noqa: PLC0415
        from shapely.ops import unary_union  # noqa: PLC0415
    except ImportError as exc:
        raise FootprintExtractError(f"shapely unavailable: {exc}") from exc

    try:
        ifc = ifcopenshell.open(ifc_path)
    except Exception as exc:  # noqa: BLE001
        raise FootprintExtractError(f"Cannot open IFC file: {exc}") from exc

    storey = ifc.by_id(storey_express_id)
    if storey is None:
        raise FootprintExtractError(
            f"IfcBuildingStorey #{storey_express_id} not found in {ifc_path}"
        )

    all_elements = _contained_elements(ifc, storey)
    slabs = [e for e in all_elements if e.is_a("IfcSlab")]
    used_fallback = False

    if not slabs:
        _log.warning(
            "No IfcSlab in storey '%s' (#%d) — using all %d elements as fallback",
            storey_name,
            storey_express_id,
            len(all_elements),
        )
        slabs = all_elements
        used_fallback = True

    if not slabs:
        raise FootprintExtractError(
            f"Storey '{storey_name}' has no elements to extract geometry from."
        )

    settings = ifcopenshell.geom.settings()
    settings.set(settings.USE_WORLD_COORDS, True)

    polygons: list = []
    for element in slabs:
        try:
            shape = ifcopenshell.geom.create_shape(settings, element)
            verts = shape.geometry.verts  # flat [x, y, z, x, y, z, ...]
            local_pts = [(verts[i], verts[i + 1]) for i in range(0, len(verts) - 2, 3)]
            if len(local_pts) < 3:
                continue
            world_pts = [_local_to_world(x, y, georef) for x, y in local_pts]
            hull = Polygon(world_pts).convex_hull
            if hull.is_valid and not hull.is_empty and hull.area > 0:
                polygons.append(hull)
        except Exception as exc:  # noqa: BLE001
            _log.debug("Geometry skipped for element #%d: %s", element.id(), exc)

    if not polygons:
        raise FootprintExtractError(
            f"No valid geometry could be extracted from storey '{storey_name}'."
        )

    merged = unary_union(polygons)
    if merged.is_empty:
        raise FootprintExtractError(
            f"Merged geometry is empty for storey '{storey_name}'."
        )

    crs_auth = f"EPSG:{georef.epsg}" if georef.epsg else georef.crs_name

    _log.info(
        "Footprint extracted: storey='%s' source_elements=%d valid_polygons=%d crs=%s",
        storey_name,
        len(slabs),
        len(polygons),
        crs_auth,
    )

    return StoreyFootprint(
        wkt=merged.wkt,
        crs_auth_id=crs_auth,
        storey_name=storey_name,
        element_count=len(polygons),
        used_fallback=used_fallback,
    )


def _contained_elements(ifc: object, storey: object) -> list:
    """Return elements directly contained in a storey via IfcRelContainedInSpatialStructure."""
    elements: list = []
    for rel in ifc.by_type("IfcRelContainedInSpatialStructure"):  # type: ignore[union-attr]
        if rel.RelatingStructure == storey:
            elements.extend(rel.RelatedElements)
    return elements


def _local_to_world(x: float, y: float, georef: GeorefInfo) -> tuple[float, float]:
    """Apply IfcMapConversion rotation + scale + offset to local IFC XY coordinates."""
    cos_a = georef.x_axis_abscissa
    sin_a = georef.x_axis_ordinate
    x_rot = (x * cos_a - y * sin_a) * georef.scale
    y_rot = (x * sin_a + y * cos_a) * georef.scale
    return georef.eastings + x_rot, georef.northings + y_rot


def _parse_epsg(crs_name: str) -> str | None:
    """Extract EPSG numeric code from strings like 'EPSG:25830' or 'urn:ogc:def:crs:EPSG::25830'."""
    match = re.search(r"EPSG[:\s]+(\d{4,6})", crs_name, re.IGNORECASE)
    return match.group(1) if match else None
