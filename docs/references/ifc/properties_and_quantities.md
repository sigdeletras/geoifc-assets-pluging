# Propiedades y Cantidades IFC

Este documento describe como se deben tratar propiedades y cantidades IFC en el MVP.

---

# 1. Fuentes de informacion

El selector de propiedades debe considerar:

* atributos basicos del elemento IFC
* `GlobalId`
* clase IFC
* `Name`
* `Description`
* `ObjectType`
* Property Sets
* Quantity Sets

---

# 2. Property Sets

Los Property Sets agrupan propiedades asociadas a entidades IFC.

Para el MVP, el plugin debe:

* listar Property Sets disponibles
* mostrar nombre de Property Set
* mostrar nombre de propiedad
* mostrar valor
* mostrar tipo de dato cuando sea posible
* permitir seleccion manual de propiedades

---

# 3. Quantity Sets

Los Quantity Sets contienen cantidades declaradas en el modelo.

Para el MVP, el plugin debe leer cantidades existentes, pero no calcular cantidades nuevas.

Ejemplos:

* longitud
* area
* volumen
* recuentos declarados

---

# 4. Ausencia de datos

El plugin debe tratar como normal que:

* un Property Set no exista
* una propiedad no exista
* una cantidad no exista
* un valor sea nulo
* una misma propiedad cambie entre versiones IFC

Estos casos no deben romper el flujo.

