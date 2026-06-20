# GeoIFC Assets

## Plan de Desarrollo y Arquitectura Tecnica (v3.9)

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

Aplicar arquitectura hexagonal (Puertos y Adaptadores).

```text id="arch_hex"
presentation
    dialogs
    docks
    controllers

application
    use_cases
    dto

domain
    entities
    services
    repositories
    value_objects

infrastructure
    qgis
    ifc
    logging
    storage
    webviewer
```

---

## 1.2 Principios de desarrollo

* Clean Code
* SOLID
* DRY
* KISS
* Dependency Injection
* Arquitectura orientada a casos de uso
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

* Qt WebEngine
* QWebChannel
* HTML / JavaScript

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
* aislar diferencias de API en `infrastructure/qgis/compat/`
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
    ifc_url / ifc_path
    ifc_globalid opcional
```

---

## 2.2 Relacion principal

```text id="rel_1"
1 Feature GIS <-> 1 IFC
```

El IFC es fuente de datos y visualizacion, no geometria GIS importada.

En el MVP, la relacion puede resolverse de dos formas:

* El feature apunta a un IFC completo mediante `ifc_path` o `ifc_url`.
* El feature apunta a un elemento concreto del IFC mediante `ifc_globalid`, cuando el usuario quiera persistir esa asociacion.

---

## 2.3 Seleccion manual de propiedades

En la primera version, el usuario decide que informacion BIM quiere pasar a GIS:

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
* renderizado 3D en visor embebido
* navegacion del modelo
* seleccion de entidades IFC
* consulta de propiedades del elemento seleccionado

Tecnologias:

* Qt WebEngine
* That Open Engine
* QWebChannel

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
2. Feature contiene ifc_path o ifc_url
3. Sistema abre el IFC asociado en el visor embebido
4. Usuario selecciona un elemento IFC o consulta propiedades del modelo
5. Usuario marca una o varias propiedades IFC
6. Usuario asigna cada propiedad a un campo GIS
7. Sistema valida tipos y campos de destino
8. Sistema escribe los valores en atributos GIS
9. Sistema registra developer logs y user logs del flujo
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

### HU-01 Asociar un IFC a un activo GIS

Como tecnico GIS, quiero asociar una ruta o URL IFC a un feature GIS, para vincular el activo territorial con su modelo BIM de referencia.

Criterios de aceptacion:

* El usuario puede seleccionar un feature de una capa activa.
* El usuario puede informar `ifc_path` o `ifc_url`.
* El sistema valida que el recurso existe o que la URL tiene formato valido.
* El sistema guarda la asociacion en atributos de la capa.
* El sistema informa errores de forma comprensible.

---

### HU-02 Abrir el IFC asociado en un visor embebido

Como gestor de activos, quiero abrir el IFC asociado al feature seleccionado dentro de QGIS, para revisar el modelo sin salir del entorno GIS.

Criterios de aceptacion:

* El sistema lee el IFC asociado al feature seleccionado.
* El visor se abre dentro de QGIS.
* El usuario puede navegar el modelo 3D.
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

* El sistema escribe los valores en los campos configurados.
* El sistema actualiza `ifc_status`.
* El sistema actualiza `ifc_updated_at`.
* Si hay error, el sistema registra el mensaje en `ifc_error`.
* El usuario recibe confirmacion clara del resultado.

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

* La carpeta instalable es `plugin/geoifc_assets/`.
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

# 8. Casos de uso

## CU-1 Asociacion IFC

* asignar ruta o URL IFC a un feature GIS
* validar existencia y accesibilidad del recurso

---

## CU-2 Visualizacion IFC

* apertura desde capa GIS
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

* escritura de resultados en campos de la capa
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
ifc_path
ifc_url
ifc_globalid
ifc_status
ifc_error
ifc_updated_at
```

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
    plugin/
        geoifc_assets/
            metadata.txt
            __init__.py
            main.py
            resources.qrc
            resources.py
            icon.png

            domain/
                entities/
                services/
                repositories/
                value_objects/

            application/
                use_cases/
                dto/

            infrastructure/
                qgis/
                    compat/
                ifc/
                logging/
                storage/
                webviewer/

            presentation/
                dialogs/
                docks/
                controllers/

            webviewer/
                index.html
                assets/
                js/

            i18n/
                geoifc_assets_en.ts
                geoifc_assets_es.ts
                geoifc_assets_en.qm
                geoifc_assets_es.qm

    docs/
        plan_desarrollo.md
        arquitectura.md
        manual_usuario.md
        instalacion.md
        ciclo_vida_desarrollo.md
        compatibilidad_qgis.md
        gestion_logs.md
        decisiones/

    tests/
        unit/
        integration/
        qgis/
        fixtures/

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

La carpeta `plugin/geoifc_assets/` es la unica carpeta que debe instalarse o empaquetarse como complemento QGIS.

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

La carpeta `docs/` contiene documentacion de producto, arquitectura y uso en espanol. No es necesario mantener una copia completa de la documentacion en ingles.

La carpeta `tests/` contiene pruebas unitarias, integracion y fixtures. Las pruebas de QGIS deben quedar separadas porque requieren entorno QGIS.

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
geoifc_assets/
    metadata.txt
    __init__.py
    main.py
    resources.py
    icon.png
    domain/
    application/
    infrastructure/
    presentation/
    webviewer/
    i18n/
```

El ZIP final para QGIS no debe incluir `docs/`, `tests/`, `rules/`, `scripts/`, `.github/`, `.cursor/`, `.agents/` ni archivos propios del repositorio.

---

# 12. Casos de uso de arquitectura

* AssociateIfcToFeatureUseCase
* OpenIfcViewerUseCase
* ReadIfcPropertiesUseCase
* SelectIfcPropertiesUseCase
* MapIfcPropertiesToFieldsUseCase
* UpdateFeatureAttributesUseCase
* RecordWorkflowLogUseCase

Evolutivo:

* CreateSectorProfileFromMappingUseCase
* ApplySectorProfileUseCase

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
* capa inicial `infrastructure/qgis/compat/`
* capa inicial `infrastructure/logging/`
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
* apertura de IFC desde feature seleccionado
* visor embebido funcional
* comprobacion controlada de Qt WebEngine en QGIS 3 y QGIS 4
* consulta basica de propiedades
* seleccion multiple de propiedades IFC
* mapeo de propiedades a campos GIS
* creacion controlada de campos
* escritura de valores en atributos GIS
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

1. Asociar un IFC a un feature GIS.
2. Abrir el IFC asociado en un visor embebido dentro de QGIS.
3. Seleccionar un elemento IFC y consultar sus propiedades.
4. Elegir una o varias propiedades IFC.
5. Mapear cada propiedad seleccionada a un campo GIS.
6. Crear campos GIS cuando el usuario lo confirme.
7. Escribir los valores seleccionados en atributos GIS.
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
