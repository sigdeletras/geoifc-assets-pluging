# Reglas del Plugin QGIS

## Carpeta instalable

Solo esta carpeta debe empaquetarse como plugin:

```text
plugin/geoifc_assets/
```

El ZIP final debe contener:

```text
geoifc_assets/
```

No incluir en el ZIP:

* `docs/`
* `tests/`
* `rules/`
* `scripts/`
* `.github/`
* `.cursor/`
* `.agents/`
* `AGENTS.md`
* `CLAUDE.md`

---

## Metadata

`metadata.txt` debe estar en UTF-8.

Si el mismo paquete soporta QGIS 3 y QGIS 4:

```ini
qgisMinimumVersion=3.0
qgisMaximumVersion=4.99
```

`metadata.txt` debe estar disponible en ingles y espanol cuando el mecanismo de QGIS lo permita.

---

## Carga del plugin

El plugin no debe fallar al cargar si:

* no hay capa activa
* no hay feature seleccionado
* falta Qt WebEngine
* falta un IFC asociado

Debe mostrar mensajes claros al usuario.

---

## Logging

El plugin no debe usar `print()` como mecanismo normal de diagnostico.

Debe usar la estrategia de logs definida en:

* `docs/gestion_logs.md`
* `rules/logging_rules.md`
