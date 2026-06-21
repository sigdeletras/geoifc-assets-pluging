# Reglas de Arquitectura

## Arquitectura Hexagonal Ligera

El complemento usa una arquitectura hexagonal ligera.

La idea base es:

```text
nucleo puro + adaptadores QGIS/IFC + servicios transversales
```

Capas principales:

```text
core
adapters
services
```

---

## Core

La carpeta `core/` contiene logica pura.

No debe importar:

* QGIS
* PyQt
* IfcOpenShell
* visor web
* sistema de archivos QGIS

Puede contener modelos, validaciones, reglas de mapeo IFC-GIS y errores propios.

---

## Adapters

La carpeta `adapters/` contiene integraciones externas.

Subcarpetas:

* `adapters/qgis/`
* `adapters/ifc/`

`adapters/qgis/` contiene plugin, dock, lectura/escritura QGIS, mensajes, i18n y compatibilidad QGIS 3/4.

`adapters/ifc/` contiene lectura IFC y adaptacion de IfcOpenShell.

---

## Services

La carpeta `services/` contiene servicios transversales.

Inicialmente:

* logging

---

## Criterio de Abstraccion

Crear una abstraccion solo si:

* aisla QGIS, Qt, IfcOpenShell u otra dependencia externa
* permite probar logica sin QGIS
* contiene una decision funcional
* reduce duplicacion real
* estabiliza una frontera que probablemente cambiara

Evitar abstracciones que solo pasen datos de un sitio a otro sin logica.

No crear de entrada `domain/`, `application/`, `infrastructure/`, `presentation/`, `ports/`, `dto/` ni `use_cases/`. Solo incorporarlas si el crecimiento del proyecto lo justifica claramente.
