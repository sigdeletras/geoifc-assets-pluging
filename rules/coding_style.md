# Reglas de Estilo de Codigo

## Idioma

El codigo se escribe en ingles:

* nombres de archivos Python
* modulos
* paquetes
* clases
* funciones
* variables
* tests
* logs
* comentarios tecnicos

La documentacion del repositorio se escribe en espanol, salvo README.

---

## Python

Reglas base:

* usar type hints
* preferir funciones pequenas
* evitar efectos laterales ocultos
* no ocultar errores sin registrarlos
* no usar `print()` como mecanismo de logging del plugin
* no usar dependencias globales si pueden inyectarse
* mantener la logica de negocio fuera de la UI

Herramientas previstas:

* `ruff`
* `mypy`
* `pytest`

---

## Logging

Usar la estrategia definida en `docs/gestion_logs.md` y `rules/logging_rules.md`.

Evitar `print()` en codigo distribuible del plugin.

---

## Comentarios

Usar comentarios solo cuando expliquen una decision o una parte no obvia.

Evitar comentarios que repitan literalmente lo que hace el codigo.
