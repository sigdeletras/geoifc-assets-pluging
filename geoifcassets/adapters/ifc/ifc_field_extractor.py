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
    "bbox_width", "bbox_depth", "bbox_height", "footprint_area",
    # Heuristic — require corpus-level calibration
    "detected_domain", "detected_discipline",
})

# Lookup table: asset-level field → candidate (pset_name, property_name) pairs.
# Extractor searches IfcProject / IfcSite / IfcBuilding / IfcFacility entities in order.
_ASSET_PSET_CANDIDATES: dict[str, list[tuple[str, str]]] = {
    "asset_type": [
        ("Pset_BuildingCommon", "OccupancyType"),
        ("Pset_FacilityCommon", "AssetType"),
        ("Pset_AssetCommon", "Category"),
    ],
    "asset_subtype": [
        ("Pset_BuildingCommon", "OccupancyType"),
        ("Pset_FacilityCommon", "SubType"),
        ("Pset_AssetCommon", "Subtype"),
    ],
    "intended_use": [
        ("Pset_BuildingCommon", "IntendedUse"),
        ("Pset_SpaceCommon", "IntendedUse"),
        ("Pset_FacilityCommon", "IntendedUse"),
    ],
    "lifecycle_stage": [
        ("Pset_ProjectCommon", "LifeCyclePhase"),
        ("Pset_BuildingCommon", "ConstructionProjectScope"),
        ("Pset_AssetCommon", "LifeCyclePhase"),
    ],
    "operational_status": [
        ("Pset_BuildingCommon", "OperatingStatus"),
        ("Pset_FacilityCommon", "OperationalStatus"),
        ("Pset_AssetCommon", "OperationalStatus"),
    ],
    "owner": [
        ("Pset_BuildingCommon", "Owner"),
        ("Pset_FacilityCommon", "Owner"),
        ("Pset_AssetCommon", "Owner"),
    ],
    "operator": [
        ("Pset_BuildingCommon", "Operator"),
        ("Pset_FacilityCommon", "Operator"),
        ("Pset_AssetCommon", "Operator"),
    ],
    "maintainer": [
        ("Pset_BuildingCommon", "Maintainer"),
        ("Pset_FacilityCommon", "Maintainer"),
        ("Pset_AssetCommon", "Maintainer"),
    ],
    "asset_identifier": [
        ("Pset_AssetCommon", "AssetIdentifier"),
        ("Pset_BuildingCommon", "Reference"),
        ("Pset_FacilityCommon", "Reference"),
    ],
    "facility_identifier": [
        ("Pset_FacilityCommon", "FacilityIdentifier"),
        ("Pset_BuildingCommon", "BuildingNumber"),
        ("Pset_AssetCommon", "FacilityIdentifier"),
    ],
    "commissioning_date": [
        ("Pset_FacilityCommon", "CommissioningDate"),
        ("Pset_AssetCommon", "CommissioningDate"),
        ("Pset_BuildingCommon", "YearOfConstruction"),
    ],
    "expected_service_life": [
        ("Pset_LifeTime", "ServiceLife"),
        ("Pset_BuildingCommon", "ServiceLife"),
        ("Pset_AssetCommon", "ExpectedServiceLife"),
    ],
}


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
        # IFC4X3: IfcBuilding deprecated — fall back to IfcFacility
        for facility in _by_type_safe(self._ifc, "IfcFacility"):
            return _str_or_none(getattr(facility, "Name", None))
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
        count = self._count("IfcBuilding")
        if count == 0:
            # IFC4X3: IfcBuilding deprecated — count IfcFacility instead
            count = len(_by_type_safe(self._ifc, "IfcFacility"))
        return count

    def _field_storey_count(self) -> int:
        count = self._count("IfcBuildingStorey")
        if count == 0:
            # IFC4X3: IfcBuildingStorey deprecated — count IfcFacilityPart instead
            count = len(_by_type_safe(self._ifc, "IfcFacilityPart"))
        return count

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

    def _field_total_length(self) -> float | None:
        return _sum_length_from_qto(self._ifc)

    # ── Materials ─────────────────────────────────────────────────────────────

    def _field_material_count(self) -> int:
        return self._count("IfcMaterial")

    def _field_dominant_material(self) -> str | None:
        counts: dict[str, int] = {}
        for mat in self._ifc.by_type("IfcMaterial"):
            name = _str_or_none(getattr(mat, "Name", None))
            if name:
                counts[name] = counts.get(name, 0) + 1
        return max(counts, key=lambda k: counts[k]) if counts else None

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

    def _field_bim_completeness_score(self) -> float:
        geom = self.get("geometry_completion_pct") or 0.0
        prop = self.get("property_completion_pct") or 0.0
        qty = self.get("quantity_completion_pct") or 0.0
        has_cls = 10.0 if self.get("has_classifications") else 0.0
        has_mat = 10.0 if self.get("has_materials") else 0.0
        score = geom * 0.3 + prop * 0.3 + qty * 0.2 + has_cls + has_mat
        return round(min(score, 100.0), 1)

    def _field_pct_objects_with_psets(self) -> float | None:
        objects = self._ifc.by_type("IfcObject")
        if not objects:
            return None
        with_psets = sum(
            1 for o in objects
            if any(
                rel.is_a("IfcRelDefinesByProperties")
                and rel.RelatingPropertyDefinition.is_a("IfcPropertySet")
                for rel in (getattr(o, "IsDefinedBy", []) or [])
            )
        )
        return round(with_psets / len(objects) * 100, 1)

    def _field_pct_objects_with_classification(self) -> float | None:
        objects = self._ifc.by_type("IfcObject")
        if not objects:
            return None
        obj_ids = {id(o) for o in objects}
        classified: set[int] = set()
        for rel in _by_type_safe(self._ifc, "IfcRelAssociatesClassification"):
            for obj in (getattr(rel, "RelatedObjects", []) or []):
                if id(obj) in obj_ids:
                    classified.add(id(obj))
        return round(len(classified) / len(objects) * 100, 1)

    def _field_pct_objects_with_material(self) -> float | None:
        objects = self._ifc.by_type("IfcObject")
        if not objects:
            return None
        obj_ids = {id(o) for o in objects}
        with_mat: set[int] = set()
        for rel in _by_type_safe(self._ifc, "IfcRelAssociatesMaterial"):
            for obj in (getattr(rel, "RelatedObjects", []) or []):
                if id(obj) in obj_ids:
                    with_mat.add(id(obj))
        return round(len(with_mat) / len(objects) * 100, 1)

    def _field_pct_objects_with_manufacturer(self) -> float | None:
        return self._pct_objects_with_pset_prop(
            pset_names=[],
            prop_names=["Manufacturer", "ManufacturerName"],
        )

    def _field_pct_objects_with_asset_tag(self) -> float | None:
        objects = self._ifc.by_type("IfcObject")
        if not objects:
            return None
        with_tag = sum(
            1 for o in objects
            if _str_or_none(getattr(o, "Tag", None)) is not None
        )
        return round(with_tag / len(objects) * 100, 1)

    def _field_pct_objects_with_serial_number(self) -> float | None:
        return self._pct_objects_with_pset_prop(
            pset_names=[],
            prop_names=["SerialNumber", "Serial"],
        )

    def _field_pct_objects_with_documents(self) -> float | None:
        objects = self._ifc.by_type("IfcObject")
        if not objects:
            return None
        obj_ids = {id(o) for o in objects}
        with_doc: set[int] = set()
        for rel in _by_type_safe(self._ifc, "IfcRelAssociatesDocument"):
            for obj in (getattr(rel, "RelatedObjects", []) or []):
                if id(obj) in obj_ids:
                    with_doc.add(id(obj))
        return round(len(with_doc) / len(objects) * 100, 1)

    def _pct_objects_with_pset_prop(
        self,
        pset_names: list[str],
        prop_names: list[str],
    ) -> float | None:
        """% of IfcObject entities having any of prop_names in a PropertySet.

        If pset_names is empty, all PropertySets are searched.
        """
        objects = self._ifc.by_type("IfcObject")
        if not objects:
            return None
        count = sum(
            1 for o in objects
            if _object_has_pset_prop(o, pset_names, prop_names)
        )
        return round(count / len(objects) * 100, 1)

    # ── Asset ─────────────────────────────────────────────────────────────────

    def _search_asset_pset(self, candidates: list[tuple[str, str]]) -> str | None:
        """Search Psets on project/site/building/facility-level entities."""
        for etype in ("IfcProject", "IfcSite", "IfcBuilding"):
            for ent in self._ifc.by_type(etype):
                for pset_name, prop_name in candidates:
                    val = _read_pset_prop(ent, pset_name, prop_name)
                    if val is not None:
                        return str(val)
        for ent in _by_type_safe(self._ifc, "IfcFacility"):
            for pset_name, prop_name in candidates:
                val = _read_pset_prop(ent, pset_name, prop_name)
                if val is not None:
                    return str(val)
        return None

    def _field_asset_type(self) -> str | None:
        return self._search_asset_pset(_ASSET_PSET_CANDIDATES["asset_type"])

    def _field_asset_subtype(self) -> str | None:
        return self._search_asset_pset(_ASSET_PSET_CANDIDATES["asset_subtype"])

    def _field_intended_use(self) -> str | None:
        return self._search_asset_pset(_ASSET_PSET_CANDIDATES["intended_use"])

    def _field_lifecycle_stage(self) -> str | None:
        return self._search_asset_pset(_ASSET_PSET_CANDIDATES["lifecycle_stage"])

    def _field_operational_status(self) -> str | None:
        return self._search_asset_pset(_ASSET_PSET_CANDIDATES["operational_status"])

    def _field_owner(self) -> str | None:
        return self._search_asset_pset(_ASSET_PSET_CANDIDATES["owner"])

    def _field_operator(self) -> str | None:
        return self._search_asset_pset(_ASSET_PSET_CANDIDATES["operator"])

    def _field_maintainer(self) -> str | None:
        return self._search_asset_pset(_ASSET_PSET_CANDIDATES["maintainer"])

    def _field_asset_identifier(self) -> str | None:
        return self._search_asset_pset(_ASSET_PSET_CANDIDATES["asset_identifier"])

    def _field_facility_identifier(self) -> str | None:
        return self._search_asset_pset(_ASSET_PSET_CANDIDATES["facility_identifier"])

    def _field_commissioning_date(self) -> str | None:
        return self._search_asset_pset(_ASSET_PSET_CANDIDATES["commissioning_date"])

    def _field_expected_service_life(self) -> str | None:
        return self._search_asset_pset(_ASSET_PSET_CANDIDATES["expected_service_life"])

    # ── Classification ────────────────────────────────────────────────────────

    def _primary_classification(self) -> tuple[str | None, str | None, str | None]:
        if "_primary_cls" not in self._cache:
            self._cache["_primary_cls"] = self._compute_primary_classification()
        return self._cache["_primary_cls"]

    def _compute_primary_classification(self) -> tuple[str | None, str | None, str | None]:
        for ref in _by_type_safe(self._ifc, "IfcClassificationReference"):
            identification = _str_or_none(
                getattr(ref, "Identification", None) or getattr(ref, "ItemReference", None)
            )
            name = _str_or_none(getattr(ref, "Name", None))
            source = getattr(ref, "ReferencedSource", None)
            system: str | None = None
            if source is not None and hasattr(source, "is_a"):
                if source.is_a("IfcClassification"):
                    system = _str_or_none(getattr(source, "Name", None))
                elif source.is_a("IfcClassificationReference"):
                    root = getattr(source, "ReferencedSource", None)
                    if root is not None and hasattr(root, "is_a") and root.is_a("IfcClassification"):
                        system = _str_or_none(getattr(root, "Name", None))
            if identification or name or system:
                return system, identification, name
        for cls in self._ifc.by_type("IfcClassification"):
            system = _str_or_none(getattr(cls, "Name", None))
            if system:
                return system, None, None
        return None, None, None

    def _field_primary_classification_system(self) -> str | None:
        return self._primary_classification()[0]

    def _field_primary_classification_code(self) -> str | None:
        return self._primary_classification()[1]

    def _field_primary_classification_name(self) -> str | None:
        return self._primary_classification()[2]

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

    def _field_complexity_index(self) -> float | None:
        storeys = self.get("storey_count")
        entities = self.get("total_entities")
        if not storeys or not entities:
            return None
        return round(entities / storeys, 1)

    def _field_objects_per_m2(self) -> float | None:
        objects = self.get("total_objects")
        area = self.get("gross_floor_area")
        if not objects or not area:
            return None
        return round(objects / area, 4)

    def _field_volume_per_m2(self) -> float | None:
        volume = self.get("gross_volume")
        area = self.get("gross_floor_area")
        if not volume or not area:
            return None
        return round(volume / area, 4)

    # ── Extraction metadata ───────────────────────────────────────────────────

    def _field_extractor_version(self) -> str:
        return "1.1.0"

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


