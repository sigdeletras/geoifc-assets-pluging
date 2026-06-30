# Análisis y evolución del catálogo `ifc_core_catalog`

## Objetivo

Definir un catálogo de metadatos IFC que permita representar **un modelo IFC completo mediante una única fila** (por ejemplo, en un CSV o una capa GIS), facilitando:

- Catalogación de grandes repositorios de modelos IFC.
- Indexación y búsqueda.
- Evaluación de la calidad BIM.
- Comparación entre modelos.
- Integración con QGIS y sistemas GIS.
- Independencia del dominio (Building, Infrastructure, MEP, Rail, Road, Bridge, Water, etc.).

El catálogo **no pretende describir cada objeto IFC**, sino resumir las características generales del modelo.

---

# Situación inicial

El JSON original estaba correctamente organizado desde el punto de vista funcional.

Los grupos existentes eran:

- File
- IFC Header
- Project
- Location
- Domain
- Spatial Structure
- Model Statistics
- Geometry
- Materials
- BIM Quality
- Indicators
- Extraction

Sin embargo, durante el análisis se detectó que mezclaba conceptos diferentes:

- atributos IFC
- cantidades (Quantity Sets)
- indicadores calculados
- metadatos externos
- estadísticas

sin distinguir claramente el origen de cada dato.

---

# Problema identificado

Un mismo grupo (por ejemplo "Geometry" o "BIM Quality") contiene datos de naturaleza muy distinta.

Ejemplo:

```
gross_volume
```

proviene de un Quantity Set.

Mientras que

```
bbox_height
```

es un cálculo realizado por el extractor.

Y

```
has_geometry
```

es un indicador derivado.

Desde el punto de vista del extractor resulta útil conocer el origen del dato.

---

# Decisión 1

## Mantener los grupos existentes

Los grupos actuales son adecuados para organizar la interfaz de usuario y el catálogo.

No se modifican.

Se consideran una clasificación funcional.

---

# Decisión 2

## Incorporar `source_type`

Se añade un nuevo atributo a cada definición.

```
source_type
```

Valores posibles:

```
external_metadata
ifc_attribute
pset_property
quantity
computed
```

Con ello cada campo queda clasificado según su origen.

Ejemplo:

```json
{
  "name": "project_name",
  "group": "Project",
  "source_type": "ifc_attribute"
}
```

---

# Significado de cada source_type

## external_metadata

Información que no forma parte del IFC.

Ejemplos

- nombre del archivo
- ruta
- tamaño
- fecha
- hash
- estado de extracción

---

## ifc_attribute

Atributos definidos por el estándar IFC.

Ejemplos

```
IfcProject.Name

IfcProject.GlobalId

IfcSite.Name

IfcMaterial.Name
```

---

## pset_property

Información procedente de Property Sets.

No corresponde a atributos IFC.

Ejemplo:

```
Pset_ManufacturerTypeInformation

Pset_ProjectCommon

Pset_AssetCommon
```

---

## quantity

Información procedente de Quantity Sets.

Ejemplo:

```
GrossFloorArea

GrossVolume

Length

NetArea
```

---

## computed

Información generada por el extractor.

Ejemplos

- Bounding Box
- Dominio detectado
- Complejidad
- Objetos por planta
- Completitud BIM

---

# Revisión de los Property Sets

Durante el análisis se descartó incorporar propiedades de elementos individuales.

Ejemplos descartados

```
Door.FireRating

Pipe.Diameter

Window.UValue

Pump.Power
```

Motivo:

El catálogo representa un IFC completo mediante una única fila.

Un edificio puede contener miles de puertas con valores distintos.

No existe un valor único que pueda almacenarse.

---

# Nuevo enfoque

Solo incorporar propiedades que describan el activo completo.

Estas propiedades deben ser válidas tanto para:

- edificios
- carreteras
- puentes
- ferrocarriles
- redes hidráulicas
- instalaciones MEP
- plantas industriales

---

# Nuevo grupo: Asset

Se incorpora un grupo específico para describir el activo.

Campos propuestos

```
asset_type

asset_subtype

intended_use

lifecycle_stage

operational_status

owner

operator

maintainer

asset_identifier

facility_identifier

commissioning_date

expected_service_life
```

Todos ellos se consideran

```
source_type = pset_property
```

aunque el extractor podrá obtenerlos desde distintos Psets o propiedades equivalentes dependiendo del software BIM.

---

# Nuevo grupo: Classification

El catálogo inicial únicamente almacenaba:

```
classification_count
```

Se considera insuficiente.

Se incorporan:

```
primary_classification_system

primary_classification_code

primary_classification_name
```

Ejemplos

```
Uniclass

Omniclass

CoClass

GuBIMClass

IFC Classification
```

---

# Evolución de BIM Quality

El catálogo original medía únicamente la existencia de información.

Ejemplo

```
has_materials

has_property_sets

has_quantities
```

Se propone añadir indicadores de cobertura.

```
pct_objects_with_psets

pct_objects_with_material

pct_objects_with_classification

pct_objects_with_manufacturer

pct_objects_with_asset_tag

pct_objects_with_serial_number

pct_objects_with_documents
```

Estos indicadores permiten comparar fácilmente la calidad de distintos modelos IFC.

---

# Organización final

La estructura funcional queda:

```
Archivo

Cabecera IFC

Proyecto

Ubicación

Dominio

Estructura espacial

Estadísticas

Geometría

Materiales

Activo

Clasificación

Calidad BIM

Indicadores

Extracción
```

Mientras que el origen de los datos queda definido mediante:

```
external_metadata

ifc_attribute

pset_property

quantity

computed
```

---

# Filosofía del catálogo

El catálogo no pretende sustituir el modelo IFC.

Su objetivo es ofrecer una representación resumida del modelo que permita:

- catalogar
- indexar
- buscar
- comparar
- evaluar calidad BIM
- realizar análisis GIS
- construir cuadros de mando
- alimentar repositorios documentales

manteniendo una única fila por cada fichero IFC.

---

# Principios de diseño

El catálogo debe cumplir los siguientes principios:

- independiente del dominio (Building, Infrastructure, MEP, etc.)
- independiente del software de autor
- compatible con IFC2X3, IFC4 e IFC4X3
- fácilmente ampliable
- configurable mediante JSON
- reutilizable por el extractor IFC
- preparado para su explotación en QGIS, bases de datos y herramientas BI
- distinguir claramente entre atributos IFC, Property Sets, Quantity Sets y valores calculados