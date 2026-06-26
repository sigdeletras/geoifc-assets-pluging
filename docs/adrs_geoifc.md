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

**Supersedado por ADR-008.**

La decisión inicial de diseñar un puerto abstracto `IfcViewerPort` e integrar el visor mediante un `QWebEngineView` en proceso quedó invalidada tras validar que QGIS ya inicializa Chromium antes de que el plugin pueda configurar las variables de entorno necesarias para WebGL con software rendering. La arquitectura real implementada se documenta en ADR-008 (subproceso) y ADR-009 (embedding en dock).

---

## Decisión original (referencia histórica)

Diseñar el sistema mediante un puerto abstracto `IfcViewerPort`. Implementación inicial prevista: `ThatOpenAdapter` basado en `@thatopen/components` con bundle Vite offline, embebido en un `QWebEngineView` dentro del proceso QGIS.

## Por qué se descartó

El `QWebEngineView` en proceso comparte el proceso Chromium que QGIS ya ha inicializado. Las variables de entorno `QTWEBENGINE_CHROMIUM_FLAGS` (necesarias para activar SwiftShader y el software renderer de WebGL) solo surten efecto cuando el proceso Chromium arranca por primera vez. Si QGIS ha inicializado ya un `QWebEngineView` (situación habitual en instalaciones con plugins de mapas web), las flags no se aplican y el visor falla con "3D renderer unavailable". Esta limitación no es superable en proceso sin modificar QGIS.

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

---

# ADR-008: Visor IFC mediante Subproceso QProcess con SwiftShader y Polling HTTP

## Estado

Aceptado. Implementado en `geoifcassets/adapters/qgis/viewer.py` y `geoifcassets/webviewer_app.py`.

## Contexto

El MVP requiere un visor IFC 3D interactivo embebido en QGIS (HU-02). La tecnología natural es `QWebEngineView` con una librería JavaScript de renderizado IFC (web-ifc + Three.js). Sin embargo, la integración en proceso presenta una limitación crítica en la práctica:

**El problema del Chromium compartido.** QGIS utiliza `QWebEngineView` internamente (plugins de mapas web, paneles de ayuda). En el momento en que el usuario instala GeoIFC Assets, el proceso Chromium ya ha sido inicializado por QGIS. Las variables de entorno `QTWEBENGINE_CHROMIUM_FLAGS` (necesarias para activar SwiftShader y `--ignore-gpu-blocklist`) solo son leídas por Chromium en el arranque del proceso. Una vez inicializado, ignorar esas flags es imposible sin reiniciar QGIS. El resultado es que el visor en proceso muestra "3D renderer unavailable" o falla al intentar crear el contexto WebGL en hardware que no cumple los requisitos mínimos (GPU virtual, entornos de escritorio remoto, GPUs sin soporte WebGL2).

**Validación empírica.** Se verificó que ejecutar exactamente el mismo código Python en un subproceso separado (con variables de entorno SwiftShader heredadas del proceso QGIS) sí activa SwiftShader y renderiza el modelo correctamente. El subproceso arranca un proceso Chromium fresco que lee las variables antes de inicializarse.

---

## Alternativas evaluadas

### Alternativa A: QWebEngineView en proceso QGIS

```
QGIS proceso
  └── QWebEngineView (Chromium ya inicializado)
        └── index.html + web-ifc + Three.js
```

**Ventajas:** integración directa, comunicación bidireccional por QWebChannel, ciclo de vida sencillo.

**Inconvenientes:** Chromium ya está inicializado cuando el plugin arranca; `QTWEBENGINE_CHROMIUM_FLAGS` no tienen efecto; el visor falla en hardware sin WebGL2 nativo, que es el caso habitual en instalaciones de QGIS sobre escritorio remoto o GPU virtual.

**Descartada** tras validación empírica.

---

### Alternativa B: Subproceso Python con QProcess (ELEGIDA)

```
QGIS proceso (QProcess manager)
  └── python3.exe webviewer_app.py <puerto> <url>
        └── QApplication propia
              └── QWebEngineView (Chromium fresco)
                    └── index.html + web-ifc + Three.js
                          └── fetch http://127.0.0.1:<puerto>/modelo.ifc
```

**Ventajas:**
- Chromium arranca fresco y lee `QTWEBENGINE_CHROMIUM_FLAGS` correctamente.
- SwiftShader activo: el visor funciona con cualquier GPU o sin GPU hardware.
- Aislamiento total de fallos: si el renderer Chromium falla (crash), el subproceso puede recargar la página sin afectar a QGIS.
- El subproceso hereda el entorno del proceso QGIS, incluyendo las flags configuradas por `_ensure_swiftshader_flag()` en `initGui()`.

**Inconvenientes:**
- No se puede usar QWebChannel (requiere el mismo proceso Qt). La comunicación debe pasar por otro mecanismo.
- El ejecutable Python no es `sys.executable` en QGIS (que apunta al binario `qgis-bin.exe`); hay que localizar el intérprete real.
- Latencia de arranque (~1-2 s para que Chromium inicialice).
- El embedding de la ventana en el dock requiere trabajo adicional (ver ADR-009).

---

### Alternativa C: Proceso externo independiente

