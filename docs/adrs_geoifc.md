# ADR-001: Modelo de Asociación GIS ↔ IFC

## Estado

Aceptado para el MVP

## Contexto

El complemento GeoIFC Assets tiene como objetivo vincular entidades geográficas gestionadas en QGIS con información procedente de modelos IFC.

Los casos de uso identificados incluyen:

* Asociación de activos SIG con modelos IFC.
* Navegación desde una entidad GIS hacia el modelo BIM.
* Consulta de propiedades IFC.
* Transferencia de atributos IFC a capas GIS.
* Generación de indicadores agregados.
* Soporte futuro para sincronización de datos.
* Compatibilidad con edificios e infraestructuras lineales IFC 4.3.

La decisión arquitectónica principal consiste en determinar cómo representar la relación entre las entidades GIS y los elementos IFC.

---

## Alternativas evaluadas

### Alternativa A: Relación GIS → Archivo IFC

```text
GIS Feature
    └── building.ifc
```

#### Ventajas

* Implementación sencilla.
* Adecuada para un MVP.
* No requiere analizar el contenido IFC en el momento de la asociación.
* No depende de la estabilidad de GUIDs internos del fichero.

#### Inconvenientes

* No permite identificar elementos concretos dentro del fichero.
* Imposibilita sincronización selectiva (a nivel de elemento).
* No escala por sí sola para modelos complejos con múltiples activos por fichero.

---

### Alternativa B: Relación GIS → IFC GUID

```text
GIS Feature
    └── IfcElement GUID
```

#### Ventajas

* Relación precisa.
* Compatible con actualizaciones futuras.
* Permite navegación directa a un elemento concreto.

#### Inconvenientes

* Cada entidad GIS sólo puede asociarse a un elemento IFC.
* Limitada para activos compuestos.
* Depende de la estabilidad del GUID entre regeneraciones del fichero.

---

### Alternativa C: Tabla de relaciones GIS ↔ IFC

```text
GIS Feature
        ↕
Asset Association
        ↕
IfcElement
```

Ejemplo:

| GIS_ID | IFC_GUID  | IFC_CLASS   |
| ------ | --------- | ----------- |
| 1001   | 3hKf72... | IfcBuilding |
| 1001   | 8adY11... | IfcStorey   |
| 1001   | 9llP45... | IfcSpace    |

#### Ventajas

* Relación N:M.
* Escalable.
* Compatible con infraestructuras IFC 4.3.
* Permite activos compuestos.
* Facilita sincronización futura.
* Compatible con modelos federados.

#### Inconvenientes

* Mayor complejidad inicial.
* Requiere analizar el contenido IFC ya en el momento de crear la asociación.

---

## Decisión

Para el **MVP** se adopta la **Alternativa A**: relación GIS → Archivo IFC.

Cada feature GIS se asocia a un fichero IFC completo, sin descomponer ni referenciar elementos individuales dentro de él. La asociación se modela mediante una entidad de dominio simple:

```text
AssetAssociation
```

que vincula:

```text
GIS Feature  ←→  IFC File
```

No existe en el MVP ningún concepto de `IfcElement` individual a nivel de persistencia de la asociación. La selección de elementos dentro del visor (apertura, navegación, inspección de propiedades) ocurre en tiempo de uso, sobre el fichero ya asociado, pero no se persiste como relación granular.

### Razón del cambio de rumbo respecto a la Alternativa C

La Alternativa C (tabla N:M con `IfcElement`) sigue siendo la dirección correcta a medio plazo — soporta activos compuestos, sincronización selectiva y modelos federados — pero introduce complejidad de modelo y de persistencia desde el primer commit, sin que el MVP la necesite todavía para sus casos de uso mínimos (asociar, visualizar, consultar propiedades, mapear atributos puntualmente). Se prioriza entregar un MVP funcional simple y migrar a la Alternativa C cuando el uso real confirme la necesidad de granularidad por elemento.

---

## Modelo conceptual

```text
┌─────────────────┐                    ┌─────────────────┐
│ GIS Feature     │ 1..1          1..1 │ IFC File        │
└────────┬────────┘                    └────────┬────────┘
         │                                       │
         └───────────────────┬───────────────────┘
                              │
                    ┌─────────▼─────────┐
                    │ AssetAssociation  │
                    │ (clave propia)    │
                    └────────────────────┘
```

