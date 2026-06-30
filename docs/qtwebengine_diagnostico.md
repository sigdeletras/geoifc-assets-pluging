# Diagnóstico QtWebEngine en QGIS 3 / QGIS 4

## Contexto

El complemento GeoIFC Assets lanza `webviewer_app.py` como subprocess para abrir un visor IFC basado en `QWebEngineView`. El subprocess importa `PyQt6.QtWebEngineWidgets` (QGIS 4) o `PyQt5.QtWebEngineWidgets` (QGIS 3). El problema es que la instalación estándar de QGIS 3 vía OSGeo4W **no incluye** `PyQt5.QtWebEngineWidgets`.

---

## Casuísticas identificadas

### Caso 1 — QGIS 3 + OSGeo4W mínimo (instalación estándar)

**Resultado esperado:** fallo al importar en el subprocess.

- `PyQt5.QtWebEngineWidgets` no está en el setup estándar de OSGeo4W.
- El subprocess termina con `returncode != 0` antes de emitir `READY:<win_id>`.
- El plugin no abre el visor.

**Confirmación:**

```bash
# En la consola OSGeo4W Shell
python -c "from PyQt5.QtWebEngineWidgets import QWebEngineView; print('OK')"
```

Resultado esperado: `ImportError: cannot import name 'QWebEngineView'` (o similar).

---

### Caso 2 — QGIS 3 + OSGeo4W con QtWebEngine instalado manualmente

El usuario instala el componente `PyQGIS-Qt5-WebEngine` o equivalente desde el instalador OSGeo4W.

#### Subcaso 2a — Instalación completa y correcta

- Import tiene éxito.
- Subprocess emite `READY:<win_id>`.
- El visor se abre y carga la URL.

#### Subcaso 2b — Instalación parcial (DLLs Chromium incompletas)

- El import tiene éxito.
- El subprocess arranca pero Chromium crashea al cargar la URL.
- stdout emite `RENDERER_CRASH:<status>` o el proceso muere sin más output.

#### Subcaso 2c — ICU data files ausentes

- Chromium arranca pero no renderiza texto (error de internacionalización).
- La ventana se abre pero el contenido es ilegible o en blanco.

---

### Caso 3 — QGIS 3 + Instalador standalone Windows (`.exe`)

El instalador standalone de QGIS para Windows incluye más componentes que OSGeo4W mínimo.

- **A verificar:** si el bundle incluye `PyQt5.QtWebEngineWidgets`.
- Puede funcionar aunque la instalación OSGeo4W falle.

**Confirmación:**

```bash
# Desde la Python Shell de QGIS (menú Complementos → Consola Python)
import sys; print(sys.executable)
from PyQt5.QtWebEngineWidgets import QWebEngineView; print('OK')
```

---

### Caso 4 — QGIS 4 + Windows (instalación estándar)

Qt6 incluye `PyQt6.QtWebEngineWidgets` por defecto.

- El subprocess prueba PyQt6 primero (línea 31 de `webviewer_app.py`).
- Camino feliz: subprocess emite `READY:<win_id>` y el visor se abre.

**Confirmación:**

```bash
# Desde la Python Shell de QGIS 4
from PyQt6.QtWebEngineWidgets import QWebEngineView; print('OK')
```

---

### Caso 5 — Cualquier QGIS + WebEngine bloqueado por antivirus / GPO corporativa

- El import tiene éxito (DLLs presentes).
- El proceso Chromium es bloqueado por el antivirus o política de grupo.
- El subprocess puede: emitir `READY` y la ventana queda en blanco, o crashear en `renderProcessTerminated`.

**Síntoma diferenciador:**

- `READY` aparece en stdout del subprocess.
- La ventana se abre pero no carga ningún contenido.

---

### Caso 6 — Cualquier QGIS + máquina virtual / sin GPU

SwiftShader (software renderer) se activa vía:

```
QTWEBENGINE_CHROMIUM_FLAGS=--use-gl=swiftshader
```

El plugin propaga este flag al subprocess mediante `_ensure_swiftshader_flag` en `initGui`.

- Si el flag **se propaga correctamente:** el visor carga (lento, renderizado por software).
- Si el flag **no se hereda** (variables de entorno cortadas en el subprocess): Chromium puede crashear.

---

### Caso 7 — QGIS 3 + Linux (apt / flatpak)

`python3-pyqt5.qtwebengine` es un paquete separado en Debian/Ubuntu.

#### Subcaso 7a — Paquete instalado

- Funciona igual que el Caso 2a.

#### Subcaso 7b — Paquete no instalado

- `ImportError` igual que el Caso 1.

**Confirmación:**

```bash
dpkg -l | grep python3-pyqt5.qtwebengine
python3 -c "from PyQt5.QtWebEngineWidgets import QWebEngineView; print('OK')"
```

---

## Tabla resumen