Lanzar un proceso Python sin gestión por QProcess (p.ej. `subprocess.Popen`), sin embedding.

**Descartada** porque no permite capturar stdout para recibir el `win_id` (necesario para ADR-009) ni gestionar el ciclo de vida del proceso desde QGIS de forma limpia.

---

## Decisión

Se adopta la **Alternativa B**: visor IFC ejecutado como subproceso Python gestionado mediante `QProcess`.

---

## Solución técnica implementada

### 1. Localización del intérprete Python (`_find_python_executable`)

En QGIS, `sys.executable` apunta al binario de QGIS (`qgis-bin.exe`), no al intérprete Python. Pasar ese valor a `QProcess.start()` hace que QGIS interprete los argumentos del subproceso como rutas de capas de datos, generando errores como:

```
CRITICAL: D:\...\webviewer_app.py no es un origen de datos válido
```

La función `_find_python_executable()` busca el intérprete real en orden de prioridad:

```python
candidates = [
    qgis_bin / "python3.exe",        # QGIS Windows (OSGeo4W)
    qgis_bin / "python.exe",         # QGIS Windows alternativo
    Path(sys.prefix) / "python.exe", # prefijo Windows
    Path(sys.prefix) / "bin" / "python3",  # Linux/macOS
    Path(sys.prefix) / "bin" / "python",   # Linux/macOS alternativo
]
```

Si ninguno se encuentra, cae a `which("python3")` o `which("python")`.

### 2. Activación de SwiftShader (`_ensure_swiftshader_flag`)

Se llama en `initGui()`, antes de que se cree ningún widget Qt:

```python
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
    "--enable-unsafe-swiftshader --ignore-gpu-blocklist"
)
```

El subproceso hereda este entorno porque `_launch_subprocess()` construye `QProcessEnvironment` a partir de `os.environ`:

```python
qenv = QProcessEnvironment.systemEnvironment()
for key, value in os.environ.items():
    qenv.insert(key, value)
```

### 3. Punto de entrada del subproceso (`webviewer_app.py`)

Archivo independiente de QGIS (sin imports `qgis.*`). Importa PyQt6 o PyQt5 directamente:

```python
try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    ...
except ImportError:
    from PyQt5.QtWebEngineWidgets import QWebEngineView
    ...
```

Crea su propia `QApplication` con `setQuitOnLastWindowClosed(False)` para que un crash del renderer Chromium no mate el proceso. El cierre iniciado por el usuario se gestiona en el override de `closeEvent`:

```python
class _ViewerWindow(QWebEngineView):
    def closeEvent(self, event):
        event.accept()
        app.quit()
```

### 4. Comunicación QGIS ↔ subproceso: polling HTTP

QWebChannel no es viable entre procesos distintos. Las alternativas consideradas:

| Mecanismo | Motivo de descarte |
|---|---|
| QWebChannel | Requiere el mismo proceso Qt |
| stdin commands | `select()` no funciona en Windows con pipes de QProcess |
| Señales Qt | No cruzan barreras de proceso |
| WebSocket | Demasiada complejidad para el caso de uso |
| **HTTP polling** | **Elegido: simple, robusto, cross-platform** |

El servidor HTTP embebido (`IfcHttpServer`) expone dos endpoints adicionales:

- **`GET /modelo.ifc`** — sirve el fichero IFC activo desde disco local sin copiarlo.
- **`GET /current.json`** — devuelve `{"version": N, "ifc_url": "/modelo.ifc" | null}` con un contador de versión que se incrementa cada vez que `set_ifc_path()` es llamado.

El frontend TypeScript (`viewer.ts`) hace polling a `/current.json` cada 1,5 s (con delay inicial de 800 ms para que WASM inicialice). Cuando `version` cambia, carga el nuevo IFC:

```typescript
async function pollCurrentIfc() {
  const data = await fetch("/current.json").then(r => r.json());
  if (data.version !== _pollVersion) {
    _pollVersion = data.version;
    if (data.ifc_url) {
      await window.GeoIfcViewer.openReference({ modelUrl: data.ifc_url, ... });
    } else {
      clearModel();
    }
  }
}
setTimeout(() => { void pollCurrentIfc(); setInterval(() => void pollCurrentIfc(), 1500); }, 800);
```

Este mecanismo permite que el usuario seleccione una feature en QGIS y el visor actualice el modelo sin reiniciar el subproceso.

### 5. Gestión de rutas locales en `ifc_url`

Las capas de prueba existentes utilizan el campo `ifc_url` para almacenar rutas locales de Windows (no URLs `http://`). `_local_path_from_reference()` distingue ambos casos:

```python
def _local_path_from_reference(reference: IfcReference) -> str:
    value = reference.value
    if value.startswith("http://") or value.startswith("https://"):
        return ""
    return value
```

### 6. Resiliencia del renderer (`renderProcessTerminated`)

Si Chromium se cae (señal `renderProcessTerminated`), el subproceso recarga la URL automáticamente:

```python
def _on_render_process_terminated(status, exit_code):
    view.load(QUrl(url))
```

El flag `setQuitOnLastWindowClosed(False)` evita que ese crash temporal provoque la salida del subproceso.

---

