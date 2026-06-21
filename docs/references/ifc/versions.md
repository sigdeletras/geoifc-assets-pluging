# Versiones IFC

Este documento identifica las versiones IFC relevantes para GeoIFC Assets.

---

# 1. Versiones objetivo

| Version documental | Identificador habitual `FILE_SCHEMA` | Uso previsto |
| --- | --- | --- |
| IFC2x3 TC1 | `IFC2X3` | Modelos existentes de edificacion y activos heredados |
| IFC4 ADD2 TC1 | `IFC4` | Modelos actuales de edificacion y activos generales |
| IFC4.3 ADD2 / IFC 4.3.2.0 | `IFC4X3` | Infraestructura, carreteras, ferrocarril, puentes y redes |

---

# 2. Criterio de soporte MVP

El MVP debe intentar abrir y consultar propiedades en IFC2x3, IFC4 e IFC4.3 cuando IfcOpenShell pueda leer el fichero.

El soporte MVP se limita a:

* abrir modelo IFC
* identificar version/esquema
* listar entidades
* leer atributos basicos
* leer Property Sets
* leer Quantity Sets disponibles
* mapear valores seleccionados a campos GIS

No se incluye en el MVP:

* interpretacion georreferenciada
* calculo geometrico derivado
* importacion de geometria IFC
* reglas sectoriales automaticas
* procesamiento batch

---

# 3. Regla de versionado

El plugin no debe asumir que una propiedad, entidad o Quantity Set existe en todas las versiones IFC.

Cada extractor o lector debe considerar:

* version IFC detectada
* clase IFC
* disponibilidad real del Property Set
* disponibilidad real del Quantity Set
* valores nulos o ausentes

