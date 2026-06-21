# Project Brief

## GeoIFC Assets

GeoIFC Assets is a QGIS plugin for connecting GIS assets with IFC models.

The plugin keeps IFC as an external source. It does not import IFC geometry into GIS.

The MVP lets users:

* select a GIS feature
* associate an IFC file path or URL
* open the IFC in an embedded viewer
* inspect IFC properties
* select properties
* map selected properties to GIS fields
* write values into feature attributes
* log main operations with developer logs and user logs

Development language:

* English for code
* Spanish for repository documentation
* English and Spanish for plugin UI, README, and metadata

Compatibility:

* QGIS 3 LTR
* QGIS 4.x

IFC references:

* `docs/references/ifc/`
* `tests/fixtures/ifc/` for test data only

Logging:

* avoid `print()` in plugin code
* use developer logs for diagnostics
* use user logs/messages for final users