La cardinalidad GIS Feature ↔ IFC File se deja como **1:1 para el MVP** (una feature, un fichero). No se descarta evolucionar a 1:N (una feature con varios ficheros IFC asociados, por ejemplo distintas disciplinas de un mismo activo) como paso intermedio hacia la Alternativa C, pero esa decisión se posterga.

---

## Riesgos identificados

### Pérdida de trazabilidad granular

Al asociar el fichero completo, no hay forma de saber, desde la persistencia, *qué elemento concreto* del IFC es relevante para esa feature GIS si el fichero contiene múltiples elementos (por ejemplo, un fichero con todo un edificio cuando la feature GIS representa solo una planta). Esto se traslada como limitación conocida del MVP: el usuario debe navegar manualmente dentro del visor para localizar el elemento de interés cada vez.

### Ruta del fichero IFC

La asociación depende de una ruta (absoluta o relativa) al fichero `.ifc`. Si el fichero se mueve, se renombra o el proyecto QGIS se traslada a otra máquina sin mantener la misma estructura de carpetas, la asociación se rompe. Se recomienda usar rutas relativas al proyecto QGIS cuando sea posible, y documentarlo como limitación conocida si no se implementa verificación de integridad en el MVP.

### Migración futura a Alternativa C

Cuando se evolucione hacia la tabla de relaciones (Alternativa C), será necesario un proceso de migración de datos existentes: las asociaciones `Feature → Archivo` deberán convertirse en `Feature → AssetAssociation → IfcElement`, lo cual requerirá idealmente que el usuario revise y seleccione el elemento concreto dentro de cada fichero ya asociado. Este coste de migración se acepta conscientemente a cambio de simplicidad inmediata.

---

## Consecuencias

### Positivas

* Implementación mínima y rápida de entregar.
* No requiere parsear el IFC en el momento de crear la asociación.
* No depende de la estabilidad de GUIDs internos del fichero.
* Reduce el modelo de persistencia a su mínimo viable.

### Negativas

* No permite identificar ni sincronizar elementos concretos dentro de un fichero.
* No soporta de forma nativa activos compuestos (una feature con múltiples elementos IFC diferenciados).
* Requerirá migración de datos cuando se adopte la Alternativa C.
* Hereda el riesgo de ruta de fichero como punto de fallo de la asociación.

---

# ADR-002: Estrategia de Persistencia de Asociaciones

## Estado

Propuesto

## Contexto

El ADR-001 establece que, para el MVP, `AssetAssociation` vincula una feature GIS con un fichero IFC completo (Alternativa A), sin granularidad de elemento. Queda por decidir dónde y cómo se persiste esa entidad, y qué dato identifica de forma estable a la feature GIS del lado GIS de la relación.

Este segundo punto sigue siendo relevante incluso con el modelo simplificado del ADR-001, y no se resuelve solo con la elección de formato de almacenamiento.

---

## Problema: identificación estable de la feature GIS

La opción más directa es referenciar la feature por `layer_id` + `feature_id` (FID interno de QGIS). Esta aproximación es frágil:

* QGIS puede reasignar FIDs internos tras determinadas operaciones de edición.
* Un "Save As" o un cambio de formato de capa (shapefile → GeoPackage, por ejemplo) puede regenerar FIDs.
* Recargar la capa desde otra fuente de datos puede romper la correspondencia FID ↔ entidad real, sin aviso.

### Alternativas para la clave de asociación del lado GIS

**Alternativa A — FID de QGIS.** Sencilla, sin cambios en la capa del usuario. Riesgo de desincronización silenciosa según lo descrito arriba.

**Alternativa B — Campo UUID propio gestionado por el plugin.** El plugin crea (si no existe) un campo `geoifc_uuid` en la capa GIS al asociarla por primera vez, y usa ese valor como clave estable, independiente del FID. Robusta frente a recargas y cambios de formato, pero requiere modificar el esquema de la capa del usuario y gestionar su creación/migración.

## Decisión

Para el MVP se adopta la **Alternativa B**: campo UUID propio (`geoifc_uuid`) como clave de asociación del lado GIS.

Se acepta el coste de modificar el esquema de la capa porque el riesgo de desincronización silenciosa de la Alternativa A es inaceptable para un plugin cuyo propósito central es mantener vínculos persistentes a largo plazo. El plugin debe:

