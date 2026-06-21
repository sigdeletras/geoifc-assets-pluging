# GeoIFC Assets

GeoIFC Assets es un complemento de QGIS para conectar activos GIS con modelos IFC.

El proyecto esta en fase inicial de desarrollo. La fase 1 proporciona la base
instalable del complemento QGIS, estructura del proyecto, servicio de logs,
estructura inicial de traducciones, scripts de validacion y el contrato inicial
de capa usado por el MVP.

## MVP

El MVP permitira:

* seleccionar una capa GIS que contenga `ifc_path` o `ifc_url`
* abrir el IFC referenciado por el feature GIS seleccionado
* abrir el IFC en un visor embebido
* seleccionar elementos IFC
* consultar propiedades IFC
* mapear propiedades IFC seleccionadas a campos GIS
* escribir valores seleccionados en atributos GIS
* registrar operaciones principales para desarrollo y usuario final

La capa GIS seleccionada debe contener al menos uno de estos campos:

* `ifc_path`: ruta local o relativa al fichero IFC
* `ifc_url`: URL del fichero IFC

## Desarrollo

El codigo se escribe en ingles.

La documentacion del repositorio se escribe en espanol.

La interfaz del plugin, metadata y README se mantienen en ingles y espanol.

El codigo del plugin debe usar la estrategia de logs en lugar de diagnostico con `print()`.

Instrucciones para agentes:

* `AGENTS.md`
* `CLAUDE.md`
* `.cursor/rules/`

Comandos utiles:

* `.\scripts\run_tests.ps1`
* `.\scripts\lint.ps1`
* `.\scripts\package_plugin.ps1`
