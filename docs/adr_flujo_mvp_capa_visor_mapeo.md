# ADR-002: Flujo MVP de capa GIS, visor IFC y carga de atributos

## Estado

Aceptado para el MVP

## Contexto

El MVP de GeoIFC Assets debe permitir explotar informacion IFC desde QGIS sin imponer una estructura de datos pesada ni un flujo batch inicial. La duda principal es como determinar la capa GIS de trabajo, como acceder al visor IFC y desde donde transferir propiedades IFC a atributos GIS.

Se decide que el complemento no debe asumir una capa fija, pero si debe exigir un contrato minimo de nombres de campo para localizar el IFC de forma consistente. La capa vectorial de trabajo debe contener al menos uno de estos campos: `ifc_path` o `ifc_url`.

## Decision

El MVP se basara en tres decisiones funcionales:

1. La capa GIS de trabajo se configura por seleccion del usuario.
2. El acceso al visor se realiza desde el complemento y, cuando sea viable, mediante una accion de QGIS vinculada a la capa.
3. La carga de propiedades IFC a GIS se realiza desde un flujo asistido con visor y panel lateral, inicialmente sobre el feature seleccionado.

## Capa GIS de trabajo

El complemento debe permitir seleccionar una capa vectorial del proyecto QGIS. La capa seleccionada debe contener al menos un campo normalizado que apunte al IFC:

* `ifc_path`: ruta local o relativa a un fichero IFC
* `ifc_url`: URL a un fichero IFC

Requisitos minimos de la capa:

* Debe ser una capa vectorial cargada en QGIS.
* Debe tener al menos uno de estos campos: `ifc_path` o `ifc_url`.
* Debe permitir lectura de atributos.
* Debe permitir escritura solo si el usuario quiere cargar valores IFC en sus campos.

Si existen ambos campos, el complemento debe aplicar una regla explicita de seleccion. Por defecto se prioriza `ifc_path` para ficheros locales y `ifc_url` para recursos remotos, permitiendo que el usuario confirme cual usar cuando ambos tengan valor.

Para el MVP, la relacion principal es:

```text
feature GIS seleccionado -> ifc_path o ifc_url -> fichero IFC
```

La persistencia granular de un `GlobalId` IFC asociado al feature no forma parte del flujo minimo. El `GlobalId` puede consultarse en el visor y usarse para orientar al usuario, pero no se exige como campo obligatorio de la capa.

## Acceso al visor

El visor debe poder abrirse desde el panel del complemento a partir del feature seleccionado.

La tabla de features del dock incluye un boton **▶** por fila. Pulsar ese boton selecciona el feature y abre el visor IFC directamente para ese feature. Hacer clic en la fila sin pulsar el boton solo selecciona el feature y hace pan del mapa canvas, sin abrir el visor.

El boton "Open Viewer" del panel abre el visor para el feature actualmente seleccionado. Si no hay ningun feature seleccionado o no tiene referencia IFC valida, el sistema muestra un mensaje comprensible y registra el evento en logs.

Cuando la API de QGIS lo permita de forma estable en QGIS 3 y QGIS 4, el complemento podra registrar una accion de capa, por ejemplo:

```text
Abrir IFC en GeoIFC Assets
```

Esta accion deberia estar disponible desde flujos habituales de QGIS como identificacion de elemento, formulario de atributos o menu contextual de feature. La accion debe leer `ifc_path` o `ifc_url` en la capa del feature.

Si no hay feature seleccionado, si la capa no contiene `ifc_path` ni `ifc_url`, o si el campo IFC disponible esta vacio, el complemento debe mostrar un mensaje comprensible al usuario y registrar el evento en logs.

## Carga de propiedades IFC a GIS

La carga de datos se inicia desde el flujo del visor:

1. El usuario selecciona una capa con `ifc_path` o `ifc_url`.
2. El usuario selecciona un feature GIS.
3. El complemento lee `ifc_path` o `ifc_url`.
4. El visor abre el fichero IFC.
5. El usuario selecciona un elemento IFC o consulta el arbol/listado de propiedades.
6. Un panel lateral muestra atributos basicos, Property Sets y Quantity Sets.
7. El usuario marca una o varias propiedades.
8. El usuario asigna cada propiedad a un campo GIS existente o confirma la creacion de un campo nuevo.
9. El complemento valida tipos, permisos de edicion y posibles sobrescrituras.
10. El complemento escribe los valores en el feature seleccionado.
11. El complemento registra logs de desarrollo y logs de usuario final.

El MVP se limita al feature seleccionado. La aplicacion del mismo mapeo a varios features seleccionados o a una capa completa se considera evolutiva porque introduce comportamiento batch, gestion de errores agregada, confirmaciones mas complejas y mayor riesgo de modificar datos masivamente.

## Consecuencias

### Positivas

* Reduce la configuracion inicial del usuario.
* Simplifica la validacion, la accion de capa y la documentacion de uso.
* Hace explicito el contrato minimo que debe cumplir la capa GIS.
* Encaja con flujos naturales de QGIS basados en seleccion e identificacion de features.
* Mantiene el MVP centrado en visualizacion, consulta y carga manual controlada.
* Permite evolucionar hacia acciones masivas sin bloquear el diseno inicial.

### Negativas

* Las capas existentes que usen otros nombres de campo deberan adaptarse antes de usar el complemento.
* El complemento debe informar claramente cuando falten `ifc_path` e `ifc_url`.
* No existe automatizacion inicial para completar muchas features.
* El flujo depende de que el valor del campo IFC este correctamente informado.
* La accion de capa puede requerir ajustes especificos de compatibilidad entre QGIS 3 y QGIS 4.

## Evolutivos relacionados

Quedan fuera del MVP:

* aplicar mapeos a todas las features seleccionadas
* aplicar mapeos a una capa completa
* guardar plantillas reutilizables de mapeo
* perfiles sectoriales
* persistir relaciones granulares feature GIS -> elemento IFC
* procesamiento batch con resumen de errores
