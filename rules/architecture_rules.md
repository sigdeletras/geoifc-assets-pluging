# Reglas de Arquitectura

## Arquitectura Modular Pragmatica

El complemento usa una arquitectura modular pragmatica inspirada en arquitectura hexagonal.

La arquitectura hexagonal se usa como orientacion para aislar dependencias externas, no como dogma ni como obligacion de crear capas ceremoniales.

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

La capa `application` contiene casos de uso y DTOs cuando aportan valor real.

Casos de uso MVP:

* `AssociateIfcToFeatureUseCase`
* `OpenIfcViewerUseCase`
* `ReadIfcPropertiesUseCase`
* `SelectIfcPropertiesUseCase`
* `MapIfcPropertiesToFieldsUseCase`
* `UpdateFeatureAttributesUseCase`

No es obligatorio crear un caso de uso para cada accion pequena de UI. Crear un caso de uso cuando coordine una operacion significativa, contenga logica funcional o facilite pruebas sin QGIS.

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

---

## Criterio de Abstraccion

Crear una abstraccion solo si:

* aisla QGIS, Qt, IfcOpenShell u otra dependencia externa
* permite probar logica sin QGIS
* contiene una decision funcional
* reduce duplicacion real
* estabiliza una frontera que probablemente cambiara

Evitar abstracciones que solo pasen datos de un sitio a otro sin logica.
