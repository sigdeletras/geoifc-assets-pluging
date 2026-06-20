# Reglas de Arquitectura

## Arquitectura Hexagonal

El complemento usa arquitectura hexagonal ligera.

Capas principales:

```text
presentation
application
domain
infrastructure
```

---

## Domain

La capa `domain` contiene reglas puras.

No debe importar:

* QGIS
* PyQt
* IfcOpenShell
* visor web
* sistema de archivos QGIS

---

## Application

La capa `application` contiene casos de uso y DTOs.

Casos de uso MVP:

* `AssociateIfcToFeatureUseCase`
* `OpenIfcViewerUseCase`
* `ReadIfcPropertiesUseCase`
* `SelectIfcPropertiesUseCase`
* `MapIfcPropertiesToFieldsUseCase`
* `UpdateFeatureAttributesUseCase`

---

## Infrastructure

La capa `infrastructure` contiene adaptadores.

Subcarpetas:

* `qgis/`
* `qgis/compat/`
* `ifc/`
* `logging/`
* `storage/`
* `webviewer/`

---

## Presentation

La capa `presentation` contiene dialogs, docks y controllers.

La UI llama a casos de uso, no a servicios de infraestructura directamente salvo adaptadores muy acotados.