| # | Entorno | QtWebEngine | Falla en |
|---|---------|-------------|----------|
| 1 | QGIS 3 + OSGeo4W mínimo | ❌ No | Import del subprocess |
| 2a | QGIS 3 + OSGeo4W + paquete completo | ✅ Sí | — |
| 2b | QGIS 3 + OSGeo4W + paquete parcial | ⚠️ Parcial | Renderer crash (runtime) |
| 2c | QGIS 3 + OSGeo4W + ICU ausente | ⚠️ Parcial | Contenido en blanco |
| 3 | QGIS 3 + Standalone Windows | ❓ A verificar | — |
| 4 | QGIS 4 + Windows | ✅ Sí | — |
| 5 | Cualquier QGIS + AV/GPO corporativa | ⚠️ Import ok | Chromium bloqueado (runtime) |
| 6 | Cualquier QGIS + VM sin GPU | ⚠️ Import ok | Renderer crash si flag no se hereda |
| 7a | QGIS 3 + Linux + paquete instalado | ✅ Sí | — |
| 7b | QGIS 3 + Linux sin paquete | ❌ No | Import del subprocess |

---

## Pasos para confirmar la situación

### Paso 1 — Identificar el Python del subprocess

Desde la **Consola Python de QGIS** (menú Complementos → Consola Python):

```python
import sys
print("Ejecutable:", sys.executable)
print("Versión:", sys.version)
```

Anotar la ruta. Es el mismo Python que usa `webviewer_app.py`.

---

### Paso 2 — Test directo del import

```python
import sys, subprocess

result = subprocess.run(
    [sys.executable, '-c',
     'from PyQt5.QtWebEngineWidgets import QWebEngineView; print("OK")'],
    capture_output=True, text=True
)
print("STDOUT:", result.stdout)
print("STDERR:", result.stderr)
print("Return code:", result.returncode)
```

| Resultado | Diagnóstico |
|-----------|-------------|
| `OK` + RC=0 | QtWebEngine disponible → Caso 2a o 3 |
| `ImportError` + RC=1 | QtWebEngine no instalado → Caso 1 o 7b |
| RC=0 pero sin output | Error silencioso — revisar stderr |

Para QGIS 4, cambiar `PyQt5` por `PyQt6` en el comando.

---

### Paso 3 — Listar paquetes Qt instalados en OSGeo4W

Desde la **OSGeo4W Shell** (no la consola de QGIS):

```bash
# Ver qué paquetes Qt/PyQt están instalados
python -m pip list 2>nul | findstr /i "pyqt web engine"

# Alternativa: listar archivos de QtWebEngine
dir /b /s "%OSGEO4W_ROOT%\apps\qgis\plugins\*web*"
dir /b /s "%OSGEO4W_ROOT%\apps\Python312\Lib\site-packages\PyQt5\*Web*"
```

Si `QtWebEngineWidgets.pyd` no aparece → confirma Caso 1.

---

### Paso 4 — Instalar QtWebEngine desde el setup de OSGeo4W

Si el Paso 2 confirma que falta:

1. Abrir el instalador de OSGeo4W: `osgeo4w-setup.exe`
2. Seleccionar modo **Advanced Install**
3. Buscar el paquete: `python3-pyqt5-qwebengine` o `qgis-qt5-webkit`
4. Instalar y esperar que complete
5. Repetir el Paso 2 para verificar

> **Nota:** el nombre exacto del paquete puede variar según la versión de OSGeo4W. Buscar cualquier paquete que contenga `webengine` o `webkit` en la categoría `Python`.

---

### Paso 5 — Verificar que el subprocess emite READY

Con el plugin cargado, abrir el visor IFC desde el dock. Observar los logs de QGIS:

- Si aparece `READY:<win_id>` en los logs → subprocess arrancó correctamente.
- Si aparece un error de timeout o no aparece nada → subprocess falló.

Activar el nivel de log `DEBUG` del plugin para ver la salida completa del subprocess.

---

### Paso 6 — Verificar propagación de flags (casos VM / sin GPU)

```python
import os
print("CHROMIUM FLAGS:", os.environ.get('QTWEBENGINE_CHROMIUM_FLAGS', 'NO ESTABLECIDO'))
```

Si no está establecido en el proceso QGIS, el subprocess tampoco lo heredará.

---

## Instrucciones para el usuario final (QGIS 3 + OSGeo4W)

Si el visor IFC no se abre en QGIS 3 instalado vía OSGeo4W:

1. Cerrar QGIS.
2. Abrir el instalador de OSGeo4W (`osgeo4w-setup.exe`) como administrador.
3. Seleccionar **Advanced Install → Install from Internet**.
4. En el árbol de paquetes, buscar `python3-pyqt5-qwebengine`.
5. Marcarlo para instalar.
6. Completar la instalación.
7. Reabrir QGIS y volver a intentar abrir el visor IFC.

Si el paquete no aparece en el instalador, la instalación OSGeo4W puede estar desactualizada. Actualizar el instalador primero.

---

## Procedimiento de test limpio — ¿desinstalar antes?

### Cuándo desinstalar primero

