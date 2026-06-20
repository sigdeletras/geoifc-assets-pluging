# Reglas de Logging

## Objetivo

El complemento debe contar desde fases iniciales con gestion de logs para controlar los flujos que se estan realizando.

---

# 1. Tipos de log

Separar:

* developer logs
* user logs

Developer logs:

* diagnostico tecnico
* excepciones
* flujo interno
* datos de version QGIS/IFC cuando sean utiles

User logs:

* mensajes claros para usuario final
* traducibles a ingles y espanol
* sin stack traces ni detalles internos

---

# 2. No usar print()

Regla general:

```text
No usar print() en codigo distribuible del plugin.
```

Usar logging o mensajes de QGIS.

`print()` solo puede aparecer en:

* scripts internos fuera del plugin
* pruebas
* herramientas CLI de desarrollo

---

# 3. Arquitectura

El dominio no debe depender de QGIS ni de implementaciones concretas de logging.

Ubicacion recomendada:

```text
plugin/geoifc_assets/application/ports/logging_port.py
plugin/geoifc_assets/infrastructure/logging/
```

---

# 4. Flujos minimos

Instrumentar:

* carga y descarga del plugin
* seleccion de feature
* asociacion de IFC
* apertura de visor
* lectura IFC
* seleccion de propiedades
* mapeo a campos GIS
* escritura de atributos
* errores y cancelaciones

---

# 5. Revision

Antes de cerrar una tarea, revisar:

* no se introducen `print()` en el plugin
* los errores generan developer logs
* el usuario recibe mensajes claros
* los user logs son traducibles
* no se registran datos sensibles innecesarios

