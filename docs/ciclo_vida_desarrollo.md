# Ciclo de Vida del Desarrollo

## GeoIFC Assets

Este documento define el ciclo de vida de desarrollo del complemento QGIS GeoIFC Assets. Su objetivo es establecer una forma de trabajo repetible, trazable y preparada para publicar el proyecto en GitHub.

El desarrollo del codigo se realizara siempre en ingles. La documentacion del repositorio se mantiene en espanol, salvo el README, que debe estar disponible en ingles y espanol.

---

# 1. Principios del ciclo de vida

El ciclo de vida del desarrollo debe cumplir estos principios:

* Trazabilidad entre historias de usuario, casos de uso, codigo y pruebas.
* Separacion clara entre la carpeta instalable del plugin y los recursos del repositorio.
* Desarrollo preparado para editores agenticos como Codex, Cursor y Claude.
* Entregas pequenas, verificables y empaquetables.
* Interfaz traducible desde el inicio.
* Gestion de logs desde las fases iniciales.
* Validacion continua en entorno QGIS.
* Compatibilidad mantenida con QGIS 3 y QGIS 4.
* Documentacion actualizada junto con los cambios funcionales.
* Priorizacion del MVP antes de funcionalidades evolutivas.

---

# 2. Flujo general

```text id="development_lifecycle"
Idea / requisito
  |
Historia de usuario
  |
Analisis funcional
  |
Diseno tecnico
  |
Implementacion
  |
Pruebas
  |
Revision
  |
Empaquetado
  |
Validacion en QGIS
  |
Release
  |
Mantenimiento
```

---

# 3. Fases del ciclo de vida

## 3.1 Identificacion de requisitos

Entrada:

* necesidad funcional
* cambio tecnico
* correccion de error
* mejora de documentacion

Salida:

* requisito descrito
* alcance definido
* decision sobre si pertenece al MVP o a evolutivo

Artefactos:

* `docs/plan_desarrollo.md`
* historias de usuario
* decisiones tecnicas cuando aplique
* instrucciones agenticas cuando el cambio afecte al flujo de trabajo

---

## 3.2 Definicion de historia de usuario

Cada funcionalidad relevante debe expresarse como historia de usuario:

```text
Como [rol],
quiero [capacidad],
para [valor esperado].
```

Cada historia debe incluir criterios de aceptacion verificables.

Estados posibles:

* propuesta
* lista para desarrollo
* en desarrollo
* en revision
* validada
* cerrada
* descartada

Una historia esta lista para desarrollo cuando:

* tiene actor identificado
* tiene valor funcional claro
* tiene criterios de aceptacion
* no depende de decisiones abiertas criticas
* esta clasificada como MVP o evolutiva

---

## 3.3 Analisis funcional

En esta fase se concreta como debe comportarse el complemento desde el punto de vista del usuario.

Debe responder:

* que accion realiza el usuario
* que datos necesita el sistema
* que resultado se espera
* que errores pueden ocurrir
* que eventos deben registrarse como logs
* que textos visibles deben traducirse
* que campos GIS se leen o escriben

Salida esperada:

* caso de uso funcional
* criterios de validacion
* impacto en interfaz
* impacto en datos

---

## 3.4 Diseno tecnico

En esta fase se decide donde vive el cambio dentro de la arquitectura.

Debe identificar:

* capa afectada: `core`, `adapters`, `services`, `webviewer` o `i18n`
* clases o servicios implicados
* dependencias externas
* impacto en traducciones
* impacto en compatibilidad QGIS 3/4
* impacto en developer logs y user logs
* impacto en empaquetado
* pruebas necesarias

Regla general:

* La logica pura debe quedar en `core/`.
* La integracion con QGIS debe quedar en `adapters/qgis/`.
* La lectura IFC debe quedar en `adapters/ifc/`.
* Los servicios transversales, como logging, deben quedar en `services/`.
* No se deben crear `domain/`, `application/`, `infrastructure/`, `presentation/`, puertos, DTOs o casos de uso si solo anaden ceremonia sin logica real.

---

## 3.5 Implementacion

La implementacion debe seguir estas reglas:

* Codigo, nombres tecnicos y tests en ingles.
* Textos visibles extraidos a sistema de traduccion.
* Cambios pequenos y revisables.
* Sin mezclar refactorizaciones no relacionadas.
* Sin incluir `docs/`, `tests/`, `rules/`, `scripts/` ni `.github/` dentro del paquete del plugin.
* Sin incluir `.cursor/`, `.agents/`, `AGENTS.md` ni `CLAUDE.md` dentro del paquete del plugin.
* Sin usar `print()` como mecanismo normal de logging en codigo distribuible del plugin.

Para cada cambio funcional se debe revisar si afecta a:

* interfaz de usuario
* traducciones
* modelo de datos de capa GIS
* visor web
* lectura IFC
* compatibilidad QGIS 3/4
* gestion de logs
* empaquetado
* documentacion

---

## 3.6 Pruebas

Las pruebas se organizan en niveles:

```text id="test_levels"
unit
integration
qgis
manual_validation
```

