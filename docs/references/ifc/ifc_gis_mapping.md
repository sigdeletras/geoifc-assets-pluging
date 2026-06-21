# Mapeo IFC-GIS

Este documento define criterios iniciales para mapear propiedades IFC a campos GIS.

---

# 1. Principios

El MVP usa mapeo manual:

```text
propiedad IFC seleccionada -> campo GIS elegido por el usuario
```

No se aplican perfiles sectoriales automaticos en el MVP.

---

# 2. Trazabilidad recomendada

Cuando sea posible, el sistema debe conservar informacion de origen:

* version IFC
* clase IFC
* `GlobalId`
* nombre del Property Set
* nombre de la propiedad
* tipo de dato original
* campo GIS destino

---

# 3. Tipos de datos

Reglas iniciales:

| Tipo IFC conceptual | Tipo GIS sugerido |
| --- | --- |
| texto / label / identifier | texto |
| entero | entero |
| real / medida numerica | decimal |
| booleano | booleano o texto controlado |
| fecha | fecha o texto, segun soporte de capa |
| valor desconocido | texto |

---

# 4. Nombres de campos

El plugin debe:

* permitir elegir un campo existente
* proponer un campo nuevo
* normalizar nombres largos
* evitar duplicados
* advertir antes de sobrescribir valores
* respetar restricciones del proveedor de datos GIS