* Verificar si el campo existe antes de crear una asociación; crearlo si falta, con aviso explícito al usuario.
* No reutilizar ni reescribir un `geoifc_uuid` ya asignado.

---

## Decisión: formato de almacenamiento

Persistir las asociaciones mediante una capa auxiliar GeoPackage local para el MVP.

```text
geoifc_associations
```

Campos (simplificados respecto a una versión con granularidad de elemento, conforme a ADR-001 Alternativa A):

| Campo         | Tipo    | Notas                                    |
| ------------- | ------- | ------------------------------------------ |
| id            | INTEGER | Clave propia de AssetAssociation           |
| layer_id      | TEXT    | Identificador de capa QGIS (referencia operativa) |
| geoifc_uuid   | TEXT    | Clave estable de la feature                |
| ifc_file_path | TEXT    | Ruta (preferiblemente relativa al proyecto) al fichero IFC asociado |

No se incluyen `ifc_guid` ni `ifc_class`: al no existir referencia a elemento individual en el MVP (ADR-001), no hay GUID de elemento ni clase IFC que persistir a este nivel. Esos campos se incorporarán cuando se migre a la Alternativa C del ADR-001.

---

## Evolución futura

Permitir, sin modificar el dominio, manteniendo la persistencia aislada en una frontera tecnica cuando aporte valor:

* PostgreSQL/PostGIS.
* GeoPackage corporativo compartido.
* Servicios remotos.

Al evolucionar hacia ADR-001 Alternativa C, esta tabla se ampliará (o se sustituirá por una tabla de relación N:M) incorporando `ifc_guid` e `ifc_class`, con el correspondiente proceso de migración de datos ya señalado en ADR-001.

---

## Consecuencias

### Positivas

* Elimina el riesgo de desincronización silenciosa por FID.
* Persistencia desacoplada del dominio mediante puerto de repositorio.
* Esquema de persistencia mínimo, coherente con el modelo de asociación simplificado del MVP.

### Negativas

* Requiere modificar el esquema de las capas del usuario (creación de campo adicional).
* Necesita lógica de migración/verificación de `geoifc_uuid` en capas ya existentes antes de la adopción del plugin.
* El esquema deberá ampliarse con una migración cuando se adopte la Alternativa C del ADR-001.

---

# ADR-003: Estrategia de Lectura IFC y Soporte por Versión de Esquema

## Estado

Propuesto

## Contexto

Es necesario decidir, por separado:

1. Qué motor de lectura IFC se utiliza.
2. Qué nivel de soporte se ofrece para cada versión/esquema IFC objetivo (IFC2x3, IFC4, IFC4.3), dado que "poder parsear el fichero" y "poder interpretar semánticamente sus entidades" no son lo mismo — especialmente en infraestructura lineal.

---

## Decisión: motor de lectura

Utilizar exclusivamente **IfcOpenShell** como motor IFC.

```text
IfcOpenShell
    ↓
Domain Objects
    ↓
Use Cases
```

### Justificación

* Proyecto maduro, con amplio soporte de versiones IFC.
* Evita mantener múltiples parsers.
* Reduce dependencias externas frente a alternativas (por ejemplo, parsers ad-hoc o librerías JS-only del lado del visor).

---

## Decisión: nivel de soporte por versión de esquema

El soporte declarado se diferencia en dos niveles:

**Nivel 1 — Lectura genérica (atributos, Property Sets, Quantity Sets).**
Soportado de forma equivalente para IFC2x3 TC1, IFC4 ADD2 TC1 e IFC4.3 ADD2/4.3.2.0, vía IfcOpenShell. Es el nivel que cubre el MVP completo (apertura del fichero asociado, visualización, consulta de propiedades, mapeo ad-hoc a campos GIS).

**Nivel 2 — Interpretación semántica de infraestructura lineal IFC 4.3** (`IfcAlignment`, `IfcReferent`, geometría paramétrica basada en `IfcCurve`).
**No incluido en el MVP.** Este nivel es sustancialmente más complejo que la lectura de Property Sets de un `IfcBuilding`: requiere interpretar geometría de alineación paramétrica y su relación con el sistema de referencia espacial del proyecto, lo cual conecta con georreferenciación IFC — explícitamente excluida del MVP según `AGENTS.md`.

