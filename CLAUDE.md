# Claude Instructions

This repository is agent-friendly. Claude must follow the same project rules as Codex and Cursor.

Start every task by reading:

* `AGENTS.md`
* `docs/plan_desarrollo.md`
* the relevant files in `docs/`
* the relevant files in `rules/`

Key constraints:

* Code is written in English.
* Repository documentation is written in Spanish.
* Plugin UI, `metadata.txt`, and README files must be English/Spanish.
* The installable plugin is only `geoifcassets/`.
* The MVP is manual IFC property selection and mapping to GIS fields.
* QGIS 3 and QGIS 4 compatibility must be preserved.
* Use `qgis.PyQt`, not direct `PyQt5` or `PyQt6` imports.
* Do not import QGIS or IfcOpenShell from domain code.
* Do not use `print()` as plugin logging; use the logging strategy.

Before finalizing a task, report:

* files changed
* tests run
* docs updated
* logging impact
* remaining risks or compatibility gaps
