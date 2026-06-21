# GeoIFC Assets

GeoIFC Assets is a QGIS plugin for connecting GIS assets with IFC models.

The plugin is in early development. Phase 1 provides the installable QGIS plugin
shell, project structure, logging service, translation scaffolding, validation
scripts, and the initial layer contract used by the MVP.

## MVP

The MVP will support:

* selecting a GIS layer that contains `ifc_path` or `ifc_url`
* opening the IFC referenced by the selected GIS feature
* opening the IFC in an embedded viewer
* selecting IFC elements
* inspecting IFC properties
* mapping selected IFC properties to GIS fields
* writing selected values into GIS attributes
* logging main operations for developers and final users

The selected GIS layer must contain at least one of these fields:

* `ifc_path`: local or relative IFC file path
* `ifc_url`: IFC file URL

## Development

Code is written in English.

Repository documentation is written in Spanish.

The plugin UI, metadata, and README files are maintained in English and Spanish.

Plugin code should use the logging strategy instead of `print()` diagnostics.

Agent instructions:

* `AGENTS.md`
* `CLAUDE.md`
* `.cursor/rules/`

Useful commands:

* `.\scripts\run_tests.ps1`
* `.\scripts\lint.ps1`
* `.\scripts\package_plugin.ps1`
