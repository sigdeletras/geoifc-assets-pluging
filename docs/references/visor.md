
## Definición Formal del Alcance del 
**Módulo independiente para probar la  integración un visor BIM nativo para archivos IFC, con arquitectura desacoplada (Adaptador) y servidor HTTP concurrente embebido, operando en entorno local offline.**

---

### 1. Objetivo General
Desarrollar un módulo que permita visualizar modelos IFC (Industry Foundation Classes) dentro de un panel acoplable, sin necesidad de conversiones previas ni dependencia de servicios en la nube para los datos. La librería de renderizado se carga desde CDN, por lo que **se requiere conexión a internet**. La arquitectura incluirá una capa de abstracción (Adaptador) que aísle la lógica de visualización, permitiendo cambiar la librería de renderizado (ej. That Open Engine ↔ xeokit) sin modificar el código Python del plugin.

---

### 2. Arquitectura General (Cliente-Servidor Local Concurrente con Adaptador)

```
+---------------------------------------------------+
|                    QGIS                            |
|  +---------------------------------------------+  |
|  |   QDockWidget                               |  |
|  |  +---------------------------------------+  |  |
|  |  | QWebEngineView                        |  |  |
|  |  | (Carga index.html + adapter)          |  |  |
|  |  +------------------^--------------------+  |  |
|  |                     | runJavaScript          |  |
|  |  +------------------v--------------------+  |  |
|  |  |      Lógica JS (Core - main.js)      |  |  | <-- Orquesta la carga y eventos
|  |  +------------------^--------------------+  |  |
|  |                     | Llama métodos estandar |  |
|  |  +------------------v--------------------+  |  |
|  |  |    ADAPTADOR DEL VISOR (API)         |  |  | <-- CAPA DE ABSTRACCIÓN
|  |  |   (Interfaz estándar:                |  |  |
|  |  |    loadModel, highlight, destroy)    |  |  |
|  |  +------------------^--------------------+  |  |
|  |                     | Implementa            |  |
|  |  +------------------v--------------------+  |  |
|  |  | Librería A (That Open Engine)        |  |  | <-- Fácilmente reemplazable
|  |  | o Librería B (xeokit)                |  |  |
|  |  +------------------^--------------------+  |  |
|  |                     | Carga IFC (fetch)    |  |  |
|  |  +------------------v--------------------+  |  |
|  |  | Servidor ThreadingHTTPServer         |  |  | <-- CONCURRENTE (NUEVO)
|  |  | (Handler custom con Lock para ruta)  |  |  |
|  |  +------------------^--------------------+  |  |
|  |                     | Lee disco (paralelo)  |  |
|  +---------------------+-----------------------+  |
|                       | Ruta absoluta             |
+-----------------------+---------------------------+
                        |
                  [Archivo .ifc]
```

---

### 3. Decisiones Técnicas Finales (Por Capas)

#### A. Capa de Integración en QGIS (Backend PyQGIS)
- **Lenguaje**: Python 3.9+ (QGIS 3.28 LTS).
- **Componente de navegación web**: `QWebEngineView` (basado en Chromium) para renderizar el visor HTML/JS dentro del panel.
- **Manejo de hilos**: El servidor se ejecutará en un **hilo demonio** (`threading.Thread`, `daemon=True`) para no bloquear la interfaz gráfica de QGIS.
- **Selección de archivos**: `QFileDialog.getOpenFileName()` con filtro `*.ifc;*.IFC`.
- **Ciclo de vida**: El servidor se inicia al activar el plugin (`initGui`) y se destruye (`.shutdown()`, `.server_close()`) al descargarlo (`unload`) o cerrar QGIS.

#### B. Capa de Comunicación (Servidor HTTP Embebido Concurrente) 
- **Librería base**: `http.server.ThreadingHTTPServer` y `SimpleHTTPRequestHandler` (módulos nativos de Python, disponibles desde Python 3.7+).
- **Justificación**: Se opta por `ThreadingHTTPServer` frente al `HTTPServer` síncrono para manejar múltiples peticiones en **paralelo** (ej. el navegador solicita el HTML, el CSS, el JS y el pesado IFC simultáneamente). Esto evita bloqueos, timeouts y acelera la carga inicial del visor.
- **Handler personalizado**: Clase `CustomHandler` que sobrescribe el método `do_GET()`.
    - **Ruta interceptada**: `/modelo.ifc` (fija).
    - **Comportamiento**: Sirve el archivo IFC directamente desde la **ruta absoluta** guardada en memoria (sin copiar ni mover el archivo físico). Para el resto de rutas (`/index.html`, `/main.js`, `/adapter.js`), delega en `super().do_GET()` para servir archivos estáticos desde el directorio `web_visor`.
- **Gestión de concurrencia (Thread-Safety)**: Como `CustomHandler` usa una variable de clase (`ifc_path`) que se actualiza cuando el usuario cambia de archivo, se emplea un **`threading.Lock`** para proteger la escritura de esta ruta y evitar condiciones de carrera entre hilos.

    ```python
    class CustomHandler(SimpleHTTPRequestHandler):
        ifc_path = None
        _lock = threading.Lock()

        @classmethod
        def set_ifc_path(cls, path):
            with cls._lock:
                cls.ifc_path = path
    ```

- **Puerto**: Se asignará un puerto libre automáticamente mediante `socket.socket` (`bind(('', 0))`) para evitar conflictos con otros servicios.
- **URL de acceso**: `http://localhost:[puerto]/index.html` para el visor y `http://localhost:[puerto]/modelo.ifc` para la carga del modelo.