## Consecuencias

### Positivas

- WebGL funciona con SwiftShader en cualquier entorno (escritorio remoto, GPU virtual, hardware sin WebGL2 nativo).
- Fallos del renderer Chromium no afectan a la estabilidad de QGIS.
- El frontend TypeScript puede evolucionar de forma completamente independiente del código Python.
- No existe acoplamiento entre la librería de renderizado JS y el código QGIS (no hay QWebChannel ni `runJavaScript`).
- El polling HTTP es más simple de mantener y depurar que un canal bidireccional.

### Negativas

- Comunicación unidireccional por defecto: QGIS → visor (a través de HTTP). El canal inverso (selección de elemento IFC → QGIS) requiere trabajo adicional (posible extensión: endpoint `POST /selection` o WebSocket).
- Latencia de arranque del subproceso (~1-2 s).
- El polling introduce un retraso máximo de 1,5 s entre selección de feature en QGIS y actualización del modelo en el visor.
- La detección del intérprete Python depende de convenciones de instalación de QGIS; si cambian (nueva distribución), puede requerir ajuste en `_find_python_executable()`.

---

# ADR-009: Embedding del Subproceso Visor en la Pestaña del Dock

## Estado

Aceptado. Implementado en `geoifcassets/adapters/qgis/viewer.py` (`_embed_subprocess_window`, `_clear_embedded_window`).

## Contexto

ADR-008 establece que el visor IFC corre en un subproceso Python con su propia `QApplication`. Por defecto, la ventana `QWebEngineView` del subproceso aparece como una ventana flotante independiente. Esto es funcionalmente correcto, pero la experiencia de usuario es deficiente: la ventana puede quedar detrás de QGIS, el usuario tiene que gestionarla manualmente y no forma parte del flujo de trabajo integrado del plugin.

El objetivo es que el visor aparezca directamente dentro de la pestaña "IFC Viewer" del dock del complemento, sin ventana emergente.

---

## Alternativas evaluadas

### Alternativa A: Ventana flotante (comportamiento por defecto)

La ventana del subproceso abre como popup independiente. QGIS muestra en el dock una etiqueta de estado.

**Ventajas:** sin código adicional.

**Inconvenientes:** experiencia de usuario fragmentada; la ventana puede quedar oculta o perderse; no forma parte visual del complemento.

---

### Alternativa B: `QWidget.createWindowContainer(QWindow.fromWinId(win_id))` (ELEGIDA)

Qt ofrece un mecanismo nativo para embeber una ventana nativa extranjera (de otro proceso) dentro de un `QWidget`. El protocolo es:

1. El subproceso obtiene el HWND (Windows) / XID (X11) de su ventana con `view.winId()`.
2. Lo imprime por stdout: `READY:<win_id>`.
3. El proceso QGIS captura la línea, crea `QWindow.fromWinId(win_id)` y lo embebe con `QWidget.createWindowContainer(foreign_window, self.widget)`.
4. El container se inserta en el layout del dock en la posición del área de visualización (index 1, stretch=1).

**Ventajas:**
- El visor aparece integrado en el dock sin ventana flotante.
- Qt gestiona la sincronización de tamaño automáticamente: redimensionar el dock redimensiona la ventana embebida via mensajes nativos del sistema operativo.
- La ventana embebida pierde su chrome (borde, título, botón de cierre) al ser reparentada como ventana hija.

**Inconvenientes:**
- Requiere un protocolo stdout entre subproceso y proceso principal.
- El embedding es multiplataforma pero tiene matices: en Windows usa `SetParent()`, en X11 usa `XReparentWindow()`.
- Hay que gestionar cuidadosamente el orden de limpieza al cerrar.

---

### Alternativa C: Screenshot polling / framebuffer compartido

Capturar el contenido visual del subproceso y pintarlo en el dock mediante QPixmap.

**Descartada.** Demasiada complejidad, latencia visual, y no preserva interactividad (ratón, teclado no se reenvían).

---

## Decisión

Se adopta la **Alternativa B**: embedding mediante `QWidget.createWindowContainer(QWindow.fromWinId(win_id))`.

---

## Solución técnica implementada

### Protocolo de embedding

**Subproceso (`webviewer_app.py`):**

```python
view.show()   # Crea el HWND nativo (necesario para winId())
view.hide()   # Oculta la ventana antes de imprimir READY para evitar flash visual
win_id = int(view.winId())
print(f"READY:{win_id}", flush=True)
```

El `hide()` inmediato es clave: crea el HWND sin que la ventana flotante sea visible para el usuario. Cuando el dock la embebe (decenas de milisegundos después), aparece directamente en el panel, sin flash.

**Proceso QGIS (`viewer.py`):**

```python
def _on_proc_stdout(self) -> None:
    for line in raw.decode().splitlines():
        if line.startswith("READY:"):
            win_id = int(line.split(":", 1)[1])
            self._embed_subprocess_window(win_id)

def _embed_subprocess_window(self, win_id: int) -> None:
    from qgis.PyQt.QtGui import QWindow
    from qgis.PyQt.QtWidgets import QWidget

    foreign_window = QWindow.fromWinId(win_id)
    container = QWidget.createWindowContainer(foreign_window, self.widget)
    container.setMinimumSize(200, 150)
    container.setSizePolicy(QSizePolicy(Expanding, Expanding))
    # Reemplaza el placeholder en el layout (index 1, stretch 1)
    self._layout.insertWidget(1, container, 1)
    self._container = container
```