def _sum_length_from_qto(ifc: Any) -> float | None:
    """Sum IfcQuantityLength named Length/GrossLength/NetLength across all IfcElement entities."""
    total = 0.0
    found = False
    for element in ifc.by_type("IfcElement"):
        for rel in (getattr(element, "IsDefinedBy", []) or []):
            if not rel.is_a("IfcRelDefinesByProperties"):
                continue
            pdef = rel.RelatingPropertyDefinition
            if not pdef.is_a("IfcElementQuantity"):
                continue
            for qty in (getattr(pdef, "Quantities", []) or []):
                if qty.Name in ("Length", "GrossLength", "NetLength") and qty.is_a("IfcQuantityLength"):
                    try:
                        total += float(qty.LengthValue)
                        found = True
                    except (AttributeError, TypeError, ValueError):
                        pass
    return round(total, 3) if found else None


def _read_pset_prop(entity: Any, pset_name: str, prop_name: str) -> Any:
    """Return the value of prop_name inside pset_name on entity, or None."""
    for rel in (getattr(entity, "IsDefinedBy", []) or []):
        if not rel.is_a("IfcRelDefinesByProperties"):
            continue
        pdef = rel.RelatingPropertyDefinition
        if not pdef.is_a("IfcPropertySet") or pdef.Name != pset_name:
            continue
        for prop in (getattr(pdef, "HasProperties", []) or []):
            if prop.Name == prop_name and prop.is_a("IfcPropertySingleValue"):
                nv = getattr(prop, "NominalValue", None)
                if nv is not None:
                    try:
                        return nv.wrappedValue
                    except AttributeError:
                        return str(nv)
    return None


def _object_has_pset_prop(
    obj: Any,
    pset_names: list[str],
    prop_names: list[str],
) -> bool:
    """True when obj has any of prop_names in a PropertySet (optionally filtered by pset_names)."""
    for rel in (getattr(obj, "IsDefinedBy", []) or []):
        if not rel.is_a("IfcRelDefinesByProperties"):
            continue
        pdef = rel.RelatingPropertyDefinition
        if not pdef.is_a("IfcPropertySet"):
            continue
        if pset_names and pdef.Name not in pset_names:
            continue
        for prop in (getattr(pdef, "HasProperties", []) or []):
            if prop.Name in prop_names:
                if prop.is_a("IfcPropertySingleValue"):
                    return getattr(prop, "NominalValue", None) is not None
                return True
    return False