#### C. Capa de Visualización (Frontend JavaScript con Adaptador) ⭐ **MODIFICADO**
- **Arquitectura interna del frontend**:
    1.  **`index.html`**: Punto de entrada. Carga un orquestador (`main.js`) y, mediante un parámetro `?engine=`, carga el adaptador correspondiente.
    2.  **`main.js` (Core)**: Lógica común del plugin. Obtiene la instancia del adaptador desde `window.ViewerAdapter` y gestiona eventos de QGIS.
    3.  **`adapters/` (Carpeta de adaptadores)**: Contiene implementaciones concretas que cumplen con una interfaz estándar.
        - `adapter.thatopen.js`: Implementa la API usando **That Open Engine** (antiguo IFC.js).
        - `adapter.xeokit.js`: Implementa la API usando **xeokit** (para modelos pesados, opcional).
- **Interfaz del Adaptador (API estándar)**:
    Se define un contrato JavaScript global que el plugin utiliza para hablar con el visor, sin importar la librería subyacente.
    ```javascript
    window.ViewerAdapter = {
        init(containerId, options) { /* Inicializa la escena 3D */ },
        loadModel(url) { /* Carga el IFC desde la URL (fetch) */ },
        highlightElement(id) { /* Resalta un elemento por su ID */ },
        setCamera(position, target) { /* Mueve la cámara */ },
        destroy() { /* Limpia recursos (renderer, geometrías) */ }
    };
    ```
- **Selección dinámica**: El plugin puede elegir qué adaptador cargar mediante un parámetro en la URL (ej. `?engine=xeokit`) o leyendo una configuración de QGIS (`QgsSettings`). El adaptador por defecto será **That Open Engine**.

#### D. Capa de Gestión de Datos
- **Ubicación del IFC**: Ruta absoluta elegida por el usuario. El servidor solo lee el archivo; no se generan copias ni archivos temporales pesados.
- **Persistencia**: La ruta del último IFC cargado se almacenará en los settings de QGIS (`QgsSettings`) para recordarla entre sesiones.

---

### 4. Alcance Funcional (Incluido)

| Funcionalidad | Estado | Nota |
| :--- | :--- | :--- |
| Carga de archivos IFC desde el disco local | ✅ Incluido | Mediante `QFileDialog` |
| Visualización 3D interactiva (zoom, rotación, desplazamiento) | ✅ Incluido | Vía adaptador (That Open Engine por defecto) |
| Herramientas de medición y planos de corte | ✅ Incluido | Depende del adaptador concreto |
| Panel acoplable dentro de QGIS | ✅ Incluido | `QDockWidget` |
| Funcionamiento offline del modelo IFC | ✅ Incluido | El archivo IFC se sirve desde disco local |
| Librería de renderizado vía CDN | ✅ Incluido | That Open Engine y Three.js cargados desde CDN (requiere conexión a internet) |
| Sin duplicación de archivos | ✅ Incluido | Lectura directa desde ruta original |
| Cambio de librería visora sin modificar Python | ✅ Incluido | Basta con cambiar el adaptador JS cargado |
| Carga concurrente y rápida de recursos | ✅ Incluido | Gracias a `ThreadingHTTPServer` |
| Cierre limpio del servidor al salir de QGIS | ✅ Incluido | `.shutdown()` en `unload()` |

---

### 6. Dependencias Técnicas

- **QGIS**: 3.28 LTS y  superior 4.0 (por `QWebEngineView` estable y Python 3.9+).
- **Python**: Módulos nativos (`http.server.ThreadingHTTPServer`, `socket`, `threading`, `os`). Sin dependencias externas para el servidor.
- **JavaScript (Frontend)**:
    - **Adaptador por defecto (That Open Engine)**: Cargado desde CDN. **Requiere conexión a internet.** URLs de referencia: `https://cdn.jsdelivr.net/npm/web-ifc` y paquetes `@thatopen/components`.
    - **Adaptador alternativo (xeokit)**: Opcional; cargado desde CDN o empaquetado localmente bajo demanda.
    - **Prouesta de Estructura de archivos n**:
        ```
        
           ├── web_visor/
           │   ├── index.html
           │   ├── main.js (orquestador)
           │   ├── adapters/
           │   │   ├── adapter.thatopen.js
           │   │   └── adapter.xeokit.js (opcional)
           │   └── css/
           └── resources/
        ```
- **Hardware**: Tarjeta gráfica con soporte para WebGL (requisito de Three.js).

---

### 7. Plan de Desarrollo Sugerido (Hitos)

1. **Hito 1**: Generar la estructura del plugin con Plugin Builder 3. Crear el `QDockWidget` y añadir un `QWebEngineView` funcional que cargue una página HTML local.
2. **Hito 2**: Implementar el servidor `ThreadingHTTPServer` embebido con el handler personalizado (incluyendo el `Lock` para la ruta) y verificar que sirve archivos estáticos.
3. **Hito 3**: Diseñar e implementar la **API del Adaptador** en JavaScript (`main.js` y contrato de la interfaz).
4. **Hito 4**: Implementar el adaptador concreto para **That Open Engine** y probar la carga del IFC desde el servidor mediante `fetch('/modelo.ifc')`.
5. **Hito 5**: Integrar el selector de archivos (`QFileDialog`) en QGIS, conectar la señal de selección para actualizar `CustomHandler.ifc_path` y refrescar el visor.
6. **Hito 6** *(Ampliación)*: Implementar el adaptador para **xeokit** para validar la flexibilidad del sistema y tener una alternativa para modelos pesados.
7. **Hito 7**: Pruebas de rendimiento, optimización de memoria (destrucción correcta del renderizador) y depuración de cierres de hilos.

---

