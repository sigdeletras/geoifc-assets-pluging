"""Create a QGIS temporary memory layer from a StoreyFootprint."""

from __future__ import annotations

import logging
from pathlib import Path

from geoifcassets.adapters.ifc.footprint_extractor import StoreyFootprint

_log = logging.getLogger("geoifcassets")


def add_footprint_layer(footprint: StoreyFootprint, ifc_path: str) -> str:
    """Create and add a temporary Polygon layer to the current QGIS project.

    The geometry is reprojected from the IFC CRS to the project CRS when both
    are valid and differ. The original IFC CRS is preserved in the ``ifc_crs``
    attribute for traceability.

    The layer is not saved to disk — it exists only for the duration of the
    QGIS session or until the user removes it manually.

    Returns the authid of the CRS used for the layer (project CRS when
    reprojected, IFC CRS otherwise).

    Raises RuntimeError when the memory layer cannot be created.
    """
    from qgis.PyQt.QtCore import QVariant  # noqa: PLC0415
    from qgis.core import (  # noqa: PLC0415
        QgsCoordinateReferenceSystem,
        QgsCoordinateTransform,
        QgsFeature,
        QgsField,
        QgsGeometry,
        QgsProject,
        QgsVectorLayer,
    )

    project = QgsProject.instance()
    project_crs = project.crs()
    source_crs = QgsCoordinateReferenceSystem(footprint.crs_auth_id)

    geom = QgsGeometry.fromWkt(footprint.wkt)

    if project_crs.isValid() and source_crs.isValid() and project_crs != source_crs:
        transform = QgsCoordinateTransform(source_crs, project_crs, project)
        geom.transform(transform)
        target_crs = project_crs
        _log.info(
            "Footprint reprojected: %s → %s",
            footprint.crs_auth_id,
            project_crs.authid(),
        )
    else:
        target_crs = source_crs if source_crs.isValid() else project_crs
        if not source_crs.isValid():
            _log.warning(
                "Source CRS '%s' is not valid — using project CRS as fallback",
                footprint.crs_auth_id,
            )

    ifc_filename = Path(ifc_path).name
    layer_name = f"IFC Floor — {footprint.storey_name} — {ifc_filename}"
    uri = f"Polygon?crs={target_crs.authid()}"

    layer = QgsVectorLayer(uri, layer_name, "memory")
    if not layer.isValid():
        raise RuntimeError(f"Could not create QGIS memory layer: {layer_name}")

    provider = layer.dataProvider()
    provider.addAttributes([
        QgsField("storey_name", QVariant.String),
        QgsField("ifc_file", QVariant.String),
        QgsField("ifc_crs", QVariant.String),
        QgsField("elements", QVariant.Int),
        QgsField("fallback", QVariant.Bool),
    ])
    layer.updateFields()

    feature = QgsFeature()
    feature.setGeometry(geom)
    feature.setAttributes([
        footprint.storey_name,
        ifc_filename,
        footprint.crs_auth_id,   # original IFC CRS for traceability
        footprint.element_count,
        footprint.used_fallback,
    ])
    provider.addFeature(feature)
    layer.updateExtents()

    project.addMapLayer(layer)

    _log.info(
        "Footprint layer added: name='%s' ifc_crs=%s layer_crs=%s elements=%d fallback=%s",
        layer_name,
        footprint.crs_auth_id,
        target_crs.authid(),
        footprint.element_count,
        footprint.used_fallback,
    )
    return target_crs.authid()
