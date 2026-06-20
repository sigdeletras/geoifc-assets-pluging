# Reglas de Desarrollo Agentico

## GeoIFC Assets

Este documento define como deben trabajar los asistentes agenticos dentro del repositorio.

Aplica a Codex, Cursor, Claude y herramientas equivalentes.

---

# 1. Fuentes de verdad

Antes de proponer o implementar cambios, el agente debe consultar:

* `AGENTS.md`
* `docs/plan_desarrollo.md`
* `docs/ciclo_vida_desarrollo.md`
* `docs/compatibilidad_qgis.md`
* reglas especificas en `rules/`

---

# 2. Orden de trabajo

El flujo recomendado es:

```text
leer contexto
  |
identificar alcance
  |
localizar archivos afectados
  |
implementar cambio minimo
  |
actualizar pruebas o documentacion
  |
validar
  |
resumir resultado
```

---

# 3. Limites

El agente no debe:

* mezclar cambios funcionales con refactorizaciones no pedidas
* mover documentacion dentro de la carpeta instalable del plugin
* introducir textos visibles sin traduccion
* introducir `print()` como logging del plugin
* introducir imports directos `PyQt5` o `PyQt6`
* introducir dependencias de QGIS dentro del dominio
* asumir que una propiedad IFC existe en todas las versiones IFC
* cambiar el alcance MVP sin actualizar el plan

---

# 4. Criterios antes de cerrar una tarea

El agente debe indicar:

* archivos modificados
* pruebas ejecutadas
* pruebas no ejecutadas y motivo
* cambios documentales
* impacto en logs
* riesgos pendientes

---

# 5. Convenciones de instrucciones por herramienta

Archivos usados por agentes:

* `AGENTS.md`: instrucciones comunes para Codex y otros agentes.
* `CLAUDE.md`: instrucciones especificas para Claude.
* `.cursor/rules/*.mdc`: reglas especificas para Cursor.
* `.agents/`: contexto y plantillas auxiliares para agentes.

Si se cambia una regla importante, actualizar todas las superficies afectadas.
