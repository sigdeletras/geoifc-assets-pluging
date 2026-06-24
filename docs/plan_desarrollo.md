# GeoIFC Assets

## Plan de Desarrollo y Arquitectura Tecnica (v3.16)

---

# 0. Objetivo del sistema

GeoIFC Assets es un complemento de QGIS orientado a la **explotacion de modelos IFC como fuente de informacion para la construccion de inventarios de activos GIS**, permitiendo:

* Asociacion de entidades GIS con modelos IFC.
* Visualizacion de IFC en un visor embebido dentro de QGIS.
* Consulta de informacion BIM estructurada.
* Seleccion manual de propiedades IFC por parte del usuario.
* Carga de propiedades IFC seleccionadas en atributos de capas GIS.
* Interfaz traducida siempre a ingles y espanol.
* Compatibilidad preparada para QGIS 3 y QGIS 4.
* Gestion de logs de desarrollo y logs para usuario final.
* Evolucion posterior hacia perfiles sectoriales reutilizables.

El sistema no importa geometria IFC ni sustituye herramientas BIM. Actua como **capa de consulta y explotacion territorial BIM -> GIS**, manteniendo el IFC como fuente externa.

---

# 1. Principios de diseno

## 1.1 Arquitectura

Aplicar una arquitectura hexagonal ligera.

La arquitectura se basara en:

```text
nucleo puro + adaptadores QGIS/IFC + servicios transversales
```

El objetivo es conservar el aislamiento de QGIS, Qt, IfcOpenShell, logging y visor web sin crear una estructura pesada de `domain/application/infrastructure/presentation` desde el inicio.

```text id="arch_hex"
core
    models
    mapping
    validation

adapters
    qgis
    ifc

services
    logging

webviewer
i18n
```

---

## 1.2 Principios de desarrollo

* Clean Code
* SOLID
* DRY
* KISS
* Dependency Injection
* Arquitectura orientada a casos de uso cuando aporten valor real
* Diseno guiado por dominio ligero
* Tipado estatico con mypy
* Testing desde el inicio

---

## 1.3 Stack tecnico

### Desarrollo

* Python 3.11+
* QGIS 3 LTR
* QGIS 4.x
* Qt / PyQt
* Codex / Cursor / Claude

### BIM

* IfcOpenShell
* That Open Engine

### Visor embebido

* Qt WebEngine (en subproceso separado, no en proceso QGIS)
* QProcess + stdout protocol (IPC QGIS ↔ subproceso)
* ThreadingHTTPServer + polling `/current.json` (IPC visor ↔ QGIS)
* HTML / TypeScript (bundle Vite offline, sin CDN)
* web-ifc (WASM) + Three.js (WebGL con fallback SwiftShader)

### Calidad

* pytest
* pytest-qt
* coverage
* ruff
* mypy

---

## 1.4 Politica multiidioma

El desarrollo del complemento se realizara siempre en ingles:

* nombres de modulos
* clases
* funciones
* variables
* comentarios tecnicos
* tests
* mensajes internos de log
* documentacion tecnica interna cuando este asociada directamente al codigo

La politica multiidioma aplica solamente a:

* interfaz del complemento
* `metadata.txt`
* `README.md` / `README.es.md`

La interfaz de usuario del complemento debe estar disponible siempre en:

* ingles
* espanol

Todos los textos visibles por el usuario deben ser traducibles:

* menus
* toolbars
* dialogs
* docks
* botones
* etiquetas
* mensajes de error
* mensajes de estado
* tooltips
* textos del visor embebido cuando formen parte de la UI del plugin

No deben existir textos visibles hardcodeados en componentes de interfaz. La arquitectura debe incluir desde el inicio una capa de traduccion basada en los mecanismos de Qt/QGIS.

La documentacion del repositorio no necesita mantenerse en dos idiomas. Se redactara en espanol, salvo el README, que si debe estar disponible en ingles y espanol.

---

## 1.5 Politica de compatibilidad QGIS 3/4

El complemento debe estar preparado para funcionar tanto en QGIS 3 como en QGIS 4.

QGIS 4 introduce la migracion tecnica a Qt6, por lo que el desarrollo debe evitar dependencias directas de una version concreta de PyQt.

Reglas principales:

* usar imports Qt desde `qgis.PyQt`
* evitar imports directos desde `PyQt5` o `PyQt6`
* usar enumeraciones compatibles con Qt5/Qt6
* aislar diferencias de API en `adapters/qgis/`
* validar el plugin en una version QGIS 3 LTR y una version QGIS 4.x antes de publicar
* declarar correctamente `qgisMinimumVersion` y `qgisMaximumVersion` en `metadata.txt`
* comprobar especialmente Qt WebEngine, QWebChannel, traducciones y escritura de atributos en ambas versiones

Si una funcionalidad no puede comportarse igual en QGIS 3 y QGIS 4, debe degradarse de forma controlada y documentada, sin impedir la carga del complemento.

---

## 1.6 Politica de logging

El complemento debe contar desde fases iniciales con una gestion de logs que permita controlar los flujos que se estan realizando.

Se diferencian dos tipos de log:

* developer logs: orientados a desarrollo, diagnostico y soporte tecnico
* user logs: orientados al usuario final, con mensajes claros y traducibles

Los developer logs pueden contener informacion tecnica como operacion, version de QGIS, version IFC, excepciones y estado interno del flujo.

Los user logs deben mostrar informacion comprensible sobre acciones realizadas, advertencias y errores recuperables. Al formar parte de la interfaz del complemento, deben estar disponibles en ingles y espanol.

Como regla general, debe evitarse al maximo el uso de `print()` en codigo del plugin. Los flujos deben registrarse mediante logging estructurado, adaptadores de infraestructura o mecanismos propios de QGIS.

`print()` solo se admite en scripts de desarrollo, pruebas o herramientas CLI internas, nunca como mecanismo normal de diagnostico del plugin distribuible.

---

# 2. Modelo conceptual del sistema

## 2.1 Unidad base: activo GIS

Cada entidad GIS representa un activo territorial vinculado a un modelo IFC:

```text id="model_asset"
Feature GIS
    geometria
    atributos GIS
    ifc_path o ifc_url
```

---

## 2.2 Relacion principal

```text id="rel_1"
1 Feature GIS <-> 1 IFC
```

El IFC es fuente de datos y visualizacion, no geometria GIS importada.

En el MVP, la relacion se resuelve mediante un campo obligatorio de la capa GIS. El usuario selecciona la capa de trabajo, y esa capa debe contener al menos uno de estos campos:

* `ifc_path`: ruta local o relativa a un fichero IFC
* `ifc_url`: URL a un fichero IFC

No se aceptan otros nombres de campo como contrato del MVP. Esta restriccion simplifica el flujo del visor, las acciones de QGIS, la validacion y la documentacion para usuarios.

