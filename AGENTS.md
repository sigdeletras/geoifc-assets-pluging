# Agent Instructions

## GeoIFC Assets

This repository is designed to be developed with agentic coding tools such as Codex, Cursor, Claude, and similar assistants.

These instructions are mandatory for all coding agents working in this repository.

---

# 1. Project Summary

GeoIFC Assets is a QGIS plugin that connects GIS features with IFC models.

The MVP focuses on:

* associating a GIS feature with an IFC file
* opening the IFC in an embedded viewer
* selecting IFC elements
* reading IFC attributes, Property Sets, and Quantity Sets
* selecting one or more IFC properties
* mapping selected IFC properties to GIS fields
* writing selected values into GIS feature attributes
* logging the main workflow with developer logs and user logs

The MVP does not include:

* indicator engine
* batch processing
* PostGIS integration
* IFC georeferencing
* custom profiles

Sector profiles are an evolution after the MVP.

---

# 2. Language Policy

Source code is always written in English:

* modules
* packages
* classes
* functions
* variables
* tests
* logs
* technical comments

The multilingual policy applies only to:

* plugin user interface
* `metadata.txt`
* `README.md` and `README.es.md`

Repository documentation is written in Spanish, except README files.

All user-visible plugin UI text must be translatable to English and Spanish.

---

# 3. Repository Boundaries

The installable QGIS plugin lives only in:

```text
plugin/geoifc_assets/
```

Do not place repository support files inside the installable plugin package.

The plugin package must not include:

* `docs/`
* `tests/`
* `rules/`
* `scripts/`
* `.github/`
* `.cursor/`
* `.agents/`
* root agent files

---

# 4. Architecture Rules

Use a hexagonal architecture:

```text
presentation -> application -> domain
infrastructure -> application/domain through adapters
```

Main folders inside the plugin:

```text
domain/
application/
infrastructure/
presentation/
webviewer/
i18n/
```

Rules:

* Domain code must not import QGIS, PyQt, IfcOpenShell, or viewer code.
* Application use cases coordinate domain services and ports.
* QGIS-specific code belongs in `infrastructure/qgis/`.
* IFC-specific code belongs in `infrastructure/ifc/`.
* QGIS 3/4 compatibility helpers belong in `infrastructure/qgis/compat/`.
* UI code belongs in `presentation/`.
* Embedded viewer assets belong in `webviewer/`.

---

# 5. QGIS Compatibility

The plugin must be prepared for both QGIS 3 and QGIS 4.

Rules:

* import Qt through `qgis.PyQt`
* do not import directly from `PyQt5` or `PyQt6`
* use Qt5/Qt6-compatible enum forms
* isolate QGIS 3/4 differences in `infrastructure/qgis/compat/`
* validate against one QGIS 3 LTR version and one QGIS 4.x version before release

Expected metadata for one package compatible with QGIS 3 and 4:

```ini
qgisMinimumVersion=3.0
qgisMaximumVersion=4.99
```

---

# 6. IFC/BIM Rules

The MVP reads IFC data but does not import IFC geometry into GIS.

The IFC reader must support version-aware behavior where needed.

Target IFC versions for documentation and tests:

* IFC2x3 TC1
* IFC4 ADD2 TC1
* IFC4.3 ADD2 / IFC 4.3.2.0

Agents must not assume a property exists in every IFC version.

---

# 7. Workflow

Before editing:

1. Read `docs/plan_desarrollo.md`.
2. Read the relevant file in `docs/`.
3. Read relevant rules in `rules/`.
4. Keep changes scoped to the user request.

When implementing:

* preserve user changes
* do not rewrite unrelated files
* add tests for behavior when implementation starts
* update docs when behavior or workflow changes
* keep UI strings translatable
* avoid `print()` in distributable plugin code; use logging instead

Before finishing:

* summarize changed files
* mention tests run or not run
* mention any compatibility gap
* mention logging or user-message impact when relevant

---

# 8. Authoritative Local References

Use these files as source of truth:

* `docs/plan_desarrollo.md`
* `docs/ciclo_vida_desarrollo.md`
* `docs/compatibilidad_qgis.md`
* `docs/gestion_logs.md`
* `rules/architecture_rules.md`
* `rules/qgis_plugin_rules.md`
* `rules/i18n_rules.md`
* `rules/qgis_compatibility_rules.md`
* `rules/logging_rules.md`
* `rules/agentic_development_rules.md`