Se documenta esta distinción para evitar que, al añadir soporte de "IFC 4.3" en el roadmap, se asuma erróneamente que el Nivel 2 viene incluido por el hecho de que IfcOpenShell pueda parsear el esquema.

Los agentes de desarrollo no deben asumir que una propiedad o entidad existe en todas las versiones soportadas (regla ya establecida en `AGENTS.md`, sección 6).

---

## Consecuencias

### Positivas

* El MVP tiene un nivel de soporte IFC realista y verificable por versión.
* Evita expectativas infladas sobre infraestructura lineal en la fase inicial.

### Negativas

* El soporte de infraestructura lineal IFC 4.3 queda pendiente de un ADR propio cuando se acometa, con su propia evaluación de geometría y georreferenciación.

---

# ADR-004: Gestión de Mapeos de Atributos IFC → GIS

## Estado

Aceptado para el MVP

## Contexto

Es necesario decidir si el mapeo entre propiedades IFC y campos GIS es una configuración reutilizable o una decisión puntual por feature, y dónde se persiste esa configuración.

---

## Decisión

Para el **MVP**, el mapeo se realiza de forma **ad-hoc**, feature por feature: el usuario, en el momento de transferir valores desde el IFC asociado, selecciona qué propiedad(es) IFC quiere transferir y a qué campo GIS de destino, sin que exista una plantilla reutilizable persistida por clase IFC.

```text
Usuario abre el IFC asociado a la feature
    → selecciona propiedad(es) IFC en el visor/inspector
    → indica el campo GIS de destino (existente o nuevo)
    → el plugin escribe el valor en el atributo de la feature
```

No se persiste el mapeo como configuración independiente reutilizable en el MVP. Cada transferencia es una operación puntual.

### Razón del cambio de rumbo respecto a plantillas reutilizables

Una plantilla por clase IFC (`IfcBuilding.Name → nombre`, etc.) sigue siendo la dirección deseable a medio plazo para evitar inconsistencias entre activos del mismo tipo, pero requiere una interfaz de gestión de plantillas (crear, editar, versionar) que no es prioritaria para validar el flujo principal del MVP: asociar, visualizar, inspeccionar y transferir un valor puntual. Se prioriza validar ese flujo básico antes de invertir en el mecanismo de plantillas.

---

## Justificación

Ventajas del enfoque ad-hoc para el MVP:

* Reduce el alcance de implementación inicial (sin gestor de plantillas, sin persistencia adicional de configuración de mapeo).
* Permite validar con usuarios reales qué propiedades IFC son realmente relevantes de transferir, antes de fijar plantillas que podrían no ajustarse al uso real.

Riesgos aceptados conscientemente:

* Posible inconsistencia de nombres de campo GIS entre features similares (un usuario podría llamar `anio_construccion` a una propiedad y otro usuario `anyo_construccion` a la misma propiedad en otra feature).
* Repetición de trabajo: si el usuario transfiere las mismas propiedades para múltiples activos del mismo tipo, debe repetir la selección cada vez.
* Mayor superficie para errores de tipado o de campo inexistente, al no haber validación contra una plantilla predefinida.

---

## Evolución futura

Cuando el uso real confirme patrones de mapeo recurrentes por clase IFC, se evaluará introducir plantillas reutilizables (persistidas, por ejemplo, en una tabla `geoifc_mapping_templates` junto a `geoifc_associations`), sin que ello deba alterar el modelo de asociación definido en ADR-001 ni la persistencia base de ADR-002.

---

## Consecuencias

### Positivas

* Implementación mínima para el MVP; no requiere gestor de plantillas ni esquema de persistencia adicional.
* Permite observar el uso real antes de diseñar plantillas que podrían no ajustarse a las necesidades reales.

### Negativas

* Riesgo de inconsistencia de nombres/tipos de campo entre activos similares.
* Trabajo repetitivo para el usuario en activos del mismo tipo.
* Sin validación automática de mapeos contra una configuración de referencia.

---

# ADR-005: Visor IFC Embebido

## Estado

Propuesto

## Decisión

Diseñar el sistema mediante un puerto abstracto:

```text
IfcViewerPort
```

Implementación inicial validada:

```text
ThatOpenAdapter   (@thatopen/components, bundle Vite offline)
```

Implementaciones futuras contempladas por el puerto, no implementadas:

```text
IfcJsAdapter
ExternalViewerAdapter
```

---

## Justificación

El visor es un detalle de infraestructura. No debe contaminar:

* Casos de uso.
* Dominio.
* Persistencia.

### Condición de validación

El puerto `IfcViewerPort` se considera **estable solo después de validarse con el adaptador `ThatOpenAdapter` funcionando dentro del entorno real de QGIS** (embebido vía el mecanismo de renderizado web disponible en PyQGIS). Definir el contrato del puerto antes de esa validación, basándose únicamente en la API de `@thatopen/components` en abstracto, conlleva riesgo de diseñar una abstracción que no encaje con las limitaciones reales de embeber un visor web dentro de QGIS (comunicación QGIS ↔ webview, ciclo de vida del proceso, paso de selección bidireccional).

Por tanto: el puerto se implementa y se ajusta de forma iterativa junto con `ThatOpenAdapter`; no se fija como contrato cerrado hasta tener una integración funcional end-to-end en QGIS.

---

## Consecuencias

### Positivas

* Permite sustituir el visor sin afectar al núcleo del complemento, una vez validado.
* Evita acoplar casos de uso a la API concreta de `@thatopen/components`.

### Negativas

* El puerto puede requerir ajustes tras la primera integración real; no se debe tratar como API congelada desde el primer commit.

---

# ADR-006: Estrategia de Sincronización Futura

## Estado

Propuesto (post-MVP — fuera de alcance de implementación inmediata)

## Contexto

El MVP no incluye sincronización (excluida explícitamente en `AGENTS.md`). Este ADR fija la **intención** de diseño para no cerrar puertas en ADR-001 a ADR-005, y para dar tratamiento formal al riesgo de ruptura de asociación identificado en ADR-001 (ruta de fichero IFC movida o regenerada).

---

## Decisión

Se adopta como dirección de diseño la **sincronización unidireccional con detección de cambios**, no la reconciliación automática bidireccional, al menos en una primera evolución post-MVP.

### Mecanismo previsto

* Detección de cambios en el fichero IFC mediante hash de contenido (o timestamp como fallback) comparado contra el estado registrado en la última asociación.
* Si el fichero IFC cambió o no se encuentra en la ruta registrada: el plugin marca las `AssetAssociation` afectadas como "pendientes de revisión", sin sobrescribir datos GIS automáticamente.
* La reconciliación (relocalizar el fichero, decidir si el contenido sigue siendo válido) es **asistida por el usuario**, no automática, dado el riesgo de pérdida silenciosa de datos si se automatiza sin supervisión.

### Explícitamente fuera de esta primera evolución

* Sincronización bidireccional (escritura automática desde GIS hacia el modelo IFC).
* Reconciliación automática sin intervención del usuario.
* Sincronización a nivel de elemento individual (depende de migrar a ADR-001 Alternativa C).

---

## Justificación

Automatizar la reconciliación sin supervisión sería razonable solo si la ruta y el contenido del fichero IFC fueran garantizados estables — lo cual, según ADR-001, no se puede asumir en general (ficheros movidos, proyectos trasladados entre máquinas, regeneración de exportaciones). Sincronización unidireccional con marcado de "pendiente de revisión" es la opción que minimiza riesgo de corrupción de datos GIS mientras se mantiene la utilidad de detectar cambios.

---

## Consecuencias

### Positivas

* Da tratamiento explícito al riesgo de ruptura de asociación de ADR-001, en lugar de dejarlo sin resolver indefinidamente.
* No bloquea una futura evolución hacia sincronización bidireccional o a nivel de elemento si se valida que es necesaria y segura.

### Negativas

* Requiere diseño de detección de cambios (hash/timestamp) y una interfaz de "asociaciones pendientes de revisión" que no existe en el MVP — debe presupuestarse como trabajo futuro, no asumirse como gratuito.
* Su alcance real queda limitado mientras ADR-001 se mantenga en la Alternativa A (sin granularidad de elemento).

---

Con estos seis ADR el proyecto tiene definida su arquitectura estratégica para el MVP, con un modelo de asociación y de mapeo deliberadamente simplificados (Alternativa A y mapeo ad-hoc respectivamente) para acelerar la primera entrega funcional, y con el camino de evolución hacia un modelo más granular (tabla N:M, plantillas de mapeo) documentado y no bloqueado por las decisiones actuales.

# ADR-007: Arquitectura Modular Pragmatica

## Estado

Aceptada.

## Contexto