No se persiste en el MVP una relacion granular con un elemento IFC mediante `GlobalId`. El `GlobalId` puede consultarse en el visor y ayudar a identificar el elemento seleccionado, pero no es un requisito estructural de la capa GIS.

---

## 2.3 Configuracion de capa GIS de trabajo

El complemento debe permitir seleccionar la capa GIS de trabajo desde la interfaz:

* seleccionar una capa vectorial cargada en QGIS
* validar que la capa contiene `ifc_path` o `ifc_url`
* validar que al menos uno de esos campos tiene valor para el feature seleccionado
* cuando existan ambos campos con valor, permitir confirmar cual se usara
* informar si la capa no permite escritura cuando se quiera cargar datos

Requisitos minimos:

* capa vectorial
* campo `ifc_path` o campo `ifc_url`
* permisos de lectura de atributos
* permisos de escritura solo para operaciones de carga de valores IFC a GIS

La exigencia de `ifc_path` o `ifc_url` crea un contrato minimo de datos para el MVP. Las capas existentes que usen otros nombres deberan adaptarse antes de usar el complemento.

---

## 2.4 Acceso al visor IFC

El visor IFC debe poder abrirse desde el panel del complemento tomando como entrada el feature GIS seleccionado y el valor de `ifc_path` o `ifc_url`.

Como flujo recomendado de uso en QGIS, el complemento podra registrar una accion de capa, por ejemplo:

```text
Abrir IFC en GeoIFC Assets
```

La accion deberia poder usarse desde flujos habituales de QGIS como identificacion de elemento, formulario de atributos o menu contextual de feature, siempre que la capa este configurada.

Si no existe feature seleccionado, la capa no contiene `ifc_path` ni `ifc_url`, o los campos estan vacios, el complemento debe mostrar un mensaje de usuario claro y registrar el evento en logs.

---

## 2.5 Seleccion manual de propiedades

En la primera version, el usuario decide que informacion BIM quiere pasar a GIS:

* Selecciona una capa GIS con `ifc_path` o `ifc_url`.
* Selecciona un feature GIS.
* Abre el IFC asociado en el visor embebido.
* Selecciona un elemento IFC o consulta propiedades del modelo.
* Marca una o varias propiedades.
* Define el campo GIS de destino para cada propiedad.
* Ejecuta la carga de valores en la capa.

Este enfoque evita fijar perfiles sectoriales prematuros y permite validar con casos reales que propiedades son realmente utiles.

---

# 3. Selector y mapeo de propiedades IFC

## 3.1 Concepto

El MVP se basa en un flujo manual de seleccion y mapeo:

```text id="manual_mapping"
IFC -> Propiedades seleccionadas -> Campos GIS
```

---

## 3.2 Fuentes de propiedades

El complemento debe permitir consultar y seleccionar:

* atributos basicos del elemento IFC
* `GlobalId`
* clase IFC
* nombre
* tipo
* Property Sets
* Quantity Sets disponibles

---

## 3.3 Mapeo a campos GIS

Para cada propiedad seleccionada, el usuario debe poder:

* elegir un campo GIS existente
* crear un campo nuevo
* confirmar el tipo de dato
* revisar el valor antes de escribirlo
* evitar sobrescrituras accidentales

---

## 3.4 Persistencia del mapeo

El MVP puede guardar el ultimo mapeo usado para facilitar pruebas repetidas, pero no debe tratarlo todavia como perfil sectorial.

Un mapeo guardado debe contener:

```text id="saved_mapping"
nombre_mapeo
clase_ifc
propiedad_origen
campo_destino
tipo_dato
```

---

# 4. Perfiles sectoriales como evolutivo

## 4.1 Concepto futuro

Los perfiles sectoriales se incorporaran despues del MVP como plantillas reutilizables basadas en mapeos ya validados por usuarios:

```text id="profile_evolution"
Mapeos manuales validados -> Perfil sectorial -> Carga semiautomatica
```

---

## 4.2 Perfiles candidatos

### Edificacion

* plantas
* puertas
* ventanas
* superficies disponibles

---

### Carreteras

* tramos
* elementos
* longitudes disponibles

---

### Puentes

* partes
* materiales disponibles
* longitudes disponibles

---

### Redes hidraulicas

* valvulas
* pozos
* longitudes disponibles

---

### Ferrocarriles

* elementos de via
* instalaciones
* longitudes disponibles

---

## 4.3 Criterio para activar perfiles

Los perfiles sectoriales se deben desarrollar cuando existan:

* mapeos manuales repetidos
* campos GIS de destino estables
* propiedades IFC frecuentes por tipologia
* validacion funcional con usuarios reales

---

# 5. Arquitectura funcional

## 5.1 Modulo de visualizacion IFC

Responsable de:

* apertura del IFC asociado al feature GIS seleccionado
* renderizado 3D en visor embebido dentro del dock
* navegacion del modelo (orbita, zoom, pan)
* actualizacion del modelo al cambiar feature seleccionado en QGIS
* reinicio automatico del subproceso si este termina
* exploracion de elementos por categoria IFC (arbol plano — Fase A)
* exploracion por jerarquia espacial Proyecto → Sitio → Edificio → Planta → Espacio (arbol espacial — Fase B)
* seleccion de elemento por clic en la escena 3D via ray-casting (Fase B)
* zoom de camara al elemento seleccionado en el arbol o en la escena 3D
* consulta de atributos directos y PropertySets del elemento seleccionado
* transferencia de propiedades BIM a campos GIS via POST /transfer + QDialog (Fase C)

Tecnologias:

* `QProcess` (gestion del subproceso Python visor)
* `QWidget.createWindowContainer` + `QWindow.fromWinId` (embedding ventana nativa)
* `ThreadingHTTPServer` (servidor IFC local, polling `/current.json`)
* `web-ifc` (WASM, lectura IFC + lectura de propiedades) + `Three.js` (renderizado WebGL)
* SwiftShader (software renderer activado via `QTWEBENGINE_CHROMIUM_FLAGS`)

El visor corre en un subproceso Python separado (`webviewer_app.py`) para que
Chromium arranque fresco y lea las flags de SwiftShader, resolviendo la
incompatibilidad con el Chromium ya inicializado por QGIS. Ver ADR-008 y ADR-009.

El arbol de elementos incluye dos vistas (Fase A y Fase B, ver ADR-010):

* **Vista por categoria** — lista plana de elementos agrupados por tipo IFC (Walls, Doors, Slabs...).
* **Vista espacial** — jerarquia Proyecto → Sitio → Edificio → Planta → Elemento, usando
  `IFCRELAGGREGATES` y `IFCRELCONTAINEDINSPATIALSTRUCTURE`. Activada por defecto si el modelo
  tiene estructura espacial; deshabilitada si no.