### Layout del dock

La estructura del dock es fija con tres elementos:

```
QVBoxLayout
  index 0 — _source_label      (sin stretch) — ruta del IFC activo
  index 1 — _viewer_placeholder o _container (stretch=1) — área del visor
  index 2 — _status_label      (sin stretch) — mensajes de estado
```

Cuando el subproceso envía `READY:`, el placeholder se retira del layout y el container se inserta en su lugar con `insertWidget(1, container, 1)`. Cuando el subproceso termina, el container se elimina y el placeholder se restaura.

### Gestión del ciclo de vida

El orden correcto de limpieza es crítico para evitar referencias Qt a ventanas nativas destruidas:

```
_stop_subprocess()
  ├── _clear_embedded_window()   ← primero: desreferencia la QWindow
  │     ├── removeWidget(container)
  │     ├── container.setParent(None)
  │     ├── container.deleteLater()
  │     └── restaurar placeholder
  └── proc.kill()                ← después: destruye la ventana nativa
```

Si el subproceso termina por sí solo (p.ej. el usuario cierra QGIS), `_on_proc_finished()` llama también a `_clear_embedded_window()` antes de poner `self._proc = None`. Cuando `open_reference()` detecta `self._proc is None`, relanza el subproceso, que enviará un nuevo `READY:` con un nuevo `win_id`.

### Compatibilidad Qt 5 / Qt 6

`QWindow.fromWinId` está disponible en ambas versiones. `QSizePolicy.Expanding` cambia de nombre en Qt6 a `QSizePolicy.Policy.Expanding`; se resuelve con:

```python
try:
    _exp = QSizePolicy.Expanding
except AttributeError:
    _exp = QSizePolicy.Policy.Expanding
```

---

## Consecuencias

### Positivas

- El visor IFC es parte visual integrada del dock, no una ventana flotante.
- El redimensionado del dock se propaga automáticamente a la ventana embebida.
- El ciclo de vida (arranque, reinicio, cierre) está completamente gestionado desde el dock sin intervención del usuario.
- Cuando el subproceso termina (crash, cierre de QGIS), el dock muestra un placeholder descriptivo y el siguiente `open_reference()` lo reinicia.

### Negativas

- Cuando el subproceso es terminado externamente (p.ej. `_stop_subprocess()` por recarga del plugin), la ventana nativa puede parpadear brevemente al ser desreparentada antes de que el proceso muera. Es un artefacto visual menor (~50 ms).
- El foco del teclado en ventanas embebidas entre procesos puede tener comportamientos específicos de plataforma (conocido en algunos entornos Linux/X11).
- Si el subproceso no imprime `READY:` (p.ej. error de arranque), el dock se queda con el placeholder permanentemente hasta el siguiente reinicio.

---

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
    core/
    adapters/
    services/
    webviewer/
    i18n/
