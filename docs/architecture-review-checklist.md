# Open Architectural Questions

## Objetivo

Este documento recopila cuestiones arquitectónicas, funcionales y de dominio que no condicionan el MVP actual, pero cuya respuesta puede influir significativamente en la evolución futura del proyecto.

Las preguntas aquí recogidas están abiertas deliberadamente y deben validarse mediante:

* Uso real del complemento.
* Feedback de beta testers.
* Expertos BIM.
* Expertos IFC.
* Expertos en gestión de activos.
* Usuarios SIG.

Las respuestas obtenidas podrán originar nuevos ADRs.

---

# Dominio

## ¿Qué representa realmente una feature GIS?

Posibles interpretaciones:

* Activo.
* Localización.
* Parcela.
* Edificio.
* Infraestructura.
* Entidad GIS genérica.

### Impacto

Condiciona:

* Modelo de dominio.
* Asociación GIS-IFC.
* Navegación futura.
* Gestión de activos.

---

## ¿Debe existir una entidad "Asset" independiente?

Actualmente la feature GIS actúa implícitamente como activo.

Preguntas:

* ¿Es suficiente?
* ¿Será necesario desacoplar activo y geometría?

### Ejemplo

Un mismo activo podría:

* Tener varias geometrías.
* Tener varios IFC.
* Cambiar de representación GIS.

---

# Asociación GIS-IFC

## ¿Debe mantenerse la asociación Feature → IFC File?

Actualmente:

```text
Feature GIS
    ↔
Archivo IFC
```

### Alternativa futura

```text
Feature GIS
    ↔
IfcElement
```

o

```text
Feature GIS
    ↔
Conjunto de IfcElements
```

### Validar con usuarios

* ¿La asociación a fichero completo resulta suficiente?
* ¿Qué casos reales requieren granularidad por elemento?

---

## ¿Es necesario soportar modelos federados?

Ejemplos:

* Arquitectura.
* Estructura.
* Instalaciones.

### Preguntas

* ¿Una feature puede necesitar varios IFC?
* ¿Cómo se presentan al usuario?

---

# Infraestructuras

## ¿Qué nivel de soporte IFC 4.3 es realmente necesario?

Actualmente:

* Lectura genérica soportada.
* Interpretación semántica avanzada no incluida.

### Validar

* Carreteras.
* Ferrocarriles.
* Redes hidráulicas.
* Infraestructuras energéticas.

---

## ¿Qué entidades IFC 4.3 deben priorizarse?

Ejemplos:

* IfcFacility
* IfcFacilityPart
* IfcAlignment
* IfcReferent

---

# Transferencia de atributos

## ¿Los mapeos ad-hoc son suficientes?

Actualmente:

* Selección manual.
* Sin plantillas persistentes.

### Preguntas

* ¿Se repiten patrones de mapeo?
* ¿Son necesarias plantillas reutilizables?

---

## ¿Qué propiedades IFC son realmente relevantes?

Validar:

* Psets más utilizados.
* Qsets más utilizados.
* Propiedades de mantenimiento.
* Propiedades de inventario.

---

# Indicadores agregados

## ¿Qué métricas aportan valor?

Ejemplos:

* Número de plantas.
* Número de espacios.
* Número de puertas.
* Número de ventanas.
* Longitud total.
* Área total.
* Volumen total.

### Preguntas

* ¿Deben almacenarse como atributos GIS?
* ¿Deben calcularse dinámicamente?

---

# Sincronización

## ¿Es suficiente la sincronización unidireccional?

Actualmente:

```text
IFC → GIS
```

### Futuro posible

```text
GIS ↔ IFC
```

### Preguntas

* ¿Existe demanda real?
* ¿Qué casos de uso la justifican?

---

## ¿Cómo gestionar cambios en el IFC?

Opciones:

* Hash.
* Timestamp.
* Versionado.
* Revisión manual.

---

# Escalabilidad

## ¿Cuál es el tamaño real de los modelos utilizados?

Clasificación propuesta:

* Pequeños (<1.000 elementos).
* Medios (1.000-10.000).
* Grandes (>10.000).
* Muy grandes (>100.000).

### Impacto

* Rendimiento.
* Cachés.
* Persistencia.
* Diseño del visor.

---

# Experiencia de usuario

## ¿Qué flujo esperan realmente los usuarios?

Preguntas:

* ¿Empiezan desde GIS?
* ¿Empiezan desde IFC?
* ¿Trabajan simultáneamente en ambos?

### Impacto

Condiciona:

* Diseño de la interfaz.
* Navegación.
* Casos de uso prioritarios.

---

# Criterios para generar nuevos ADR

Una cuestión de este documento debería transformarse en ADR cuando:

* Exista una decisión clara.
* Afecte a la arquitectura.
* Afecte al modelo de dominio.
* Afecte a la persistencia.
* Afecte a la interoperabilidad BIM-SIG.
