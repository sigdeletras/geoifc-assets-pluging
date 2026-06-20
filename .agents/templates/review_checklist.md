# Review Checklist

## Scope

* [ ] Change matches the user request.
* [ ] No unrelated refactor.
* [ ] Plugin package boundaries respected.

## Architecture

* [ ] Domain has no QGIS/PyQt/IfcOpenShell imports.
* [ ] QGIS code stays in infrastructure or presentation.
* [ ] IFC code stays in infrastructure/ifc.
* [ ] QGIS 3/4 differences are isolated in compat layer.

## I18n

* [ ] Visible UI text is translatable.
* [ ] English and Spanish UI are covered.
* [ ] README/metadata language requirements are respected.

## Logging

* [ ] No `print()` has been introduced in plugin code.
* [ ] Developer logs are considered for technical flows.
* [ ] User logs/messages are clear and translatable.
* [ ] Sensitive data is not logged unnecessarily.

## Compatibility

* [ ] No direct PyQt5/PyQt6 imports.
* [ ] Qt enum usage is compatible with Qt5/Qt6.
* [ ] QGIS 3/4 behavior considered.

## Validation

* [ ] Tests run or reason documented.
* [ ] Manual QGIS checks listed when needed.
* [ ] Packaging impact considered.
