# ADR - Arquitectura Hexagonal Ligera

## Estado

Aceptada.

## Contexto

GeoIFC Assets es un complemento de QGIS. Necesita aislar dependencias externas como QGIS, Qt/PyQt, IfcOpenShell, visor web, logging e internacionalizacion.

La arquitectura hexagonal completa aporta una buena orientacion, pero puede convertirse en sobrearquitectura si se traduce desde el inicio en muchas carpetas, puertos, DTOs y casos de uso para operaciones simples.

El objetivo es conservar lo importante de la arquitectura hexagonal:

* un nucleo libre de QGIS, PyQt e IfcOpenShell
* adaptadores para dependencias externas
* testabilidad de la logica pura
* facilidad de evolucion

sin imponer una estructura pesada.

## Decision

El desarrollo usara una **arquitectura hexagonal ligera** basada en:

```text
nucleo puro + adaptadores QGIS/IFC + servicios transversales
```

La estructura base sera:

```text
geoifcassets/
    __init__.py
    main.py
    metadata.txt
    icon.svg

    core/
        __init__.py
        models.py
        mapping.py
        validation.py

    adapters/
        __init__.py
        qgis/
            __init__.py
            plugin.py
            dock.py
            feature_reader.py
            messages.py
            i18n.py
            compat.py
        ifc/
            __init__.py
            reader.py

    services/
        __init__.py
        logging.py

    webviewer/
        index.html

    i18n/
        geoifcassets_en.ts
        geoifcassets_es.ts
```

## Reglas

### Core

`core/` contiene logica pura del complemento.

No debe importar:

* QGIS
* PyQt
* IfcOpenShell
* visor web

Puede contener:

* modelos simples
* validaciones
* reglas de mapeo IFC-GIS
* normalizacion de valores
* errores propios del dominio

### Adapters

`adapters/` contiene integraciones con el exterior.

`adapters/qgis/` contiene:

* carga del plugin
* docks/dialogs
* lectura de capa y feature seleccionado
* escritura futura de atributos
* mensajes QGIS
* i18n Qt/QGIS
* compatibilidad QGIS 3/4

`adapters/ifc/` contiene:

* lectura IFC
* adaptacion de IfcOpenShell
* extraccion cruda de propiedades

### Services

`services/` contiene servicios transversales que no pertenecen claramente al nucleo ni a un adaptador concreto.

Inicialmente:

* logging

## Lo que no se hara al inicio

No se crearan de entrada:

* `domain/`
* `application/`
* `infrastructure/`
* `presentation/`
* `ports/`
* `dto/`
* `use_cases/`

Estas carpetas solo se incorporaran si el crecimiento del proyecto lo justifica claramente.

## Criterio de evolucion

Crear una abstraccion adicional solo si:

* aisla una dependencia externa relevante
* permite probar logica sin QGIS/Qt/IfcOpenShell
* contiene una regla funcional real
* reduce duplicacion real
* mejora la legibilidad de un flujo que ya ha crecido

Evitar abstracciones que:

* solo pasan datos de A a B
* existen solo por simetria arquitectonica
* obligan a saltar por muchos archivos para entender una operacion simple

## Consecuencias

Ventajas:

* mantiene aislamiento entre nucleo y dependencias externas
* reduce friccion de mantenimiento
* facilita empezar el MVP
* mantiene testabilidad de la logica importante
* evita sobrearquitectura prematura

Costes:

* requiere criterio para decidir cuando extraer nuevas capas
* hay menos simetria formal que en una hexagonal completa
* las revisiones deben vigilar que QGIS/Qt/IfcOpenShell no entren en `core/`

