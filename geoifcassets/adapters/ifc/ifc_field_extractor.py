"""Extract scalar IFC fields by name from a local IFC file.

Each field name maps to a dedicated extraction method via the ``_field_*``
naming convention.  Unknown field names return ``None`` without raising.

The extractor is designed to be called once per IFC file with a list of
requested field names; computed intermediate values (entity counts, header
values) are cached so they are computed at most once per call.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
from pathlib import Path
from typing import Any

_log = logging.getLogger("geoifcassets")

_NOT_EXTRACTABLE_MVP: frozenset[str] = frozenset({
    # Geometry — require full mesh processing (expensive, out of scope for MVP)
    "bbox_width", "bbox_depth", "bbox_height",
    "footprint_area", "total_length",
    # Heuristic — require corpus-level calibration
    "detected_domain", "detected_discipline",
    "dominant_material",
    # Composite scores — require all area metrics first
    "bim_completeness_score", "complexity_index",
    "objects_per_m2", "volume_per_m2",
})


def extract_fields(ifc_path: str, field_names: list[str]) -> dict[str, Any]:
    """Return a dict mapping each requested field name to its extracted value.

    Values are ``None`` when the field is not supported, not found in the model,
    or listed in ``_NOT_EXTRACTABLE_MVP``.
    """
    import ifcopenshell  # noqa: PLC0415

    try:
        ifc = ifcopenshell.open(ifc_path)
    except Exception as exc:  # noqa: BLE001
        _log.warning("ifc_field_extractor: cannot open %s: %s", ifc_path, exc)
        return {name: None for name in field_names}

    extractor = _IfcFieldExtractor(ifc, ifc_path)
    result: dict[str, Any] = {}
    for name in field_names:
        if name in _NOT_EXTRACTABLE_MVP:
            result[name] = None
            continue
        try:
            result[name] = extractor.get(name)
        except Exception as exc:  # noqa: BLE001
            _log.debug("ifc_field_extractor: field %r failed: %s", name, exc)
            result[name] = None

    _log.info(
        "ifc_field_extractor: extracted %d/%d fields from %s",
        sum(1 for v in result.values() if v is not None),
        len(field_names),
        ifc_path,
    )
    return result


class _IfcFieldExtractor:
    def __init__(self, ifc: Any, ifc_path: str) -> None:
        self._ifc = ifc
        self._ifc_path = ifc_path
        self._cache: dict[str, Any] = {}

    def get(self, field_name: str) -> Any:
        if field_name not in self._cache:
            method = getattr(self, f"_field_{field_name}", None)
            self._cache[field_name] = method() if method is not None else None
        return self._cache[field_name]

    # ── File ─────────────────────────────────────────────────────────────────

    def _field_file_name(self) -> str:
        return Path(self._ifc_path).name

    def _field_file_path(self) -> str:
        return self._ifc_path

    def _field_document_format(self) -> str:
        return "IFC"

    def _field_file_extension(self) -> str:
        return Path(self._ifc_path).suffix.lower()

    def _field_file_size_mb(self) -> float | None:
        try:
            return round(os.path.getsize(self._ifc_path) / (1024 * 1024), 3)
        except OSError:
            return None

    def _field_file_hash(self) -> str | None:
        try:
            with open(self._ifc_path, "rb") as f:  # noqa: PTH123
                chunk = f.read(65536)  # first 64 KB — quick hash, not full-file
            return hashlib.md5(chunk).hexdigest()  # noqa: S324
        except OSError:
            return None

    def _field_file_created(self) -> str | None:
        try:
            t = os.path.getctime(self._ifc_path)
            return _ts_to_iso(t)
        except OSError:
            return None

    def _field_file_modified(self) -> str | None:
        try:
            t = os.path.getmtime(self._ifc_path)
            return _ts_to_iso(t)
        except OSError:
            return None

    # ── IFC Header ───────────────────────────────────────────────────────────

    def _field_ifc_version(self) -> str | None:
        return _str_or_none(getattr(self._ifc, "schema", None))

    def _field_schema_identifier(self) -> str | None:
        try:
            schemas = self._ifc.header.file_schema.schemas
            if schemas:
                return str(schemas[0])
        except AttributeError:
            pass
        return self._field_ifc_version()

    def _field_file_description(self) -> str | None:
        try:
            desc = self._ifc.header.file_description.description
            if desc:
                return str(desc[0]) if isinstance(desc, (list, tuple)) else str(desc)
        except AttributeError:
            pass
        return None

    def _field_file_timestamp(self) -> str | None:
        try:
            return _str_or_none(self._ifc.header.file_name.time_stamp)
        except AttributeError:
            return None

    def _field_author(self) -> str | None:
        try:
            authors = self._ifc.header.file_name.author
            if authors:
                return str(authors[0]) if isinstance(authors, (list, tuple)) else str(authors)
        except AttributeError:
            pass
        return None

    def _field_organization(self) -> str | None:
        try:
            orgs = self._ifc.header.file_name.organization
            if orgs:
                return str(orgs[0]) if isinstance(orgs, (list, tuple)) else str(orgs)
        except AttributeError:
            pass
        return None

    def _field_originating_system(self) -> str | None:
        try:
            return _str_or_none(self._ifc.header.file_name.originating_system)
        except AttributeError:
            return None

    def _field_preprocessor_version(self) -> str | None:
        try:
            return _str_or_none(self._ifc.header.file_name.preprocessor_version)
        except AttributeError:
            return None

    def _field_authorization(self) -> str | None:
        try:
            return _str_or_none(self._ifc.header.file_name.authorization)
        except AttributeError:
            return None

    # ── Project ──────────────────────────────────────────────────────────────

    def _project(self) -> Any | None:
        projects = self._ifc.by_type("IfcProject")
        return projects[0] if projects else None

    def _field_project_name(self) -> str | None:
        p = self._project()
        return _str_or_none(getattr(p, "Name", None)) if p else None

    def _field_project_globalid(self) -> str | None:
        p = self._project()
        return _str_or_none(getattr(p, "GlobalId", None)) if p else None

    def _field_project_description(self) -> str | None:
        p = self._project()
        return _str_or_none(getattr(p, "Description", None)) if p else None

    def _field_project_phase(self) -> str | None:
        p = self._project()
        return _str_or_none(getattr(p, "Phase", None)) if p else None

    # ── Location ─────────────────────────────────────────────────────────────

    def _site(self) -> Any | None:
        sites = self._ifc.by_type("IfcSite")
        return sites[0] if sites else None

    def _field_site_name(self) -> str | None:
        s = self._site()
        return _str_or_none(getattr(s, "Name", None)) if s else None

    def _field_building_name(self) -> str | None:
        buildings = self._ifc.by_type("IfcBuilding")
        if buildings:
            return _str_or_none(getattr(buildings[0], "Name", None))
        return None

    def _field_epsg(self) -> str | None:
        for crs in _by_type_safe(self._ifc, "IfcCoordinateReferenceSystem"):
            name = _str_or_none(getattr(crs, "Name", None))
            if name:
                m = re.search(r"\b(\d{4,6})\b", name)
                if m:
                    return m.group(1)
        return None

    def _field_crs_name(self) -> str | None:
        for crs in _by_type_safe(self._ifc, "IfcCoordinateReferenceSystem"):
            return _str_or_none(getattr(crs, "Name", None))
        return None

    def _field_latitude(self) -> float | None:
        s = self._site()
        if s is None:
            return None
        ref = getattr(s, "RefLatitude", None)
        return _dms_to_decimal(ref)

    def _field_longitude(self) -> float | None:
        s = self._site()
        if s is None:
            return None
        ref = getattr(s, "RefLongitude", None)
        return _dms_to_decimal(ref)

    def _map_conversion(self) -> Any | None:
        entities = _by_type_safe(self._ifc, "IfcMapConversion")
        return entities[0] if entities else None

    def _field_easting(self) -> float | None:
        mc = self._map_conversion()
        v = getattr(mc, "Eastings", None) if mc else None
        return float(v) if v is not None else None

    def _field_northing(self) -> float | None:
        mc = self._map_conversion()
        v = getattr(mc, "Northings", None) if mc else None
        return float(v) if v is not None else None

    def _field_elevation(self) -> float | None:
        mc = self._map_conversion()
        v = getattr(mc, "OrthogonalHeight", None) if mc else None
        return float(v) if v is not None else None

    def _field_is_georeferenced(self) -> bool:
        return self._map_conversion() is not None

    # ── Spatial Structure ─────────────────────────────────────────────────────

    def _count(self, ifc_type: str) -> int:
        return len(self._ifc.by_type(ifc_type))

    def _field_site_count(self) -> int:
        return self._count("IfcSite")

    def _field_building_count(self) -> int:
        return self._count("IfcBuilding")

    def _field_storey_count(self) -> int:
        return self._count("IfcBuildingStorey")

    def _field_space_count(self) -> int:
        return self._count("IfcSpace")

    def _field_zone_count(self) -> int:
        return len(_by_type_safe(self._ifc, "IfcZone"))

    def _field_system_count(self) -> int:
        return len(_by_type_safe(self._ifc, "IfcSystem"))

    # ── Model Statistics ──────────────────────────────────────────────────────

    def _field_total_entities(self) -> int:
        try:
            return len(self._ifc)  # ifcopenshell File.__len__
        except TypeError:
            return sum(1 for _ in self._ifc)

    def _field_total_objects(self) -> int:
        return self._count("IfcObject")

    def _field_total_physical_elements(self) -> int:
        return self._count("IfcElement")

    def _field_distinct_ifc_classes(self) -> int:
        try:
            types = {e.is_a() for e in self._ifc}
            return len(types)
        except Exception:  # noqa: BLE001
            return 0

    # ── Geometry ──────────────────────────────────────────────────────────────

    def _field_gross_floor_area(self) -> float | None:
        # IfcSpace carries GrossFloorArea in Qto_SpaceBaseQuantities (most common)
        result = _sum_area_from_qto(self._ifc, "IfcSpace", ("GrossFloorArea", "GrossArea"))
        if result is None:
            result = _sum_area_from_qto(
                self._ifc, "IfcBuildingStorey",
                ("GrossFloorArea", "GrossArea", "NetFloorArea", "NetArea"),
            )
        return result

    def _field_net_floor_area(self) -> float | None:
        result = _sum_area_from_qto(self._ifc, "IfcSpace", ("NetFloorArea", "NetArea"))
        if result is None:
            result = _sum_area_from_qto(
                self._ifc, "IfcBuildingStorey", ("NetFloorArea", "NetArea"),
            )
        return result

    def _field_gross_volume(self) -> float | None:
        return _sum_volume_from_qto(self._ifc, "IfcSpace", ("GrossVolume",))

    def _field_net_volume(self) -> float | None:
        return _sum_volume_from_qto(self._ifc, "IfcSpace", ("NetVolume",))

    # ── Materials ─────────────────────────────────────────────────────────────

    def _field_material_count(self) -> int:
        return self._count("IfcMaterial")

    # ── BIM Quality ───────────────────────────────────────────────────────────

    def _field_propertyset_count(self) -> int:
        return self._count("IfcPropertySet")

    def _field_quantityset_count(self) -> int:
        return self._count("IfcElementQuantity")

    def _field_classification_count(self) -> int:
        return self._count("IfcClassification")

    def _field_has_geometry(self) -> bool:
        for element in self._ifc.by_type("IfcElement")[:100]:  # sample
            if getattr(element, "Representation", None):
                return True
        return False

    def _field_has_quantities(self) -> bool:
        return self._count("IfcElementQuantity") > 0

    def _field_has_property_sets(self) -> bool:
        return self._count("IfcPropertySet") > 0

    def _field_has_materials(self) -> bool:
        return self._count("IfcMaterial") > 0

    def _field_has_classifications(self) -> bool:
        return self._count("IfcClassification") > 0

    def _field_has_spatial_structure(self) -> bool:
        return self._count("IfcBuildingStorey") > 0 or self._count("IfcSpace") > 0

    def _field_geometry_completion_pct(self) -> float | None:
        elements = self._ifc.by_type("IfcElement")
        if not elements:
            return None
        with_geom = sum(1 for e in elements if getattr(e, "Representation", None))
        return round(with_geom / len(elements) * 100, 1)

    def _field_property_completion_pct(self) -> float | None:
        elements = self._ifc.by_type("IfcElement")
        if not elements:
            return None
        with_props = sum(1 for e in elements if getattr(e, "IsDefinedBy", None))
        return round(with_props / len(elements) * 100, 1)

    def _field_quantity_completion_pct(self) -> float | None:
        elements = self._ifc.by_type("IfcElement")
        if not elements:
            return None

        def _has_qto(element: Any) -> bool:
            for rel in (getattr(element, "IsDefinedBy", []) or []):
                if rel.is_a("IfcRelDefinesByProperties"):
                    pdef = rel.RelatingPropertyDefinition
                    if pdef.is_a("IfcElementQuantity"):
                        return True
            return False

        with_qto = sum(1 for e in elements if _has_qto(e))
        return round(with_qto / len(elements) * 100, 1)

    # ── Indicators ────────────────────────────────────────────────────────────

    def _field_objects_per_storey(self) -> float | None:
        storeys = self.get("storey_count")
        objects = self.get("total_objects")
        if not storeys or not objects:
            return None
        return round(objects / storeys, 1)

    def _field_objects_per_space(self) -> float | None:
        spaces = self.get("space_count")
        objects = self.get("total_objects")
        if not spaces or not objects:
            return None
        return round(objects / spaces, 1)

    # ── Extraction metadata ───────────────────────────────────────────────────

    def _field_extractor_version(self) -> str:
        return "1.0.0"

    def _field_extraction_datetime(self) -> str:
        import datetime  # noqa: PLC0415
        return datetime.datetime.now(tz=datetime.timezone.utc).isoformat(timespec="seconds")

    def _field_extraction_status(self) -> str:
        return "ok"

    def _field_extraction_error(self) -> str:
        return ""


# ── Helpers ───────────────────────────────────────────────────────────────────


def _str_or_none(value: object) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def _ts_to_iso(timestamp: float) -> str:
    import datetime  # noqa: PLC0415
    return datetime.datetime.fromtimestamp(
        timestamp, tz=datetime.timezone.utc
    ).isoformat(timespec="seconds")


def _dms_to_decimal(dms: Any) -> float | None:
    if not dms:
        return None
    try:
        parts = list(dms)
        d = float(parts[0]) if len(parts) > 0 else 0.0
        m = float(parts[1]) if len(parts) > 1 else 0.0
        s = float(parts[2]) if len(parts) > 2 else 0.0
        ms = float(parts[3]) if len(parts) > 3 else 0.0
        return round(d + m / 60 + s / 3600 + ms / 3_600_000, 8)
    except (TypeError, ValueError, IndexError):
        return None


def _by_type_safe(ifc: Any, type_name: str) -> list:
    try:
        return ifc.by_type(type_name)
    except RuntimeError:
        return []


def _sum_area_from_qto(
    ifc: Any,
    ifc_type: str,
    qty_names: tuple[str, ...],
) -> float | None:
    elements = ifc.by_type(ifc_type)
    if not elements:
        return None
    total = 0.0
    found = False
    for element in elements:
        for rel in (getattr(element, "IsDefinedBy", []) or []):
            if not rel.is_a("IfcRelDefinesByProperties"):
                continue
            pdef = rel.RelatingPropertyDefinition
            if not pdef.is_a("IfcElementQuantity"):
                continue
            for qty in pdef.Quantities:
                if qty.Name in qty_names and qty.is_a("IfcQuantityArea"):
                    try:
                        total += float(qty.AreaValue)
                        found = True
                    except (AttributeError, TypeError, ValueError):
                        pass
    return round(total, 3) if found else None


def _sum_volume_from_qto(
    ifc: Any,
    ifc_type: str,
    qty_names: tuple[str, ...],
) -> float | None:
    elements = ifc.by_type(ifc_type)
    if not elements:
        return None
    total = 0.0
    found = False
    for element in elements:
        for rel in (getattr(element, "IsDefinedBy", []) or []):
            if not rel.is_a("IfcRelDefinesByProperties"):
                continue
            pdef = rel.RelatingPropertyDefinition
            if not pdef.is_a("IfcElementQuantity"):
                continue
            for qty in pdef.Quantities:
                if qty.Name in qty_names and qty.is_a("IfcQuantityVolume"):
                    try:
                        total += float(qty.VolumeValue)
                        found = True
                    except (AttributeError, TypeError, ValueError):
                        pass
    return round(total, 3) if found else None