La seleccion de un elemento (tanto desde el arbol como por clic en la escena 3D via ray-casting)
hace zoom de camara, destaca el elemento en naranja y muestra sus atributos directos y PropertySets.

La comunicacion QGIS → visor es unidireccional via HTTP polling.

**Transferencia BIM→GIS (Fase C):** cada propiedad del panel muestra un boton `→`. Al pulsarlo,
el JS hace `POST /transfer` al servidor HTTP local. Un QTimer a 250 ms consume la cola en el hilo
Qt principal y abre un dialogo donde el usuario elige el campo GIS de destino (existente o nuevo).
El valor se escribe con `layer.changeAttributeValue`. Ver ADR-010 (Fase C).

Este modulo forma parte del MVP.

---

## 5.2 Modulo de lectura IFC

Responsable de:

* abrir modelos IFC
* leer entidades
* extraer atributos basicos
* leer Property Sets
* leer Quantity Sets disponibles
* devolver valores normalizados para la interfaz

Tecnologia:

* IfcOpenShell

---

## 5.3 Modulo de seleccion y mapeo

Responsable de:

* listar propiedades disponibles
* permitir seleccion multiple
* asociar propiedades IFC con campos GIS
* validar tipos de dato
* preparar la escritura de atributos

---

## 5.4 Integracion con QGIS

Responsable de:

* leer el feature seleccionado
* validar campos requeridos
* abrir el visor IFC
* crear campos cuando el usuario lo confirme
* actualizar atributos GIS
* mostrar mensajes de estado al usuario

---

## 5.5 Modulo de logging

Responsable de:

* registrar inicio y fin de flujos principales
* registrar errores tecnicos para diagnostico
* registrar mensajes comprensibles para usuario final
* diferenciar developer logs y user logs
* evitar `print()` en codigo del plugin
* mantener trazabilidad por operacion
* evitar datos sensibles innecesarios

Flujos minimos a registrar:

* carga y descarga del plugin
* comprobacion de version QGIS
* comprobacion de Qt WebEngine
* asociacion de IFC
* apertura del visor IFC
* lectura de propiedades IFC
* seleccion de propiedades
* mapeo a campos GIS
* creacion de campos
* escritura de atributos
* errores y cancelaciones

---

# 6. Flujo funcional principal del MVP

```text id="flow_main"
1. Usuario selecciona feature GIS
2. Sistema valida que la capa contiene `ifc_path` o `ifc_url`
3. Sistema lee el valor IFC del feature seleccionado
4. Sistema abre el IFC asociado en el visor embebido
5. Usuario selecciona un elemento IFC o consulta propiedades del modelo
6. Panel lateral muestra atributos, Property Sets y Quantity Sets
7. Usuario marca una o varias propiedades IFC
8. Usuario asigna cada propiedad a un campo GIS
9. Sistema valida tipos, permisos y campos de destino
10. Sistema escribe los valores en atributos GIS del feature seleccionado
11. Sistema registra developer logs y user logs del flujo
```

---

# 7. Historias de usuario

Las historias de usuario definen el comportamiento esperado desde la perspectiva de usuarios reales del complemento. Sirven como base para priorizar el MVP, disenar la interfaz y derivar casos de uso tecnicos.

## 7.1 Actores principales

* Tecnico GIS: mantiene capas GIS e inventarios territoriales.
* Tecnico BIM: conoce el contenido del modelo IFC y sus propiedades.
* Gestor de activos: necesita consultar y completar informacion de inventario.
* Administrador del complemento: instala, configura y valida el plugin en QGIS.

---

## 7.2 Historias MVP

### HU-01 Validar la capa GIS de trabajo

Como tecnico GIS, quiero seleccionar una capa GIS que contenga `ifc_path` o `ifc_url`, para que el complemento pueda localizar el modelo IFC de cada feature de forma predecible.

Criterios de aceptacion:

* El usuario puede seleccionar una capa vectorial cargada en QGIS.
* El sistema valida que existe `ifc_path` o `ifc_url`.
* El sistema informa si el feature seleccionado no tiene valor IFC.
* Si existen ambos campos con valor, el sistema permite confirmar cual se usara.
* Si no existe ninguno de esos campos, el sistema informa del requisito de estructura de capa.
* El sistema informa errores de forma comprensible.

---

### HU-02 Abrir el IFC asociado en un visor embebido desde feature seleccionado

Como gestor de activos, quiero abrir el IFC asociado al feature seleccionado dentro de QGIS, para revisar el modelo sin salir del entorno GIS.

Criterios de aceptacion:

* El sistema lee el IFC desde `ifc_path` o `ifc_url`.
* El visor se abre dentro de QGIS.
* El usuario puede navegar el modelo 3D.
* El visor puede abrirse desde el panel del complemento.
* Si es viable en QGIS 3 y QGIS 4, el visor puede abrirse mediante una accion de capa.
* Si el IFC no se puede abrir, el sistema muestra el motivo.
* La interfaz del visor esta disponible en ingles y espanol.

---

### HU-03 Seleccionar un elemento IFC

Como tecnico BIM, quiero seleccionar un elemento del modelo IFC, para consultar sus datos especificos y decidir que propiedades llevar a GIS.

Criterios de aceptacion:

* El usuario puede seleccionar un elemento IFC desde el visor o desde un listado/arbol.
* El sistema identifica el elemento seleccionado mediante `GlobalId`.
* El sistema muestra la clase IFC del elemento.
* La seleccion actual queda sincronizada con el panel de propiedades.

---

### HU-04 Consultar propiedades BIM

Como tecnico GIS, quiero consultar atributos, Property Sets y Quantity Sets del elemento IFC seleccionado, para entender que informacion esta disponible.

Criterios de aceptacion:

* El sistema muestra atributos basicos del elemento.
* El sistema muestra Property Sets disponibles.
* El sistema muestra Quantity Sets disponibles.
* El usuario puede buscar o filtrar propiedades por texto.
* Los valores se presentan con tipo de dato reconocible cuando sea posible.

---

### HU-05 Seleccionar propiedades para cargar en GIS

Como tecnico GIS, quiero marcar una o varias propiedades IFC, para preparar la informacion que se incorporara como atributos GIS.

Criterios de aceptacion:

* El usuario puede seleccionar varias propiedades.
* El sistema muestra una lista de propiedades seleccionadas.
* El usuario puede quitar propiedades antes de ejecutar la carga.
* El sistema conserva el origen de cada propiedad seleccionada.
* La seleccion se prepara para el feature GIS actualmente seleccionado.

---

### HU-06 Mapear propiedades IFC a campos GIS

Como tecnico GIS, quiero asignar cada propiedad IFC seleccionada a un campo GIS, para controlar donde se guardara cada valor.

Criterios de aceptacion:

* El usuario puede elegir un campo existente.
* El usuario puede proponer un campo nuevo.
* El sistema infiere un tipo de dato razonable.
* El usuario puede confirmar o ajustar el tipo de dato.
* El sistema advierte antes de sobrescribir valores existentes.

---

### HU-07 Crear campos GIS controladamente

Como tecnico GIS, quiero crear campos nuevos desde el complemento solo cuando lo confirme, para evitar modificar la estructura de la capa accidentalmente.

Criterios de aceptacion:

* El sistema lista los campos que se van a crear.
* El usuario confirma la creacion antes de modificar la capa.
* El sistema valida nombres duplicados o no permitidos.
* El sistema informa si la capa no permite edicion.

---

### HU-08 Escribir valores IFC en atributos GIS

Como gestor de activos, quiero cargar los valores seleccionados en el feature GIS, para enriquecer el inventario con informacion BIM.

Criterios de aceptacion:

* El sistema escribe los valores en los campos configurados del feature seleccionado.
* El sistema actualiza `ifc_status`.
* El sistema actualiza `ifc_updated_at`.
* Si hay error, el sistema registra el mensaje en `ifc_error`.
* El usuario recibe confirmacion clara del resultado.
* La carga sobre varias features o sobre una capa completa queda fuera del MVP.

---

### HU-09 Usar el complemento en ingles y espanol

Como usuario del complemento, quiero poder usar toda la interfaz en ingles o espanol, para trabajar en el idioma requerido por mi entorno.

Criterios de aceptacion:

* Todos los textos visibles del MVP son traducibles.
* El complemento carga traducciones ingles/espanol.
* No hay textos visibles hardcodeados en dialogs, docks, menus ni mensajes.
* Los textos del visor que formen parte de la UI del plugin tambien estan traducidos.

---

### HU-10 Instalar y validar el complemento desde el repositorio

Como administrador del complemento, quiero una estructura de repositorio clara y empaquetable, para instalar el plugin en QGIS y mantenerlo en GitHub.

Criterios de aceptacion:

* La carpeta instalable es `geoifcassets/`.
* El ZIP de distribucion no incluye `docs/`, `tests/`, `rules/`, `scripts/` ni `.github/`.
* Existen instrucciones iniciales de instalacion.
* Existen scripts iniciales para validar y empaquetar.

---

### HU-11 Consultar el estado de los flujos ejecutados

Como usuario del complemento, quiero recibir mensajes claros sobre las operaciones realizadas, para saber si el flujo se ha completado correctamente o si debo corregir algo.

Criterios de aceptacion:

* El sistema registra mensajes para el usuario durante los flujos principales.
* Los mensajes de usuario estan disponibles en ingles y espanol.
* Los errores tecnicos no muestran stack traces al usuario final.
* El sistema registra developer logs para diagnostico.
* El codigo del plugin no usa `print()` como mecanismo normal de logging.

---

### HU-12 Visualizar un IFC y crear o enriquecer una capa GIS sin capa previa

Como tecnico GIS que acaba de arrancar el complemento sin una capa GIS de activos, quiero abrir un IFC directamente y generar o enriquecer una capa GIS a partir del resultado, para iniciar el flujo de inventario sin necesidad de preparar una capa previa.

Criterios de aceptacion:

* El usuario puede abrir un fichero IFC directamente desde el panel del complemento, sin necesidad de tener una capa GIS cargada.
* El visor IFC se abre con el fichero seleccionado y se muestran las metricas del modelo.
* El usuario puede crear una capa de memoria temporal (puntual, lineal o poligonal) con los campos minimos `ifc_file` e `ifc_url`. Tras confirmar el dialogo, el complemento activa la herramienta de digitalizacion de QGIS para que el usuario dibuje la geometria en el lienzo.
* El usuario puede generar una huella geografica a partir de una planta del IFC (HU-E04) cuando el modelo esta georreferenciado. La capa de huella incluye el campo `ifc_url` para que sea reconocida por el combo de capas del complemento.
* El usuario puede anadir un nuevo registro a una capa GIS existente. Tras confirmar el dialogo, el complemento activa la digitalizacion. Al terminar de dibujar, los campos `ifc_path` o `ifc_url` e `ifc_file` se rellenan automaticamente si existen en la capa destino.
* Los botones de accion ("New temp layer…" y "Add to existing layer…") se habilitan cuando hay un IFC cargado en el visor, tanto si se abrio via "Browse IFC file…" como si se abrio desde un feature GIS.
* Todos los mensajes del flujo son traducibles a ingles y espanol.

---

## 7.3 Historias evolutivas

### HU-E01 Guardar un mapeo reutilizable

Como tecnico GIS, quiero guardar una seleccion de propiedades y campos de destino, para repetir una carga similar sin configurar todo desde cero.

---

### HU-E02 Crear un perfil sectorial desde mapeos validados

Como responsable de inventario, quiero convertir mapeos frecuentes en perfiles sectoriales, para estandarizar cargas por tipologia de activo.

---

### HU-E03 Aplicar un perfil sectorial a un activo

Como tecnico GIS, quiero aplicar un perfil sectorial a un feature, para cargar propiedades IFC habituales de forma semiautomatica.

---

### HU-E04 Generar huella geografica de una planta IFC georreferenciada como capa temporal

Como tecnico GIS, quiero seleccionar una planta de un modelo IFC georreferenciado y cargar su geometria 2D como capa temporal en QGIS, para verificar y situar geograficamente una planta concreta del edificio sin importar geometria BIM de forma permanente.

Criterios de aceptacion:

**Deteccion de georreferenciacion:**

* El sistema detecta si el IFC abierto contiene georreferenciacion completa mediante `IfcMapConversion` e `IfcCoordinateReferenceSystem` (IFC4+).
* Si no existe `IfcMapConversion` o no se puede identificar un CRS valido, el sistema informa al usuario con un mensaje claro y no genera la capa.
* Si solo existe `IfcSite.RefLatitude`/`RefLongitude` sin `IfcMapConversion`, el sistema advierte de la limitacion y no procede.

**Seleccion de planta:**

* El sistema lee los elementos `IfcBuildingStorey` del modelo y presenta al usuario una lista de plantas disponibles, ordenadas por elevation.
* Cada entrada de la lista muestra el nombre del `IfcBuildingStorey` y su cota de referencia cuando este disponible.
* El usuario selecciona una planta de la lista antes de generar la capa.
* Si el modelo no contiene `IfcBuildingStorey`, el sistema informa al usuario y no genera la capa.

**Generacion de geometria:**

* El sistema obtiene los elementos `IfcSlab` contenidos en el `IfcBuildingStorey` seleccionado mediante `IfcRelContainedInSpatialStructure`.
* Si el storey no contiene `IfcSlab`, el sistema usa todos los elementos del storey como fallback e informa al usuario de esta situacion.
* El sistema extrae la geometria 3D de los elementos seleccionados usando IfcOpenShell con coordenadas de mundo (`USE_WORLD_COORDS`).
* El sistema proyecta los vertices al plano XY (descarta Z) y calcula la union de las geometrias resultantes.
* Si la union produce una geometria no valida o vacia, el sistema informa al usuario y no genera la capa.