| Objetivo | ¿Desinstalar antes? | Motivo |
|----------|---------------------|--------|
| Reproducir Caso 1 (simular ausencia) | ✅ Sí | Verificar que el plugin detecta correctamente la falta del paquete |
| Reparar instalación rota (Caso 2b/2c) | ✅ Sí | Eliminar DLLs residuales de instalación parcial |
| Usuario sin el paquete instalado (Caso 1 puro) | ❌ No | OSGeo4W instala directamente sin conflicto |

---

### Test completo para QGIS 3 (OSGeo4W + PyQt5)

**Objetivo:** validar los dos estados (ausente → presente) en la misma máquina.

#### Fase A — Confirmar ausencia (Caso 1)

1. OSGeo4W setup → buscar `python3-pyqt5-qwebengine` → marcar como **Uninstall** → aplicar.
2. Desde la **OSGeo4W Shell**:

```bash
python -c "from PyQt5.QtWebEngineWidgets import QWebEngineView; print('OK')"
```

Resultado esperado: `ImportError` — Caso 1 confirmado.

3. Desde la **Consola Python de QGIS**:

```python
import sys, subprocess
result = subprocess.run(
    [sys.executable, '-c',
     'from PyQt5.QtWebEngineWidgets import QWebEngineView; print("OK")'],
    capture_output=True, text=True
)
print("STDOUT:", result.stdout)
print("STDERR:", result.stderr)
print("Return code:", result.returncode)
```

Resultado esperado: `returncode=1`, stderr con `ImportError`.

4. Lanzar el visor IFC desde el dock del plugin → confirmar que aparece error claro (no crash silencioso).

#### Fase B — Instalar y confirmar funcionamiento (Caso 2a)

1. OSGeo4W setup → buscar `python3-pyqt5-qwebengine` → marcar como **Install** → aplicar.
2. Repetir el comando de la Fase A paso 2:

```bash
python -c "from PyQt5.QtWebEngineWidgets import QWebEngineView; print('OK')"
```

Resultado esperado: `OK`.

3. Repetir el test desde la Consola Python de QGIS (paso 3 de Fase A).  
   Resultado esperado: `returncode=0`, stdout `OK`.

4. Verificar archivos instalados:

```bash
dir /b "%OSGEO4W_ROOT%\apps\Python312\Lib\site-packages\PyQt5\*Web*"
```

Deben aparecer: `QtWebEngineWidgets.pyd`, `QtWebEngineCore.pyd`, `QtWebEngine.pyd`.

5. Lanzar el visor IFC desde el dock → confirmar `READY:<win_id>` en los logs del plugin.

---

### Test completo para QGIS 4 (PyQt6)

QGIS 4 incluye `PyQt6.QtWebEngineWidgets` en la instalación estándar. El test verifica que la ruta PyQt6 del subprocess funciona correctamente. No se requiere desinstalar nada previamente.

#### Fase A — Confirmar disponibilidad

1. Desde la **Consola Python de QGIS 4**:

```python
from PyQt6.QtWebEngineWidgets import QWebEngineView
print('OK')
```

Resultado esperado: `OK`.

2. Test del subprocess:

```python
import sys, subprocess
result = subprocess.run(
    [sys.executable, '-c',
     'from PyQt6.QtWebEngineWidgets import QWebEngineView; print("OK")'],
    capture_output=True, text=True
)
print("STDOUT:", result.stdout)
print("STDERR:", result.stderr)
print("Return code:", result.returncode)
```

Resultado esperado: `returncode=0`, stdout `OK`.

#### Fase B — Confirmar que el subprocess usa PyQt6 (no PyQt5)

```python
import sys, subprocess
result = subprocess.run(
    [sys.executable, '-c',
     '''
try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    print("PyQt6:OK")
except ImportError:
    from PyQt5.QtWebEngineWidgets import QWebEngineView
    print("PyQt5:OK (fallback)")
'''],
    capture_output=True, text=True
)
print(result.stdout.strip())
```

Resultado esperado: `PyQt6:OK`. Si devuelve `PyQt5:OK (fallback)`, PyQt6 no está accesible desde el subprocess.

#### Fase C — Confirmar visor IFC end-to-end

1. Lanzar el visor IFC desde el dock del plugin.
2. Verificar en los logs que aparece `READY:<win_id>`.
3. Cargar un archivo IFC y confirmar que el visor renderiza correctamente.
4. Verificar que `QTWEBENGINE_CHROMIUM_FLAGS` se propaga al subprocess:

```python
import os
print("CHROMIUM FLAGS:", os.environ.get('QTWEBENGINE_CHROMIUM_FLAGS', 'NO ESTABLECIDO'))
```

---

## Acciones pendientes en el plugin

- [ ] Capturar `returncode != 0` del subprocess y mostrar mensaje claro al usuario con instrucciones de instalación.
- [ ] Añadir detección proactiva de `PyQt5.QtWebEngineWidgets` antes de lanzar el subprocess, con aviso en la barra de mensajes de QGIS.
- [ ] Documentar en el README las instrucciones de instalación de QtWebEngine para QGIS 3 + OSGeo4W.
- [ ] Añadir test de compatibilidad en la matriz de pruebas de `docs/compatibilidad_qgis.md`.