```

Pero se interpreta de forma ligera:

* `core/`: conceptos y reglas puras con valor real.
* `adapters/`: adaptadores QGIS e IFC.
* `services/`: servicios transversales como logging.

No es obligatorio crear `port + use case + DTO` para cada interaccion pequena.

## Criterios por tipo de cambio

### Cambios QGIS

Mantenerlos fuera de `core/`.

Pueden vivir en:

* `adapters/qgis/`

Crear puerto solo si la funcionalidad debe probarse sin QGIS o si hay una regla de aplicacion no trivial.

### Cambios IFC

Mantener IfcOpenShell fuera de `core/`.

La lectura cruda puede vivir en `adapters/ifc/`.

La normalizacion o mapeo IFC-GIS puede vivir en `core/` si contiene logica pura.

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

---

# ADR-010: Árbol de Elementos IFC en el Visor — Fase A y Fase B

## Estado

Aceptado. **Fase A y Fase B implementadas** en `webviewer_src/src/viewer.ts`, `webviewer_src/src/viewer.css` y `webviewer_src/index.html`. Bundle compilado en `geoifcassets/webviewer/assets/`.

## Contexto

El visor IFC (ADR-008 + ADR-009) renderiza el modelo 3D completo pero no ofrece ningún mecanismo de inspección individual de elementos. El usuario ve la geometría pero no puede seleccionar un elemento concreto, hacer zoom sobre él ni consultar sus propiedades IFC (atributos directos ni PropertySets).

El MVP requiere consulta de propiedades IFC desde el visor (HU-02 parcial) como paso previo a la transferencia de valores BIM a campos GIS (HU-04). Sin un mecanismo de selección y visualización de propiedades, esa transferencia no puede realizarse de forma guiada.

La opción técnica natural sería implementar selección por clic en la escena 3D (ray-casting sobre meshes). Sin embargo, la prioridad para Fase A es demostrar el flujo de consulta de propiedades de forma robusta, con mínimo riesgo técnico. El ray-casting requiere gestionar intersecciones con geometrías complejas y puede producir selecciones ambiguas en elementos superpuestos.

---

## Alternativas evaluadas

### Alternativa A: Selección por clic en la escena 3D (ray-casting)

El usuario hace clic en la geometría. Se lanza un rayo desde la cámara y se detecta el primer mesh intersectado. El `mesh.userData.expressID` identifica el elemento.

**Ventajas:** flujo más intuitivo para usuarios BIM.

**Inconvenientes:**
- Gestión de intersecciones ambiguas (muros delante de puertas, elementos solapados).
- Requiere calcular normales y gestionar la cara frontal vs. trasera en geometrías DoubleSide.
- Mayor complejidad de implementación para un MVP.

**No descartada para Fase B:** se puede añadir como forma complementaria de selección (clic en escena + árbol lateral en paralelo).

---

### Alternativa B: Lista plana por categoría IFC + zoom + propiedades (ELEGIDA — Fase A)

Panel lateral con grupos `<details>/<summary>` HTML nativos, un botón por elemento, clic → zoom de cámara + highlight + propiedades en panel inferior.

**Ventajas:**
- Sin complejidad de ray-casting.
- El árbol por categoría es la forma estándar de navegación en herramientas BIM de referencia (Navisworks, Solibri, BIM Vision).
- `<details>/<summary>` nativos: colapsar/expandir sin JavaScript adicional.
- Compatible con cualquier modelo, incluso sin geometría consistente para ray-casting.

**Inconvenientes:**
- El usuario debe encontrar el elemento en el árbol antes de verlo en 3D (en lugar de clicar directamente sobre él).
- Fase A muestra lista plana por categoría, no árbol espacial Edificio→Planta→Elemento.

---

### Alternativa C: Árbol espacial completo (Edificio → Planta → Espacio → Elemento)

Recorre `IFCRELAGGREGATES` y `IFCRELCONTAINEDINSPATIALSTRUCTURE` para reconstruir la jerarquía espacial completa del modelo.

**Ventajas:** representación fiel de la estructura BIM; forma estándar en visores IFC avanzados.

**Inconvenientes:**
- Mayor complejidad de implementación (dos tipos de relaciones, posibles ciclos, elementos en múltiples plantas).
- En modelos mal estructurados (sin estructura espacial explícita), el árbol puede quedar vacío o incompleto.
- No es prioritaria para el MVP.

**Prevista para Fase B.**

---

## Decisión

Se adopta la **Alternativa B** para Fase A: lista de elementos agrupada por categoría IFC, con zoom de cámara, highlight y panel de propiedades al seleccionar.

---

## Solución técnica implementada

### Índice de PropertySets preconstruido

El recorrido de `IFCRELDEFINESBYPROPERTIES` para encontrar los PropertySets de un elemento es O(N_relations) si se hace en el momento del clic. Con 2.000 relaciones en un modelo típico y `api.GetLine` a ~0,1 ms/llamada, eso son 200 ms por clic — inaceptable.

Solución: construir el índice **una sola vez** cuando se carga el modelo:

```typescript
buildPropSetIndex(api, modelId):
  por cada IFCRELDEFINESBYPROPERTIES:
    psId = rel.RelatingPropertyDefinition.value
    para cada objId en rel.RelatedObjects[].value:
      propSetIndex[objId].push(psId)
```

El coste de construcción es O(N_relations × N_related_per_rel), ejecutado una sola vez. Clic posterior: O(1) lookup + O(N_psets_del_elemento) lecturas.

Los valores REF en web-ifc tienen la forma `{ type: 5, value: expressID }`. La función `resolveRef` extrae el `value` numérico y `resolveRefArray` maneja tanto un solo REF como un array de REFs.

### Índice de elementos por categoría

Solo se indexan los elementos que tienen geometría en escena (los que aparecen en `modelGroup` como meshes). Esto evita procesar las miles de entidades auxiliares del modelo (geometrías, materiales, relaciones) que no son relevantes para el árbol.

Código de mapeo: `CATEGORY_NAMES: Record<number, string>` con 31 códigos de tipo IFC mapeados a 20 categorías legibles. Tipos no reconocidos caen a la categoría "Other".

### Gestión de highlight

`HIGHLIGHT_MAT` es un `MeshStandardMaterial` singleton (naranja/amber, `emissiveIntensity: 0.35`). Al seleccionar:
- Los materiales originales de los meshes del elemento se guardan en `savedMaterials: Map<Mesh, Material | Material[]>`.
- Se asigna `HIGHLIGHT_MAT` a esos meshes.

Al deseleccionar o limpiar el modelo: `clearHighlight()` restaura los materiales originales desde `savedMaterials` y limpia el mapa. `clearHighlight()` siempre se llama **antes** de `clearModel()` para no disponer meshes con materiales aún en memoria.

### Lectura de propiedades en el clic

**Atributos directos:** `api.GetLine(modelId, expressId, false)` sin `flatten` para no expandir entidades relacionadas. Se filtran claves técnicas (`expressID`, `type`, `OwnerHistory`, `ObjectPlacement`, `Representation`, relaciones inversas). Los valores REF (`{ type: 5 }`) se omiten — son apuntadores, no datos displayables.

**PropertySets:** `propSetIndex[expressId]` → lista de IDs → `api.GetLine` de cada PropertySet → `HasProperties` / `Quantities` → `api.GetLine` de cada propiedad → `NominalValue.value` (IfcPropertySingleValue) o `*Value` (IfcQuantityLength/Area/Volume/Count).

`extractAttrValue` desenvuelve objetos web-ifc `{ type, value }` de forma defensiva, retornando `null` para REFs, arrays o valores vacíos.

### Layout del panel lateral

```
.viewer-panel (flex column, overflow hidden)
  ├── .panel-info     (flex-shrink: 0) — nombre del fichero IFC
  ├── .panel-tree     (flex: 1, overflow-y: auto) — árbol de categorías
  ├── .panel-props    (flex-shrink: 0, max-height: 45%, hidden) — propiedades
  └── .panel-status   (flex-shrink: 0) — estado actual
