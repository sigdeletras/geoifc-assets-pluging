# Compatibilidad QGIS 3 y QGIS 4

## GeoIFC Assets

Este documento define la estrategia de compatibilidad del complemento GeoIFC Assets con QGIS 3 y QGIS 4.

El complemento debe estar preparado para funcionar tanto en QGIS 3 como en QGIS 4. Esta decision afecta a arquitectura, imports Qt/PyQt, APIs PyQGIS, visor embebido, traducciones, empaquetado, pruebas y metadata del plugin.

---

# 1. Contexto

QGIS 4.0 fue publicado el 6 de marzo de 2026 y representa una migracion tecnica del nucleo de QGIS al framework Qt6. QGIS indica que se han mantenido APIs obsoletas cuando ha sido posible para facilitar la transicion de plugins, pero los complementos deben revisarse para compatibilidad Qt5/Qt6.

Fuentes principales:

* QGIS 4.0 Changelog: https://changelog.qgis.org/en/version/4.0/
* QGIS Qt5/Qt6 plugin migration guide: https://github.com/qgis/QGIS/wiki/Plugin-migration-to-be-compatible-with-Qt5-and-Qt6
* QGIS PyQGIS plugin documentation: https://docs.qgis.org/3.44/en/docs/pyqgis_developer_cookbook/plugins/plugins.html

---

# 2. Versiones objetivo

## 2.1 Soporte funcional

El objetivo del proyecto es soportar:

* QGIS 3.x LTR
* QGIS 4.x

La version exacta de certificacion se definira en cada release.

Para el MVP se recomienda validar como minimo:

* una version QGIS 3 LTR
* una version QGIS 4 estable

---

## 2.2 Politica de metadata

Si el mismo paquete del plugin debe cargarse en QGIS 3 y QGIS 4, `metadata.txt` debe declarar explicitamente:

```ini
qgisMinimumVersion=3.0
qgisMaximumVersion=4.99
```

La guia de migracion Qt5/Qt6 de QGIS indica que, si un plugin soporta mas de una version mayor de QGIS, se debe establecer explicitamente `qgisMaximumVersion`; de lo contrario, QGIS 4 puede no cargar el plugin.

Esta politica debe revisarse antes de cada release.

---

# 3. Reglas tecnicas

## 3.1 Imports Qt/PyQt

El plugin debe importar Qt desde los wrappers de QGIS:

```python
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QAction
```

No se deben usar imports directos de:

```python
from PyQt5 ...
from PyQt6 ...
```

salvo que exista una justificacion tecnica documentada y encapsulada.

---

## 3.2 Enumeraciones compatibles

El codigo debe usar formas compatibles con PyQt5/PyQt6 y QGIS 3/4.

Ejemplos:

```python
Qt.ItemDataRole.UserRole
Qt.CursorShape.WaitCursor
Qgis.MessageLevel.Critical
QgsMapLayer.LayerType.VectorLayer
```

Evitar formas antiguas si existen equivalentes compatibles:

```python
Qt.UserRole
Qt.WaitCursor
Qgis.Critical
QgsMapLayer.VectorLayer
```

---

## 3.3 Capa de compatibilidad

El codigo dependiente de diferencias QGIS 3/4 debe aislarse en:

```text
geoifcassets/infrastructure/qgis/compat/
```

Esta capa debe incluir:

* deteccion de version QGIS
* helpers para diferencias de API
* wrappers de acciones, mensajes y dialogs si son necesarios
* comprobaciones de disponibilidad de Qt WebEngine

La logica de dominio y casos de uso no debe depender de la version de QGIS.

---

## 3.4 Visor embebido

El visor IFC embebido debe comprobar:

* disponibilidad de Qt WebEngine
* comportamiento de `QWebEngineView` en QGIS 3
* comportamiento de `QWebEngineView` en QGIS 4
* comunicacion QWebChannel en ambos entornos

Si alguna version de QGIS no incluye WebEngine en una instalacion concreta, el plugin debe mostrar un error claro y no fallar durante la carga.

---

## 3.5 Traducciones

Las traducciones deben compilarse y cargarse correctamente en QGIS 3 y QGIS 4.

Debe comprobarse:

* carga de `.qm`
* locale activo de QGIS
* textos de menus
* textos de docks/dialogs
* mensajes de error
* textos visibles del visor embebido

---

# 4. Pruebas de compatibilidad

La matriz minima de validacion debe cubrir:

```text id="qgis_compat_matrix"
QGIS 3 LTR + Windows
QGIS 4.x   + Windows
```

Cuando sea posible, ampliar a:

```text
QGIS 3 LTR + Linux
QGIS 4.x   + Linux
```

Pruebas obligatorias:

* el plugin carga sin errores
* el dock principal se abre
* la traduccion funciona en ingles y espanol
* se puede seleccionar un feature
* se puede leer `ifc_path` o `ifc_url`
* se puede abrir el visor IFC
* se pueden consultar propiedades IFC
* se pueden mapear propiedades a campos GIS
* se pueden escribir atributos
* el plugin se descarga sin errores al cerrar QGIS

---

# 5. Checklist antes de release

Antes de publicar una version:

* `metadata.txt` revisado para QGIS 3/4.
* Sin imports directos `PyQt5` o `PyQt6`.
* Enumeraciones compatibles Qt5/Qt6.
* Capa `infrastructure/qgis/compat/` revisada.
* Validacion manual en QGIS 3 LTR.
* Validacion manual en QGIS 4.x.
* Visor IFC probado en ambos entornos.
* Traducciones ingles/espanol probadas en ambos entornos.
* ZIP del plugin probado en ambos entornos.

---

# 6. Criterio de decision

Si una funcionalidad no puede ser compatible simultaneamente con QGIS 3 y QGIS 4, se debe:

1. aislar la diferencia en la capa de compatibilidad
2. documentar la limitacion
3. degradar la funcionalidad de forma controlada
4. evitar que el plugin falle al cargar

La prioridad del MVP es mantener un mismo codigo base compatible con QGIS 3 y QGIS 4.