**Transformacion de coordenadas:**

* El sistema aplica la transformacion de `IfcMapConversion` (Eastings, Northings, OrthogonalHeight, rotacion, escala) usando `ifcopenshell.util.geolocation`.
* El CRS de la capa generada corresponde al identificado en `IfcCoordinateReferenceSystem` del modelo.

**Capa QGIS:**

* El sistema crea una capa de memoria en QGIS de tipo **MultiPolygon** con el CRS detectado.
* La capa contiene un unico feature por planta con la geometria unificada en un MultiPolygon (incluso si la union produce un unico recinto) y los atributos: nombre del storey, nombre del fichero IFC y CRS identificado.
* Usar MultiPolygon garantiza que haya exactamente un registro por planta aunque la union produzca recintos disjuntos (p.ej. edificios separados en la misma planta).
* La capa se denomina "IFC Floor — <nombre_storey> — <nombre_fichero>" y se anade automaticamente al proyecto QGIS activo.
* La capa es temporal y no persiste entre sesiones de QGIS.
* Se puede generar una nueva capa para una planta diferente sin eliminar las anteriores.

**Operacion y feedback:**

* La operacion se lanza desde el panel del complemento cuando hay un IFC abierto en el visor.
* El sistema registra en developer logs el CRS detectado, el storey seleccionado, el numero de elementos procesados y el resultado de la transformacion.
* El sistema muestra mensajes de usuario al completar la operacion o al informar de cualquier limitacion o error.
* Los mensajes de usuario estan disponibles en ingles y espanol.

Restricciones tecnicas:

* La deteccion de georreferenciacion y la lectura de storeys y geometria se implementan en `adapters/ifc/`.
* La creacion de la capa temporal y el selector de planta se implementan en `adapters/qgis/`.
* No se importa geometria IFC como capa GIS permanente.
* Se usa `ifcopenshell.util.geolocation` para la transformacion de coordenadas.
* Se usa `shapely` para la union de geometrias (disponible en el entorno QGIS).
* No se importa `shapely` ni `IfcOpenShell` desde codigo del nucleo (`core/`).
* La operacion no bloquea la interfaz de QGIS; si el modelo es grande, debe ejecutarse con feedback de progreso o en un hilo separado.

Condicion de activacion:

* Requiere que el IFC este abierto en el visor embebido (HU-02 completada).
* Se activa solo cuando el IFC tiene georreferenciacion completa via `IfcMapConversion`.
* Esta historia es evolutiva y no forma parte del MVP. Se implementa tras validar el flujo manual de propiedades (HU-05 a HU-08).

Diseno de integracion con el selector de plantas existente:

* El selector de plantas del visor (storey bar) ya existe en TypeScript (Phase D). Al pulsar una planta,
  el visor JS notifica a Python mediante `POST /transfer` con `{"type": "storey_selected", "storey_id": N, "storey_name": "..."}`.
  Al pulsar All, notifica con `storey_id: null`.
* El endpoint `/transfer` ya existe en `IfcHttpServer`. No se requiere infraestructura IPC nueva.
* `GeoIfcAssetsPlugin._handle_transfer` despacha el nuevo tipo para actualizar `_active_storey`.
* El boton "Generar planta en QGIS" aparece en la barra inferior del visor tab del dock, habilitado
  solo cuando hay una planta activa y el IFC es un fichero local.
* La extraccion de geometria se realiza en el proceso QGIS via IfcOpenShell (independiente de web-ifc).
* Modulos nuevos: `adapters/ifc/footprint_extractor.py` (logica IFC pura) y
  `adapters/qgis/footprint_layer.py` (creacion de capa QGIS).

---

# 8. Casos de uso

## CU-1 Asociacion IFC

* seleccionar capa vectorial de trabajo
* validar existencia de `ifc_path` o `ifc_url`
* validar valor IFC del feature seleccionado

---

## CU-2 Visualizacion IFC

* apertura desde feature seleccionado
* apertura desde panel del complemento
* accion de capa como acceso recomendado cuando sea viable
* visor embebido en QGIS
* navegacion del modelo

---

## CU-3 Consulta de propiedades

* lectura de GlobalId
* clases IFC
* Property Sets
* Quantity Sets disponibles

---

## CU-4 Seleccion de propiedades IFC

* seleccion de una o varias propiedades
* revision de valores
* confirmacion de propiedades a cargar en GIS

---

## CU-5 Mapeo a campos GIS

* seleccion de campo existente
* creacion de campo nuevo
* validacion de tipo de dato
* confirmacion antes de escribir

---

## CU-6 Actualizacion de inventario GIS

* escritura de resultados en campos del feature seleccionado
* registro de estado de procesamiento
* notificacion de errores al usuario

---

## CU-7 Gestion de logs

* registro de developer logs
* registro de user logs
* trazabilidad por operacion
* mensajes traducibles para usuario final
* diagnostico tecnico sin uso de `print()`

---

# 9. Arquitectura de extraccion

## 9.1 Modelo conceptual

```text id="extract_flow"
IFC
  |
Lector IFC (IfcOpenShell)
  |
Propiedades seleccionadas
  |
Campos GIS
```

---

## 9.2 Tipos de extraccion del MVP

* Propiedad directa
* Atributo basico IFC
* Property Set
* Quantity Set existente

No se incluyen calculos derivados ni reglas sectoriales en el MVP.

---

# 10. Modelo de datos de capa GIS

## 10.1 Campos minimos

```text id="layer_fields"
ifc_path o ifc_url
ifc_status
ifc_error
ifc_updated_at
```

El MVP obliga a que la capa contenga al menos uno de los campos `ifc_path` o `ifc_url`.

`ifc_globalid` no es un campo minimo del MVP. Puede incorporarse como campo opcional o evolutivo si se decide persistir una relacion granular con elementos IFC.

---

## 10.2 Campos de resultados

Los campos de salida se definen por seleccion del usuario. El complemento debe:

* comprobar si existen antes de escribir
* proponer su creacion cuando falten
* inferir un tipo de dato razonable
* permitir confirmacion manual del tipo
* evitar sobrescribir campos no confirmados por el usuario

---

# 11. Estructura del proyecto

El repositorio debe diferenciar claramente la carpeta instalable del plugin QGIS del resto de carpetas de soporte para desarrollo, documentacion, pruebas y automatizacion.

