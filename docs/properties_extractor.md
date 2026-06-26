# Alcance funcional del sistema de extracción de propiedades IFC

## 1. Plantillas de extracción

El sistema se basa en **plantillas de extracción** definidas mediante archivos JSON. Cada plantilla describe las propiedades que pueden recuperarse de un modelo IFC.

La plantilla base se encuentra en `geoifcassets/templates/ifc_core_catalog.json`. El usuario puede crear plantillas personalizadas siempre que respeten la estructura JSON definida.

### 1.1 Bloque `metadata` (nivel raíz)

Cada plantilla incluye un bloque `metadata` con información descriptiva sobre la propia plantilla:

| Campo | Descripción |
|---|---|
| `author` | Autor de la plantilla |
| `contact` | Correo de contacto del mantenedor |
| `created_at` | Fecha de creación (ISO 8601) |
| `updated_at` | Fecha de última modificación (ISO 8601) |
| `template_version` | Versión del esquema de la plantilla |
| `min_extractor_version` | Versión mínima del extractor compatible |
| `ifc_versions` | Lista de versiones IFC cubiertas (`["IFC2X3", "IFC4", "IFC4X3"]`) |
| `language` | Idioma por defecto de alias y descripciones |
| `license` | Licencia de la plantilla |
| `tags` | Etiquetas para búsqueda y categorización |

### 1.2 Array `fields`

Cada elemento del array `fields` define una propiedad extraíble. Campos implementados:

| Campo JSON | Obligatorio | Descripción |
|---|---|---|
| `name` | sí | Identificador interno; se usa como nombre de campo GIS |
| `enabled` | sí | Si la propiedad está activa por defecto |
| `group` | sí | Grupo funcional (File, IFC Header, Project, Location, …) |
| `alias` | no | Nombre legible mostrado en la UI |
| `description` | no | Descripción del campo |
| `ifc_source` | no | Origen IFC exacto del valor (ver tabla siguiente). `null` para campos de sistema de archivos, metadatos del extractor o indicadores calculados |
| `computed` | no | `true` si el valor es calculado/derivado; `false` si es lectura directa de un atributo IFC o cabecera STEP |
| `min_ifc_version` | no | Solo presente cuando el campo NO está disponible en IFC2X3 (ej. `"IFC4"` para campos que requieren `IfcMapConversion`) |
| `ifc4x3_note` | no | Solo presente cuando el campo tiene comportamiento diferente en IFC4X3 (ej. deprecación de `IfcBuilding` → `IfcFacility`) |

### 1.3 Valores de `ifc_source`

| Patrón | Ejemplo | Significado |
|---|---|---|
| `FILE_NAME.attr` | `FILE_NAME.author` | Atributo de la sección FILE_NAME de la cabecera STEP |
| `FILE_DESCRIPTION` | `FILE_DESCRIPTION` | Sección FILE_DESCRIPTION de la cabecera STEP |
| `FILE_SCHEMA` | `FILE_SCHEMA` | Sección FILE_SCHEMA de la cabecera STEP |
| `IfcEntity.Attr` | `IfcProject.Name` | Atributo directo de una entidad IFC |
| `IfcEntity` | `IfcSite` | Entidad IFC (para conteos o comprobaciones de presencia) |
| `IfcEntityQuantity.QtoName` | `IfcElementQuantity.GrossFloorArea` | Quantity de un `IfcElementQuantity` |
| `IfcEntity A \| IfcEntity B` | `IfcBuildingStorey \| IfcSpace` | Cualquiera de las dos entidades |
| `null` | — | Campo de sistema de archivos, metadato del extractor o indicador calculado sin origen IFC directo |

### 1.4 Localización (`i18n`)

La plantilla incluye un bloque `i18n` con traducciones de alias, descripciones y nombres de grupo. El loader aplica la traducción correspondiente al locale activo en tiempo de carga, sin modificar la plantilla.

El objetivo es desacoplar completamente la lógica de extracción de la definición de propiedades, permitiendo ampliar el catálogo sin modificar el código del complemento.

---

## 2. Selección de propiedades CORE

Una vez cargada la plantilla JSON, el complemento mostrará todas las propiedades agrupadas según su grupo funcional.

El usuario podrá:

* seleccionar individualmente las propiedades que desea extraer;
* seleccionar un grupo completo;
* seleccionar todas las propiedades de la plantilla.

Antes de actualizar la capa GIS, el sistema realizará una extracción preliminar y mostrará una **vista previa** con los valores obtenidos.

Esta vista permitirá detectar:

* propiedades vacías;
* propiedades inexistentes en el IFC;
* valores incorrectos;
* posibles errores de extracción.

De esta forma el usuario podrá decidir qué atributos desea incorporar finalmente a la capa.

---

## 3. Actualización de la capa GIS

Una vez confirmada la extracción, el complemento analizará la estructura de la capa GIS.

Para cada propiedad seleccionada:

* si el campo ya existe en la capa, únicamente actualizará el valor correspondiente a la entidad (feature) sobre la que se está trabajando;
* si el campo no existe, lo creará automáticamente y rellenará únicamente la entidad seleccionada.

En ningún caso se modificarán el resto de entidades de la capa.

---

# 4. Métricas por clases IFC (CLASS_METRIC)

Las métricas asociadas a las clases IFC constituyen un caso particular.

Dado que cada modelo IFC contiene un conjunto diferente de clases, estas no podrán definirse completamente de forma estática en la plantilla JSON.

El flujo será el siguiente:

1. Lectura del modelo IFC.
2. Identificación automática de todas las clases IFC presentes.
3. Generación dinámica de una nueva pestaña con las clases detectadas.
4. Para cada clase se mostrarán únicamente las métricas que puedan obtenerse para dicha clase.

Por ejemplo, si el modelo contiene la clase **IfcWall**, el sistema podrá ofrecer automáticamente:

* wall_count
* wall_length
* wall_area
* wall_volume

Si el modelo contiene la clase **IfcRoad**, se ofrecerán, por ejemplo:

* road_count
* road_length
* road_area

Y así sucesivamente para todas las clases presentes en el modelo.

El usuario decidirá qué métricas desea incorporar a la capa GIS.

---

## 5. Obtención de las métricas

Para cada métrica, el sistema intentará recuperar la información siguiendo un orden de prioridad:

1. Quantity Sets (Qto).
2. Property Sets específicos.
3. Cálculo geométrico mediante IfcOpenShell.
4. No disponible.

En la vista previa se indicará también el origen del valor recuperado, permitiendo conocer si la información procede directamente del modelo IFC o ha sido calculada.

---

## 6. Arquitectura general

El funcionamiento general del sistema será el siguiente:

2. Carga de la plantilla JSON.
3. Extracción de las propiedades CORE.
4. Descubrimiento automático de las clases IFC presentes.
5. Generación dinámica de las métricas disponibles para cada clase.
6. Vista previa de todos los valores recuperados.
7. Selección de las propiedades y métricas a incorporar.
8. Actualización automática de la capa GIS.

Esta arquitectura permite que el sistema sea completamente configurable mediante plantillas, independiente de la versión del estándar IFC y extensible a futuras clases o propiedades sin necesidad de modificar el código del complemento.
ión del estándar IFC y extensible a futuras clases o propiedades sin necesidad de modificar el código del complemento.
