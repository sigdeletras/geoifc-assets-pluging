# Alcance funcional del sistema de extracción de propiedades IFC

## 1. Plantillas de extracción

El sistema estará basado en **plantillas de extracción** definidas mediante archivos JSON. Cada plantilla describirá las propiedades que podrán recuperarse de un modelo IFC.

El complemento incluirá un conjunto de plantillas predefinidas, aunque el usuario podrá crear sus propias plantillas o cargar plantillas personalizadas, siempre que respeten la estructura JSON definida.

Cada plantilla contendrá, como mínimo, la siguiente información para cada propiedad:

* Tipo (CORE o CLASS_METRIC).
* Grupo al que pertenece (por ejemplo: CDE_IFC, Archivo, IFC, Proyecto, Localización, Organización espacial, Objetos, Geometría, Materiales, Calidad BIM, Indicadores, etc.).
* Identificador de la propiedad.
* Nombre del campo que se creará en la capa GIS.
* Alias del campo.
* Descripción.
* Tipo de dato.
* Unidad (cuando proceda).
* Origen del dato (Cabecera IFC, IfcProject, Quantity Set, Property Set, cálculo geométrico, derivado, etc.).
* Indicador de obligatoriedad.
* Relevancia para explotación GIS.

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