```text id="repo_structure"
GeoIFC_Assets/
    geoifcassets/
        metadata.txt
        __init__.py
        main.py
        resources.qrc
        resources.py
        icon.png

        core/
            models.py
            mapping.py
            validation.py

        adapters/
            qgis/
                plugin.py
                dock.py
                feature_reader.py
                messages.py
                i18n.py
                compat.py
            ifc/

        services/
            logging.py

        webviewer/
            index.html
            assets/
            js/

        i18n/
            geoifcassets_en.ts
            geoifcassets_es.ts
            geoifcassets_en.qm
            geoifcassets_es.qm

    docs/
        plan_desarrollo.md
        arquitectura.md
        manual_usuario.md
        instalacion.md
        ciclo_vida_desarrollo.md
        compatibilidad_qgis.md
        gestion_logs.md
        references/
            ifc/
                README.md
                versions.md
                sources.md
                properties_and_quantities.md
                ifc_gis_mapping.md
                IFC2X3_TC1/
                    README.md
                IFC4_ADD2_TC1/
                    README.md
                IFC4X3_ADD2/
                    README.md
        decisiones/

    tests/
        unit/
        integration/
        qgis/
        fixtures/
            ifc/

    rules/
        agentic_development_rules.md
        coding_style.md
        architecture_rules.md
        qgis_plugin_rules.md
        i18n_rules.md
        qgis_compatibility_rules.md
        logging_rules.md

    .agents/
        README.md
        context/
            project_brief.md
            mvp_scope.md
        templates/
            task_brief.md
            review_checklist.md

    .cursor/
        rules/
            00-project-overview.mdc
            10-architecture.mdc
            20-qgis-compatibility.mdc
            30-i18n.mdc
            35-logging.mdc
            40-agent-workflow.mdc

    scripts/
        package_plugin.ps1
        run_tests.ps1
        lint.ps1
        update_translations.ps1
        compile_translations.ps1
        validate_qgis3.ps1
        validate_qgis4.ps1

    examples/
        sample_projects/
        sample_ifc/
        sample_layers/

    .github/
        workflows/

    README.md
    README.es.md
    AGENTS.md
    CLAUDE.md
    CHANGELOG.md
    LICENSE
    pyproject.toml
    .editorconfig
    .gitignore
```

---

## 11.1 Carpeta del plugin QGIS

La carpeta `geoifcassets/` es la unica carpeta que debe instalarse o empaquetarse como complemento QGIS.

Debe contener:

* `metadata.txt` del complemento
* punto de entrada Python del plugin
* codigo fuente del complemento
* recursos Qt
* visor web embebido
* iconos y assets necesarios en ejecucion
* archivos de traduccion compilados necesarios para la interfaz

No debe contener:

* documentacion interna del repositorio
* tests
* reglas de desarrollo
* scripts de automatizacion
* datos de ejemplo pesados
* configuracion de CI

---

## 11.2 Carpetas de soporte del repositorio

La carpeta `docs/` contiene documentacion de producto, arquitectura, uso y referencias tecnicas en espanol. No es necesario mantener una copia completa de la documentacion en ingles.

Los documentos de referencia del proyecto deben vivir dentro de `docs/references/`. La base documental IFC-BIM versionada debe ubicarse en `docs/references/ifc/`.

La carpeta `tests/` contiene pruebas unitarias, integracion y fixtures. Las pruebas de QGIS deben quedar separadas porque requieren entorno QGIS. Los fixtures IFC usados por tests deben estar en `tests/fixtures/ifc/`; la documentacion de referencia IFC debe estar en `docs/references/ifc/`.

La carpeta `rules/` contiene reglas internas para mantener consistencia durante el desarrollo: estilo de codigo, arquitectura, estructura del plugin, convenciones de mapeo IFC-GIS, internacionalizacion, compatibilidad QGIS 3/4, gestion de logs y trabajo con agentes.

La carpeta `.agents/` contiene contexto y plantillas auxiliares para asistentes agenticos.

La carpeta `.cursor/` contiene reglas especificas para Cursor.

Los archivos `AGENTS.md` y `CLAUDE.md` contienen instrucciones de alto nivel para Codex, Claude y otros agentes compatibles.

La carpeta `scripts/` contiene comandos reproducibles para empaquetar, probar, validar el complemento, actualizar traducciones y comprobar compatibilidad QGIS 3/4.

La carpeta `examples/` contiene proyectos, capas e IFC de ejemplo. Si los archivos IFC son grandes, deben gestionarse con cuidado para no cargar el repositorio.

La carpeta `.github/` contiene automatizaciones de GitHub, como lint, tests y empaquetado.

---

## 11.3 Criterio de empaquetado

El paquete distribuible del complemento debe incluir solo:

```text id="plugin_package"
geoifcassets/
    metadata.txt
    __init__.py
    main.py
    resources.py
    icon.png
    core/
    adapters/
    services/
    webviewer/
    i18n/
```

El ZIP final para QGIS no debe incluir `docs/`, `tests/`, `rules/`, `scripts/`, `.github/`, `.cursor/`, `.agents/` ni archivos propios del repositorio.

---

# 12. Flujos Funcionales Candidatos

La arquitectura ligera no exige crear un caso de uso por cada flujo. Estos nombres sirven como referencia funcional, no como obligacion de estructura:

* validar capa con `ifc_path` o `ifc_url`
* abrir visor IFC
* leer propiedades IFC
* seleccionar propiedades IFC
* mapear propiedades a campos GIS
* actualizar atributos GIS
* registrar logs de flujo

Evolutivo:

* crear perfil sectorial desde mapeo
* aplicar perfil sectorial

---

# 13. Estrategia de desarrollo

## Fase 1 - Base del complemento

* estructura del repositorio preparada para GitHub
* separacion entre carpeta instalable del plugin y carpetas de soporte
* documento inicial de ciclo de vida del desarrollo
* documento inicial de compatibilidad QGIS 3/4
* documento inicial de gestion de logs
* instrucciones iniciales para desarrollo agentico
* estructura base del plugin QGIS
* adaptadores iniciales `adapters/qgis/`
* servicio inicial `services/logging.py`
* carga del complemento
* configuracion de dependencias
* menu, toolbar y dock inicial
* infraestructura inicial de traducciones ingles/espanol
* scripts iniciales de validacion y empaquetado
* scripts iniciales de actualizacion y compilacion de traducciones
* scripts iniciales de validacion QGIS 3 y QGIS 4
* reglas iniciales de arquitectura y estilo
* reglas iniciales de internacionalizacion
* reglas iniciales de compatibilidad QGIS 3/4
* reglas iniciales de logging y prohibicion de `print()` en plugin
* reglas iniciales para Codex, Cursor y Claude

---

## Fase 2 - MVP con visor IFC y carga manual de propiedades