```

`.panel-tree` crece para ocupar todo el espacio disponible. `.panel-props` aparece desde el borde inferior con altura máxima del 45% del panel total cuando hay un elemento seleccionado.

---

## Consecuencias

### Positivas

- El usuario puede explorar cualquier elemento del modelo sin necesidad de ray-casting.
- Los PropertySets se leen en el momento del clic (<10 ms gracias al índice preconstruido) sin bloqueo visual perceptible.
- El árbol de categorías nativo (`<details>/<summary>`) no requiere ningún framework de componentes UI.
- La base de datos de propiedades en memoria (`propSetIndex`) habilita funcionalidades futuras (búsqueda por propiedad, transferencia BIM→GIS desde el árbol).

### Negativas

- La lista plana por categoría no refleja la estructura espacial del modelo (Planta 1, Planta 2...). Previsto resolverlo en Fase B con la jerarquía espacial completa.
- El highlight no diferencia elementos con geometrías múltiples (un IfcWall puede tener N meshes — todos se destacan en naranja, lo que es correcto funcionalmente pero puede dificultar ver la forma exacta en modelos densos).
- `buildElementIndex` hace una llamada `api.GetLine` por cada elemento con geometría. En modelos con >5.000 elementos únicos, el tiempo de indexación puede ser de 1-3 s adicionales tras la carga de geometría.

---

## Fase B: jerarquía espacial y selección por clic

Implementada en la misma rama que Fase A.

### Árbol espacial (Proyecto → Sitio → Edificio → Planta → Elemento)

Se construye el árbol espacial recorriendo dos tipos de relaciones IFC:

- **`IFCRELAGGREGATES`** — descomposición espacial: `RelatingObject` (nodo padre) → `RelatedObjects[]` (nodos hijos). Define la jerarquía Proyecto → Sitio → Edificio → Planta → Espacio.
- **`IFCRELCONTAINEDINSPATIALSTRUCTURE`** — contenencia: `RelatingStructure` (planta o espacio) → `RelatedElements[]` (elementos físicos contenidos).

Algoritmo de `buildSpatialTree`:

```
1. GetLineIDsWithType(IFCRELAGGREGATES)
     → decomposedBy: Map<parentId, childIds[]>
2. GetLineIDsWithType(IFCRELCONTAINEDINSPATIALSTRUCTURE)
     → containedIn: Map<structureId, elementIds[]>
3. GetLineIDsWithType(IFCPROJECT) → rootId
4. buildSpatialNode(rootId) [recursivo]
     → SpatialNode { expressId, name, typeLabel, typeCss,
                     children: SpatialNode[], elements: IFCElement[],
                     totalCount: number }