GeoIFC Assets es un complemento de QGIS que debe integrar dependencias externas y dificiles de probar:

* QGIS / PyQGIS
* Qt / PyQt
* IfcOpenShell
* visor web embebido
* traducciones
* logging
* escritura de atributos GIS

En el plan inicial se propuso aplicar arquitectura hexagonal. Esta decision es razonable para aislar dependencias externas, pero aplicada de forma estricta puede introducir demasiadas capas, clases y archivos para un complemento QGIS de escala pequena o media.

El riesgo principal es convertir la arquitectura en una fuente de friccion:

* demasiados saltos para entender un flujo sencillo
* `ports` y `use_cases` sin logica real
* duplicacion de DTOs y estructuras simples
* mayor coste para evolucionar UI y flujos QGIS
* dificultad para mantener el complemento por personas que no participaron en el diseno inicial

## Decision

GeoIFC Assets usara una **arquitectura modular pragmatica inspirada en arquitectura hexagonal**, no una arquitectura hexagonal estricta.

Se mantienen fronteras claras donde aportan valor:

* QGIS debe estar aislado en infraestructura/presentacion.
* Qt/PyQt no debe entrar en dominio.
* IfcOpenShell debe estar aislado en infraestructura IFC.
* La logica pura de mapeo IFC-GIS debe poder probarse sin QGIS.
* Logging, traducciones y compatibilidad QGIS 3/4 deben tener puntos de integracion claros.

Pero no se crearan capas, puertos o casos de uso cuando solo anadan ceremonia.

## Regla practica

Crear una abstraccion solo si cumple al menos una de estas condiciones:

* aisla una dependencia externa relevante
* permite probar logica sin QGIS/Qt/IfcOpenShell
* contiene una regla de negocio o decision funcional
* reduce duplicacion real
* estabiliza una frontera que probablemente cambiara

Evitar una abstraccion si:

* solo pasa datos de A a B
* no contiene logica
* obliga a navegar muchos archivos para entender un flujo simple
* se crea solo para cumplir una plantilla arquitectonica

## Estructura orientativa

La estructura actual puede mantenerse:

```text
geoifcassets/
    domain/
    application/
    infrastructure/
    presentation/
    webviewer/
    i18n/
```

Pero se interpreta de forma ligera:

* `domain/`: solo para conceptos y reglas puras con valor real.
* `application/`: casos de uso cuando coordinan una operacion significativa.
* `infrastructure/`: adaptadores QGIS, IFC, logging, storage y compatibilidad.
* `presentation/`: UI, docks, dialogs y controllers.

No es obligatorio crear `port + use case + DTO` para cada interaccion pequena.

## Criterios por tipo de cambio

### Cambios QGIS

Mantenerlos fuera de `domain/`.

Pueden vivir en:

* `infrastructure/qgis/`
* `presentation/`

Crear puerto solo si la funcionalidad debe probarse sin QGIS o si hay una regla de aplicacion no trivial.

### Cambios IFC

Mantener IfcOpenShell fuera de `domain/`.

La lectura cruda puede vivir en `infrastructure/ifc/`.

La normalizacion o mapeo IFC-GIS puede vivir en `application/` o `domain/` si contiene logica pura.

### Cambios UI

La UI debe poder evolucionar rapido.

Evitar convertir cada boton o widget en un caso de uso si solo dispara una accion directa de interfaz.

### Logging

Mantener una estrategia clara de developer logs y user logs.

No introducir `print()` como diagnostico del plugin.

### Traducciones

Los textos visibles deben pasar por la capa de traduccion, aunque la arquitectura se mantenga ligera.

## Consecuencias

Ventajas:

* menor friccion para evolucionar el plugin
* menos archivos ceremoniales
* mejor legibilidad para flujos simples
* se conserva testabilidad donde importa
* se mantiene aislamiento de QGIS/Qt/IfcOpenShell

Costes:

* requiere criterio tecnico caso a caso
* puede haber menos simetria formal entre modulos
* las reglas deben revisarse en code review para evitar acoplamientos accidentales

## Decision final

La arquitectura hexagonal se mantiene como orientacion, no como dogma.

El objetivo es que el complemento sea:

* mantenible
* facil de entender
* testeable donde aporte valor
* compatible con QGIS 3/4
* preparado para evolucionar hacia visor IFC, mapeo IFC-GIS y perfiles sectoriales

