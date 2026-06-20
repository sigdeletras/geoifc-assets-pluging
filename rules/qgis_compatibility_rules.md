# Reglas de Compatibilidad QGIS 3/4

## Objetivo

El complemento debe estar preparado para QGIS 3 y QGIS 4.

---

## Imports Qt

Usar:

```python
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QAction
```

No usar:

```python
from PyQt5 ...
from PyQt6 ...
```

---

## Enumeraciones

Usar formas compatibles Qt5/Qt6 cuando sea posible:

```python
Qt.ItemDataRole.UserRole
Qt.CursorShape.WaitCursor
Qgis.MessageLevel.Critical
QgsMapLayer.LayerType.VectorLayer
```

---

## Capa de compatibilidad

Las diferencias QGIS 3/4 deben aislarse en:

```text
plugin/geoifc_assets/infrastructure/qgis/compat/
```

---

## Validacion

Antes de release:

* cargar plugin en QGIS 3 LTR
* cargar plugin en QGIS 4.x
* probar visor IFC en ambos
* probar traducciones en ambos
* probar escritura de atributos en ambos

