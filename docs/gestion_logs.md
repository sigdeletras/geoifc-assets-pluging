# Gestion de Logs

## GeoIFC Assets

Este documento define la estrategia de logs del complemento QGIS GeoIFC Assets.

La gestion de logs forma parte de las fases iniciales del desarrollo y debe estar presente desde el MVP. Su objetivo es permitir controlar los flujos que se estan realizando, facilitar diagnostico durante el desarrollo y ofrecer informacion comprensible al usuario final.

Como regla general, debe evitarse al maximo el uso de `print()`.

---

# 1. Tipos de log

El complemento debe diferenciar dos tipos de logs:

```text id="log_types"
developer logs
user logs
```

---

## 1.1 Developer logs

Los developer logs estan orientados a desarrollo, soporte y diagnostico tecnico.

Deben registrar:

* inicio y fin de flujos principales
* errores tecnicos
* excepciones
* version de QGIS
* version IFC detectada
* disponibilidad de Qt WebEngine
* operaciones de lectura IFC
* operaciones de mapeo IFC-GIS
* operaciones de escritura de atributos
* identificador del flujo u operacion

Pueden contener informacion tecnica, pero deben evitar datos sensibles innecesarios.

---

## 1.2 User logs

Los user logs estan orientados al usuario final.

Deben registrar mensajes comprensibles sobre:

* IFC asociado correctamente
* IFC abierto en el visor
* elemento IFC seleccionado
* propiedades cargadas
* campos creados
* atributos actualizados
* advertencias recuperables
* errores que requieren accion del usuario

No deben mostrar:

* trazas internas
* stack traces
* nombres de clases internas
* errores crudos de librerias
* mensajes sin traducir

Los user logs forman parte de la interfaz del complemento y, por tanto, deben estar traducidos a ingles y espanol.

---

# 2. Niveles

Niveles recomendados:

```text id="log_levels"
DEBUG
INFO
WARNING
ERROR
CRITICAL
```

Uso:

* `DEBUG`: diagnostico detallado de desarrollo.
* `INFO`: flujo normal completado o iniciado.
* `WARNING`: situacion recuperable o incompleta.
* `ERROR`: fallo de una operacion concreta.
* `CRITICAL`: fallo que impide continuar o cargar una parte esencial.

---

# 3. Flujos a instrumentar en el MVP

El MVP debe registrar como minimo:

* carga del plugin
* descarga del plugin
* comprobacion de version QGIS
* comprobacion de Qt WebEngine
* seleccion de feature GIS
* asociacion de IFC
* apertura del visor IFC
* lectura de modelo IFC
* seleccion de elemento IFC
* lectura de propiedades IFC
* seleccion de propiedades por el usuario
* mapeo a campos GIS
* creacion de campos
* escritura de atributos
* errores y cancelaciones

---

# 4. Identificador de flujo

Cada operacion relevante debe poder asociarse a un identificador de flujo.

Ejemplos:

```text
associate_ifc
open_ifc_viewer
read_ifc_properties
map_ifc_properties
update_feature_attributes
```

Cuando sea util, se puede usar tambien un identificador unico de operacion para correlacionar mensajes de un mismo proceso.

---

# 5. Politica sobre print()

Regla general:

```text
No usar print() en codigo del plugin.
```

Alternativas:

* logging tecnico para desarrollo
* mensajes de QGIS para usuario
* panel o historial de usuario del complemento
* excepciones controladas en capas internas

Uso excepcional de `print()`:

* scripts de desarrollo ejecutados fuera de QGIS
* pruebas puntuales
* herramientas CLI internas

Cuando se use `print()` fuera del plugin, debe estar justificado por el contexto y no debe aparecer en codigo distribuible del complemento.

---

# 6. Integracion tecnica

La arquitectura debe incluir un puerto de logging para no acoplar el dominio a QGIS.

Ubicacion recomendada:

```text
plugin/geoifc_assets/application/ports/logging_port.py
plugin/geoifc_assets/infrastructure/logging/
```

Reglas:

* `domain` no debe depender de logging concreto.
* `application` puede depender de un puerto de logging.
* `infrastructure/logging` implementa adaptadores concretos.
* `presentation` puede mostrar user logs.
* `infrastructure/qgis` puede integrar logs con mecanismos de QGIS.

---

# 7. Canales recomendados

Para developer logs:

* logger interno Python
* integracion con `QgsMessageLog` cuando aplique

Para user logs:

* panel del complemento
* message bar de QGIS
* mensajes traducibles en dialogs/docks

El mismo evento puede generar:

* un developer log tecnico
* un user log simplificado

Ejemplo conceptual:

```text
developer log:
ERROR read_ifc_properties operation_id=... schema=IFC4X3 exception=...

user log:
No se pudieron leer las propiedades del elemento IFC seleccionado.
```

---

# 8. Datos minimos por entrada

Developer log:

```text
timestamp
level
operation
message
qgis_version opcional
ifc_schema opcional
feature_id opcional
global_id opcional
exception opcional
```

User log:

```text
timestamp
level
operation
translated_message
action_hint opcional
```

---

# 9. Privacidad y seguridad

Los logs no deben incluir datos innecesarios.

Evitar:

* rutas completas si no son necesarias
* URLs con tokens
* credenciales
* datos personales
* contenido masivo de atributos
* dumps completos de modelos IFC

Cuando sea necesario registrar una ruta o URL, preferir versiones resumidas o sanitizadas.

---

# 10. Criterio de aceptacion

La gestion de logs se considera integrada en el MVP si:

* no hay `print()` en codigo distribuible del plugin
* los flujos principales generan developer logs
* los eventos relevantes generan user logs traducibles
* los errores tecnicos quedan disponibles para diagnostico
* el usuario recibe mensajes comprensibles
* los logs no rompen la compatibilidad QGIS 3/4
* los logs no acoplan el dominio a QGIS