```

Los datos de elementos (nombre, categoría) se reutilizan desde el índice `elementsByCategory` ya construido en Fase A, evitando llamadas duplicadas a `api.GetLine`.

`totalCount` se calcula recursivamente en la construcción del árbol para mostrar el número total de elementos en cada nodo (incluyendo sub-nodos).

**Comportamiento con modelos sin estructura espacial:** si `GetLineIDsWithType(IFCPROJECT)` devuelve 0 entradas, o si `IFCRELAGGREGATES` no existe en el modelo, `spatialRoot` queda como `null`. El botón "Spatial" queda deshabilitado y el visor usa la vista por categoría.

**Selector de vista:** dos botones (`Category` / `Spatial`) en una barra justo encima del árbol. La vista "Spatial" se activa por defecto si el modelo tiene estructura espacial. Los `<details>` de storey están abiertos por defecto; los de space están cerrados (modelos con muchos espacios generarían demasiado ruido visual).

**Indentación visual:** los nodos `snode-building`, `snode-storey` y `snode-space` tienen `margin-left: 10px` y `border-left` para mostrar la jerarquía sin profundidad de anidamiento excesiva.

### Selección por clic en la escena 3D (ray-casting)

`THREE.Raycaster` singleton instanciado una sola vez. Listener de `mousedown` registra la posición inicial. Listener de `click` descarta eventos de arrastre (distancia > 4 px) para no interferir con la órbita de `OrbitControls`:

```typescript
canvas.addEventListener("click", (e) => {
  if (Math.sqrt(dx*dx + dy*dy) > 4) return; // era arrastre
  raycaster.setFromCamera(mouse, camera);
  const hits = raycaster.intersectObjects(meshes, false);
  if (hits.length > 0) selectElement(hits[0].object.userData.expressID);
});
```

El clic dispara `selectElement(expressId)`, que abre los `<details>` ancestros necesarios y hace scroll hasta el botón del árbol correspondiente:

```typescript
let parent = btn?.parentElement;
while (parent && parent !== elementTreeEl) {
  if (parent.tagName === "DETAILS") (parent as HTMLDetailsElement).open = true;
  parent = parent.parentElement;
}
btn?.scrollIntoView({ block: "nearest" });
```

Esto garantiza que después de seleccionar por clic 3D, el árbol muestra y resalta el elemento seleccionado.

## Fase C — Transferencia BIM→GIS (implementada)

### Problema

El visor corre en un subproceso separado. Para que el usuario pueda copiar una propiedad IFC a un campo GIS necesita un canal de comunicación subproceso → QGIS, no disponible por QWebChannel (el visor usa QWebEngineView en el subproceso).

### Decisión

Se usa el servidor HTTP local ya existente (`IfcHttpServer`) como canal inverso:

1. El JS añade un botón `→` (*prop-transfer*) a cada fila del panel de propiedades.
2. Al hacer clic, el JS hace `POST /transfer` con `{ pset, key, value }` al mismo origen (`http://127.0.0.1:{port}`).
3. `IfcHttpServer._receive_transfer` deserializa el JSON y lo almacena en `_pending_transfers` (protegido por `threading.Lock`).
4. Un `QTimer` a 250 ms en `IfcViewerDock` llama a `_poll_transfers()` en el hilo principal de Qt, extrayendo la primera transferencia con `pop_pending_transfer()`.
5. La transferencia se pasa al callback `on_transfer` registrado en `GeoIfcAssetsPlugin`.
6. `GeoIfcAssetsPlugin._show_transfer_dialog()` abre un `QDialog` que permite seleccionar o nombrar el campo GIS de destino y escribe el valor con `layer.changeAttributeValue()`.

### Archivos modificados

| Archivo | Cambios |
|---|---|
| `geoifcassets/adapters/qgis/viewer.py` | `IfcHttpServer.do_POST` + `_receive_transfer` + `pop_pending_transfer`; `IfcViewerDock.__init__` + `_poll_transfers` con QTimer 250 ms |
| `geoifcassets/adapters/qgis/plugin.py` | `_show_dock` pasa `on_transfer`; nuevos métodos `_handle_transfer` + `_show_transfer_dialog` |
| `webviewer_src/src/viewer.ts` | funciones `propRow`, `transferProp`; actualización de `renderProps` con delegación de eventos |
| `webviewer_src/src/viewer.css` | estilos `.prop-transfer`, `.prop-sent`, `.prop-error` |

### Pendiente

- **Elementos sin estructura espacial**: elementos con geometría pero sin `IFCRELCONTAINEDINSPATIALSTRUCTURE` no aparecen en el árbol espacial. Se puede añadir un nodo "Not placed" en iteraciones futuras.

---

# ADR-011: Herramientas de Análisis Visual en el Visor — Medición, Sección y Vistas Ortonormales

## Contexto

Una vez cargado el modelo IFC en el visor 3D, los usuarios necesitan herramientas de inspección geométrica para interpretar el modelo sin salir de QGIS: medir distancias y superficies, cortar el modelo con un plano para ver el interior, y navegar por vistas ortogonales estándar (alzados, plantas) para combinar con la sección transversal.

Todas las herramientas deben ser temporales y visuales (no transfieren datos a GIS), implementarse en la SPA Vite (TypeScript + Three.js) sin dependencias nuevas, y coexistir con el flujo de selección y transferencia BIM→GIS ya existente.

## Decisiones

### Medición (longitud y área)

- **Longitud**: dos clics sobre la malla IFC vía `THREE.Raycaster`; segmento `THREE.Line` + etiqueta de distancia en metros.
- **Área**: N clics + clic derecho para cerrar polígono; malla semitransparente `THREE.Mesh` (triangulación fan) + etiqueta de área.
- **Geometría de medición**: `depthTest: false` + `renderOrder ≥ 999` para renderizar sobre el modelo.
- **Etiquetas**: `<div>` absolutamente posicionados en `#measure-labels` (`pointer-events: none`); reposicionados cada frame en `animate()` con `vector.project(camera)`.
- **Ciclo de vida**: se borran al cambiar de elemento seleccionado (`clearMeasurements` en `selectElement`) y con el botón ✕ Clear.

### Sección transversal

- **Mecanismo**: `THREE.Plane` + `renderer.clippingPlanes = [sectionPlane]` (clipping global). `renderer.localClippingEnabled` permanece en `false`.
- **Cálculo del plano**: bounding box del modelo → `threshold = min + (max − min) × posicion%`. Normal según eje; modo "no invertido" muestra la parte inferior (`normal = −axisDir, const = threshold`); modo "invertido" muestra la parte superior.
- **UI**: panel flotante en la parte inferior del visor (`#section-controls`, `position: absolute; bottom: 40px`) con selector de eje X/Y/Z, slider 0-100 %, botón ↕ flip y botón ✕ off.
- **Coexistencia**: sección es independiente de los modos de medición (toggles separados).