* asociacion IFC <-> feature GIS
* validacion de capa con `ifc_path` o `ifc_url`
* apertura de IFC desde feature seleccionado
* accion de capa para abrir el visor cuando sea viable en QGIS 3 y QGIS 4
* visor embebido funcional
* comprobacion controlada de Qt WebEngine en QGIS 3 y QGIS 4
* consulta basica de propiedades
* seleccion multiple de propiedades IFC
* mapeo de propiedades a campos GIS
* creacion controlada de campos
* escritura de valores en atributos GIS
* carga limitada al feature seleccionado
* interfaz completa del MVP traducida a ingles y espanol
* developer logs y user logs de los flujos principales

---

## Fase 3 - Calidad y empaquetado

* tests unitarios del dominio
* tests de casos de uso
* pruebas manuales en QGIS LTR
* pruebas manuales en QGIS 3 LTR
* pruebas manuales en QGIS 4.x
* validacion de instalacion
* documentacion de uso
* revision de textos traducibles
* validacion de traducciones ingles/espanol
* validacion de compatibilidad QGIS 3/4
* validacion de logs y ausencia de `print()` en codigo del plugin
* documentacion inicial en espanol
* README disponible en ingles y espanol

---

## Fase 4 - Evolutivo: perfiles sectoriales

* convertir mapeos frecuentes en perfiles
* definir perfiles por tipologia de activo
* permitir aplicar un perfil a un feature
* reutilizar configuraciones validadas por usuarios

---

# 14. Criterio de exito del MVP

GeoIFC Assets sera exitoso en su MVP si permite:

1. Seleccionar una capa GIS que contenga `ifc_path` o `ifc_url`.
2. Abrir el IFC del feature seleccionado en un visor embebido dentro de QGIS.
3. Seleccionar un elemento IFC y consultar sus propiedades.
4. Elegir una o varias propiedades IFC.
5. Mapear cada propiedad seleccionada a un campo GIS.
6. Crear campos GIS cuando el usuario lo confirme.
7. Escribir los valores seleccionados en atributos GIS del feature seleccionado.
8. Usar la interfaz completa del MVP en ingles y espanol.
9. Cargar y ejecutar el flujo MVP en QGIS 3 LTR y QGIS 4.x.
10. Registrar developer logs y user logs de los flujos principales.
11. No usar `print()` como mecanismo normal de diagnostico del plugin.
12. Mantener el IFC como fuente externa sin importar geometria al SIG.

---

# 15. Resultado final esperado

GeoIFC Assets sera un complemento QGIS que conecta activos GIS con modelos IFC para:

```text id="final"
activos territoriales + visor IFC + atributos GIS enriquecidos desde BIM
```

sin necesidad de replicar el modelo BIM dentro del SIG.

---

# 16. Estado de implementacion (2026-06-24, actualizado tras commits 585b451 / 9601bfe)

## 16.1 Resumen por fase

| Fase | Descripcion | Estado |
|------|-------------|--------|
| Fase 1 | Base del complemento | Completa |
| Fase 2 | MVP visor IFC + carga manual | ~90 % (pendiente: compilar .qm, Quantity Sets en visor JS) |
| Fase 3 | Calidad y empaquetado | ~40 % (tests unitarios presentes; faltan integracion, QGIS y documentacion) |
| Fase 4 | Perfiles sectoriales | No iniciada |

---

## 16.2 Estado por historia de usuario MVP

| HU | Titulo | Estado | Observaciones |
|----|--------|--------|---------------|
| HU-01 | Validar la capa GIS de trabajo | Completa | Selector de capa y feature en dock; validacion de `ifc_path` / `ifc_url`; mensajes de error claros. |
| HU-02 | Abrir el IFC en visor embebido | Completa | Subproceso `webviewer_app.py` + SwiftShader + polling HTTP. El subproceso se lanza de forma lazy al seleccionar el primer feature (no al abrir el panel). Seleccionar un feature activa automaticamente la pestana IFC Viewer. La accion de capa QGIS no esta implementada (aplazada). |
| HU-03 | Seleccionar un elemento IFC | Completa | Arbol por categoria (Fase A), arbol espacial (Fase B), ray-casting 3D, zoom de camara al elemento seleccionado. |
| HU-04 | Consultar propiedades BIM | Parcial | Atributos directos y PropertySets mostrados en el panel del visor. Extractores Python `model_info_extractor.py` y `quantity_extractor.py` implementados. Panel de metricas de modelo en el dock aun no conectado (HU-04-B pendiente). |
| HU-05 | Seleccionar propiedades para cargar en GIS | Parcial | Transferencia propiedad a propiedad con boton `->` (elementos IFC individuales). Nueva fuente de datos: metricas agregadas de modelo (metadatos + cantidades). Panel de seleccion de metricas en el dock pendiente. |
| HU-06 | Mapear propiedades IFC a campos GIS | Completa | Dialogo BIM->GIS con campo existente o campo nuevo (Fase C: POST /transfer + QDialog + `changeAttributeValue`). |
| HU-07 | Crear campos GIS controladamente | Completa | El dialogo de transferencia solicita confirmacion antes de crear el campo. |
| HU-08 | Escribir valores IFC en atributos GIS | Completa | Escritura del valor funcional. `ifc_status`, `ifc_updated_at` e `ifc_error` se actualizan automaticamente si existen en la capa; se omiten sin error si no existen. |
| HU-09 | Usar el complemento en ingles y espanol | Parcial | Todos los textos usan `tr()`. Archivos `.ts` en ingles y espanol presentes. Archivos `.qm` compilados ausentes — las traducciones no estan activas en QGIS. |
| HU-10 | Instalar y validar el complemento | Completa | Estructura de repositorio correcta, `metadata.txt`, scripts de empaquetado presentes. |
| HU-11 | Consultar el estado de los flujos | Completa | Log de usuario en dock (QTextEdit). Developer logs via `PluginLogger`. Sin `print()` en el plugin distribuible. |
| HU-12 | Visualizar IFC y crear capa GIS sin capa previa | Completa | Boton "Browse IFC file…" en tab Layer/Features. Barra de acciones en tab IFC Viewer: "New temp layer…" (Point/Line/Polygon, digitaliza con valores por defecto pre-rellenos) y "Add to existing layer…" (signal `featureAdded` rellena campos IFC tras el dibujo). Capa de huella incluye `ifc_url`. |

---

## 16.3 Estado por historia de usuario evolutiva

| HU | Titulo | Estado | Observaciones |
|----|--------|--------|---------------|
| HU-E01 | Guardar un mapeo reutilizable | No iniciada | |
| HU-E02 | Crear un perfil sectorial desde mapeos validados | No iniciada | |
| HU-E03 | Aplicar un perfil sectorial a un activo | No iniciada | |
| HU-E04 | Generar huella geografica de planta IFC | Completa | Implementada antes del MVP. `footprint_extractor.py` y `footprint_layer.py`. Deteccion de `IfcMapConversion`, transformacion de coordenadas via `ifcopenshell.util.geolocation`, capa temporal en QGIS de tipo **MultiPolygon** con reproyeccion al CRS del proyecto. Un unico feature por planta; la union de recintos disjuntos se preserva como MultiPolygon. Dialogo manual de CRS si el IFC carece de `IfcMapConversion`. |