Pruebas unitarias:

* dominio
* casos de uso
* validadores
* mapeo de propiedades IFC a campos GIS

Pruebas de integracion:

* lectura de IFC con fixtures
* conversion de propiedades a valores normalizados
* preparacion de escritura en atributos GIS

Pruebas QGIS:

* carga del plugin
* apertura de dock/dialogs
* lectura de feature seleccionado
* escritura controlada de atributos
* validacion en QGIS 3 LTR
* validacion en QGIS 4.x

Validacion manual:

* abrir QGIS
* instalar o cargar el plugin
* asociar un IFC a un feature
* abrir el visor
* seleccionar propiedades
* mapear campos
* escribir atributos
* revisar developer logs y user logs esperados
* cambiar idioma ingles/espanol
* repetir el flujo minimo en QGIS 3 y QGIS 4

---

# 4. Revision y calidad

Antes de integrar un cambio, se debe comprobar:

* la historia de usuario relacionada queda cubierta
* los criterios de aceptacion se cumplen
* no hay textos visibles sin traducir
* no hay `print()` en codigo distribuible del plugin
* los flujos principales generan logs adecuados
* el codigo respeta la arquitectura
* el codigo respeta las reglas de compatibilidad QGIS 3/4
* las pruebas relevantes pasan
* la documentacion afectada se actualiza
* las instrucciones agenticas se actualizan si cambia el flujo de trabajo
* el plugin sigue siendo empaquetable

Herramientas previstas:

* `ruff`
* `mypy`
* `pytest`
* `pytest-qt`
* scripts de empaquetado
* validacion manual en QGIS LTR

---

# 5. Gestion de ramas

Estrategia recomendada:

```text id="branching"
main
develop
feature/*
fix/*
docs/*
release/*
```

Uso:

* `main`: versiones estables publicables.
* `develop`: integracion de trabajo validado.
* `feature/*`: nuevas funcionalidades.
* `fix/*`: correcciones.
* `docs/*`: cambios de documentacion.
* `release/*`: preparacion de version.

Cada rama debe tener un alcance concreto y relacionarse con una historia, caso de uso, bug o tarea documental.

---

# 6. Definicion de hecho

Una tarea se considera terminada cuando:

* el codigo esta implementado
* los criterios de aceptacion se cumplen
* las pruebas aplicables pasan
* la interfaz esta traducida a ingles y espanol si hay textos visibles
* los flujos principales registran logs adecuados
* no se introducen `print()` en el plugin
* el cambio esta validado o preparado para QGIS 3 y QGIS 4
* la documentacion afectada esta actualizada
* el cambio respeta la estructura del repositorio
* el plugin se puede empaquetar sin incluir carpetas no distribuibles

Para una funcionalidad MVP, ademas debe existir validacion manual en QGIS 3 LTR y QGIS 4.x.

---

# 7. Empaquetado

El empaquetado debe generar un ZIP con la carpeta:

```text
geoifcassets/
```

El paquete debe incluir solo lo necesario para ejecutar el complemento en QGIS:

* codigo del plugin
* `metadata.txt`
* recursos
* visor web
* traducciones compiladas
* assets necesarios en ejecucion

No debe incluir:

* `docs/`
* `tests/`
* `rules/`
* `scripts/`
* `.github/`
* `.cursor/`
* `.agents/`
* `AGENTS.md`
* `CLAUDE.md`
* archivos de desarrollo del repositorio

---

# 8. Release

Una version publicable debe tener:

* numero de version
* changelog actualizado
* ZIP del plugin validado
* pruebas relevantes ejecutadas
* validacion manual en QGIS 3 LTR
* validacion manual en QGIS 4.x
* traducciones compiladas
* logs revisados
* documentacion minima de instalacion y uso

Flujo de release:

```text id="release_flow"
release branch
  |
version bump
  |
changelog
  |
tests
  |
package
  |
manual QGIS validation
  |
tag
  |
GitHub release
```

---

# 9. Mantenimiento

El mantenimiento incluye:

* correccion de errores
* adaptacion a nuevas versiones de QGIS LTR
* actualizacion de dependencias
* mejora de traducciones
* ampliacion de documentacion
* incorporacion progresiva de perfiles sectoriales

Toda mejora evolutiva debe volver al inicio del ciclo:

```text
requisito -> historia -> analisis -> diseno -> implementacion -> pruebas -> release
```

---

# 10. Relacion con el MVP

Para el MVP, el ciclo de vida se aplicara a estas capacidades:

* asociar IFC a feature GIS
* abrir visor IFC embebido
* seleccionar elemento IFC
* consultar propiedades
* seleccionar propiedades IFC
* mapear propiedades a campos GIS
* crear campos controladamente
* escribir atributos GIS
* usar la interfaz en ingles y espanol
* ejecutar el flujo en QGIS 3 y QGIS 4
* registrar logs de desarrollo y usuario
* empaquetar el complemento desde la carpeta `geoifcassets/`

Los perfiles sectoriales quedan fuera del MVP y se gestionaran como funcionalidades evolutivas.