### Vistas ortonormales y cámara ortográfica

- **Preajustes de vista** (Front/Back/Left/Right/Top/ISO): calculan `targetPos = center + dir × distance` donde `distance = (maxDim × 0.6) / tan(fov/2)`. Animación suave con lerp factor 0,13 por frame en `animate()`.
- **Cámara `up`**: se asigna antes de iniciar el lerp (p.ej. `(0,0,−1)` para Top) para evitar singularidad polar en OrbitControls.
- **Cámara ortográfica**: `THREE.OrthographicCamera` secundaria, sincronizada cada frame desde la cámara perspectiva principal. Frustum derivado de `halfH = dist × tan(fov/2)` donde `dist = camera.position.distanceTo(controls.target)`. OrbitControls sigue operando sobre la cámara perspectiva; la cámara ortográfica solo se usa para renderizar.
- **`renderCamera`**: variable de módulo actualizada en `animate()` apuntando a la cámara activa (perspectiva u ortográfica). `updateMeasureLabels()` y ambos `raycaster.setFromCamera()` usan `renderCamera ?? camera` para precisión en modo ortográfico.

### Archivos modificados

| Archivo | Cambios |
|---|---|
| `webviewer_src/index.html` | `#measure-toolbar` ampliado (✂ Section); nuevos `#view-preset-bar`, `#section-controls` |
| `webviewer_src/src/viewer.ts` | Estado: `MeasureMode`, `VIEW_PRESETS`, `orthoCamera`, `useOrtho`, `renderCamera`, `cameraAnimTarget`, `sectionPlane`. Funciones: `handleMeasureClick`, `finalizeLengthMeasurement`, `finalizeAreaMeasurement`, `updateSectionPlane`, `enableSection`, `disableSection`, `snapToView`, `setOrthoMode` |
| `webviewer_src/src/viewer.css` | Estilos `.measure-toolbar`, `.measure-btn`, `.measure-label`, `.section-controls`, `.view-preset-bar`, `.view-preset-btn` |


---

# ADR-012: Funcionalidades desactivadas en v1 — Plantilla personalizada y transferencia BIM→GIS

## Estado

Decidido (2026-06-26)

## Contexto

Durante el desarrollo de la v1 del complemento GeoIFC Assets se tomó la decisión de simplificar el alcance de la primera versión pública. Dos funcionalidades estaban técnicamente implementadas pero se decidió no exponerlas en la interfaz hasta validar el flujo principal.

---

## Funcionalidades desactivadas

### 1. Carga de plantilla personalizada (custom template JSON)

**Descripción:** Botón "Load custom template…" en la pestaña Extract que permitía al usuario cargar un JSON propio para añadir campos de extracción IFC dinámicos (PropertySets, QuantitySets) como sección adicional bajo los campos del catálogo core.

**Motivo de desactivación:** En v1 no hay suficiente documentación ni UX para guiar al usuario en la creación de plantillas válidas. Se evita confusión y soporte prematuro.

**Cómo reactivar:**
- En `geoifcassets/adapters/qgis/dock.py`, función `__init__`, añadir de nuevo el botón al layout:
  ```python
  template_bar_layout.addWidget(self._load_json_btn)
  ```
- Todo el código de soporte está activo: `set_custom_template`, `_append_custom_section`, `extract_custom_fields`, plantillas de ejemplo en `geoifcassets/templates/examples/`.

---

### 2. Botón "→" de transferencia por propiedad en el panel del visor web

**Descripción:** En el panel de propiedades del visor IFC 3D, junto al valor de cada propiedad aparecía un botón `→` con tooltip _"Transfer to GIS field"_. Al pulsarlo se abría el diálogo BIM→GIS (`_show_transfer_dialog` en plugin.py) que permite mapear ese valor a un campo de una capa GIS activa.

El diálogo BIM→GIS en sí **se mantiene activo** y puede seguir lanzándose desde otros puntos de entrada (métricas, eventos futuros). Lo que se elimina es únicamente el botón en el panel del visor.

**Motivo de desactivación:** El botón por propiedad genera ruido en el panel durante la exploración IFC y requiere que el usuario tenga una capa GIS activa con el campo correcto. Se reserva para v2 junto con un flujo de mapeo más guiado.

**Cómo reactivar:**
- En `webviewer_src/src/viewer.ts`, función `propRow`, renombrar `_pset` → `pset` y descomentar la línea del botón dentro del template literal:
  ```typescript
  // restore: `<button class="prop-transfer" data-pset="${escHtml(_pset)}" ...>→</button>` +
  ```
- El click handler en `renderProps` (`.prop-transfer`) ya está en el código y no requiere cambios.

---

## Consecuencias

- El panel del visor IFC muestra propiedades sin botones de acción → interfaz más limpia.
- El botón "→ Load to GIS" de la pestaña Extract **permanece activo** — permite escribir campos extraídos en una entidad GIS seleccionada.
- El diálogo BIM→GIS (`_show_transfer_dialog`) permanece funcional para uso interno y futuras integraciones.
- Los tests unitarios y la arquitectura interna están intactos; la reactivación del botón del visor es quirúrgica (ver sección 2).