---

## 16.4 Modulos implementados

| Modulo | Ruta | Descripcion |
|--------|------|-------------|
| Plugin principal | `adapters/qgis/plugin.py` | Punto central: inicializacion, dock, visor, transferencia BIM->GIS, huella IFC. Flujo sin capa GIS previa: `_browse_ifc_file`, `_show_create_temp_layer_dialog`, `_show_add_to_layer_dialog`. |
| Dock principal | `adapters/qgis/dock.py` | Tabs GeoIFC y Properties. Tab GeoIFC: Browse IFC file, selector de capa y feature, estado del visor IFC, barra de planta/huella, botones New temp layer / Add to existing layer. Tab Properties: metricas de modelo y log de usuario. La antigua pestaña IFC Viewer fue eliminada; sus controles se integraron en GeoIFC. |
| Visor IFC | `adapters/qgis/viewer.py` | `IfcViewerDock`: QProcess + HTTP server local + polling `/current.json` + cola de transferencias. SwiftShader via `_ensure_swiftshader_flag`. Subproceso lazy: se lanza en el primer `open_reference()`, no en `__init__`. |
| Subproceso visor | `webviewer_app.py` | Proceso independiente con `QWebEngineView`. Carga la SPA web-ifc + Three.js. Sirve los ficheros de la SPA e intercambia mensajes con QGIS via HTTP local. |
| SPA web-ifc | `webviewer/` | HTML + bundle Vite (JS + CSS + web-ifc WASM). Renderizado 3D, arbol de elementos (plano y espacial), ray-casting, selector de plantas, boton de transferencia propiedad. Panel redimensionable por arrastre con persistencia `localStorage`. Boton colapsar arbol. Boton Export con menu desplegable: arbol espacial (JSON), categorias (JSON), propiedades del elemento seleccionado (JSON y CSV). Grupos de propiedades colapsables (Attributes, Pset_*, Qto_*) con persistencia del estado por grupo en `localStorage`. |
| Extractor de huella | `adapters/ifc/footprint_extractor.py` | Detecta `IfcMapConversion`, extrae geometria de `IfcBuildingStorey`, aplica transformacion georreferenciada, devuelve WKT siempre como `MULTIPOLYGON` (fuerza envoltorio si `unary_union` produce un `Polygon` simple). |
| Capa de huella | `adapters/qgis/footprint_layer.py` | Crea capa de memoria QGIS de tipo **MultiPolygon** con la huella y la anade al proyecto. Un feature por planta. Incluye campo `ifc_url` (ruta completa) para que la capa sea reconocida por el combo de capas del complemento. |
| Lector IFC | `adapters/ifc/reader.py` | Lee esquema IFC (IFC2x3 / IFC4 / IFC4.3) sin IfcOpenShell completo (parsing ligero del header). |
| Lector de features | `adapters/qgis/feature_reader.py` | Lee `ifc_path` / `ifc_url` del feature seleccionado y resuelve conflictos. |
| Escritor de features | `adapters/qgis/feature_writer.py` | Escribe atributos en la capa GIS. |
| Modelos core | `core/models.py` | `IfcReference`, `IfcReferenceKind`, `IfcModelSummary`, `LayerRequirementResult`, `ModelMetric`, `MetricSource`. |
| Extractor de info de modelo | `adapters/ifc/model_info_extractor.py` | Extrae metadatos de `IfcProject`, `IfcBuilding`, `IfcCoordinateReferenceSystem`, `Pset_BuildingCommon`. Devuelve lista de `ModelMetric`. |
| Extractor de cantidades | `adapters/ifc/quantity_extractor.py` | Cuenta elementos por tipo IFC y suma areas desde `QuantitySet` formales. Fallback con prefijo `ifc_calc_` si el QtoSet esta ausente. Devuelve lista de `ModelMetric`. |
| Logging | `services/logging.py` | `PluginLogger` con developer logs y user logs; sin `print()`. |
| Compat QGIS | `adapters/qgis/compat.py` | Utilidades de compatibilidad QGIS 3 / QGIS 4. |
| i18n | `adapters/qgis/i18n.py` | Funcion `tr()` para textos traducibles. |

---

## 16.5 Tests implementados

| Archivo | Cubre |
|---------|-------|
| `test_logging_service.py` | `PluginLogger` |
| `test_layer_contract.py` | Contrato minimo de capa (`ifc_path` / `ifc_url`) |
| `test_mapping.py` | Logica de mapeo de propiedades |
| `test_qgis_feature_writer.py` | Escritura de atributos GIS |
| `test_qgis_messages.py` | Servicio de mensajes QGIS |
| `test_ifc_reader.py` | Lector ligero de IFC header |
| `test_viewer_script.py` | Script de subproceso del visor |
| `test_qgis_feature_reader.py` | Lector de referencias IFC desde features |
| `test_feature_label.py` | Generacion de etiqueta de feature |

Sin tests de integracion ni tests con entorno QGIS real aun.

---

## 16.6 Pendientes prioritarios para cerrar el MVP

1. **Compilar archivos .qm** — ejecutar `scripts/compile_translations.ps1` y verificar carga correcta en QGIS para activar traducciones EN/ES (HU-09).
2. ~~**Campos ifc_status / ifc_updated_at**~~ — Completado. `build_status_updates` en `core/mapping.py` + `_apply_status_updates` en `plugin.py` (HU-08).
3. ~~**Panel de metricas de modelo**~~ — Completado. `model_info_extractor.py` + `quantity_extractor.py` + tabla de metricas en dock (`set_model_metrics`) + boton → por metrica (HU-04/HU-05).
4. **Quantity Sets en el visor JS** — verificar que el visor web muestra Quantity Sets y que el boton `->` de elementos individuales funciona para ellos (HU-04).
5. **Tests de integracion** — al menos un test de integracion con fixture IFC real para la extraccion de propiedades y la huella geografica (Fase 3).
6. **Documentacion de usuario** — `docs/manual_usuario.md` y `docs/instalacion.md` no existen aun (Fase 3).

---

## 16.7 Decisiones tecnicas relevantes ya registradas

Los ADRs del proyecto estan documentados en `docs/adrs_geoifc.md`:

* ADR-001: Relacion GIS <-> IFC via campo `ifc_path` / `ifc_url`.
* ADR-008: Visor IFC en subproceso separado con SwiftShader y polling HTTP.
* ADR-009: Embedding de la ventana del subproceso en el dock QGIS.
* ADR-010: Fases A-B-C del visor (arbol plano, arbol espacial, transferencia BIM->GIS).

La logica de accion de capa QGIS queda aplazada; el flujo desde el selector de features del dock es suficiente para el MVP.
