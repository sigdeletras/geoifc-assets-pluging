# Selector de Plantas y Vista 2D — Visor IFC

## Objetivo

Permitir al usuario filtrar la escena 3D del visor IFC por planta (`IfcBuildingStorey`) y activar
una vista cenital ortogonal (modo 2D) para revisar la planta seleccionada como si fuera un plano
de planta arquitectónico.

Esto facilita la navegación en modelos con varias plantas, la identificación de elementos por nivel
y la consulta de propiedades BIM en contexto de planta.

---

## Funcionalidades

### F1 — Selector de plantas (storey bar)

Una barra de filtro horizontal aparece debajo de los botones Category/Spatial, visible únicamente
cuando el modelo IFC contiene al menos una entidad `IfcBuildingStorey`.

- El botón **All** muestra todas las plantas (estado por defecto al cargar un IFC).
- Un botón por cada planta detectada, con el nombre del `IfcBuildingStorey`.
- Al pulsar una planta:
  - Los meshes de elementos que pertenecen a esa planta se hacen **visibles**.
  - El resto de meshes se ocultan (`mesh.visible = false`).
  - La cámara hace fit automático a la bounding box de los elementos visibles.
- El botón activo se distingue visualmente.
- Al pulsar **All** se restaura la visibilidad completa.

La barra desaparece al limpiar el modelo (al seleccionar un feature GIS diferente).

### F2 — Vista 2D cenital (toggle 2D/3D)

Un botón **2D** flota en la esquina superior derecha del canvas. Aparece cuando hay un modelo cargado.

- **Modo 2D:**
  - La cámara se reposiciona directamente sobre el centro de los elementos visibles (eje Y ascendente).
  - El vector up de la cámara cambia a `(0, 0, −1)` para evitar singularidad gimbal en vista cenital.
  - La rotación de órbita se desactiva (`controls.enableRotate = false`).
  - El panning pasa a modo pantalla (`controls.screenSpacePanning = true`).
  - El botón cambia a **3D** con fondo verde para indicar el modo activo.

- **Modo 3D** (estado por defecto):
  - Se recupera la posición de cámara guardada antes de entrar en 2D.
  - El vector up se restaura a `(0, 1, 0)`.
  - La rotación de órbita se reactiva.
  - El botón vuelve a mostrar **2D**.

Si se cambia de planta estando en modo 2D, el fit de cámara se adapta a la bounding box de la
nueva selección manteniendo la vista cenital.

---

## Implementación técnica

### Archivos modificados

| Archivo | Cambios |
|---|---|
| `webviewer_src/index.html` | Añade `#storey-bar` (panel lateral) y `#btn-view-2d` (canvas) |
| `webviewer_src/src/viewer.ts` | Lógica de filtro, índice de plantas, cambio de cámara |
| `webviewer_src/src/viewer.css` | Estilos para `.storey-bar`, `.storey-btn` y `.view-toggle-btn` |

El bundle compilado se genera en `geoifcassets/webviewer/assets/index.js` con `npm run build:webviewer`.

No se modifican archivos Python ni la lógica del servidor HTTP.

---

### Estado nuevo en `viewer.ts`

```typescript
// Storey filter state
let storeys: SpatialNode[] = [];
const elementToStorey = new Map<number, number>(); // expressId → storey expressId
let activeStoreyId: number | null = null;

// 2D view state
let is2DView = false;
let saved3DCamera: { pos: THREE.Vector3; target: THREE.Vector3 } | null = null;
```

---

### Índice de plantas (`buildStoreyIndex`)

Se construye **una vez** tras `buildSpatialTree`, recorriendo el árbol espacial. Para cada nodo
de tipo `storey` extrae recursivamente todos los `expressId` de elementos contenidos (incluyendo
los de sub-espacios dentro de la planta).

Mapa resultante:

```
elementToStorey: Map<expressId_elemento, expressId_planta>
storeys: SpatialNode[]  — todas las plantas en orden de aparición en el árbol
```

El orden de las plantas en la barra refleja el orden en `IfcRelAggregates`, que en ficheros IFC
bien formados va de planta baja a cubierta.

---

### Filtrado por planta (`filterByStorey`)

Recorre `modelGroup.traverse()` y aplica `mesh.visible` en función de si el `expressId` del mesh
aparece en el conjunto de elementos de la planta seleccionada.

Complejidad: O(N_meshes) por filtrado. En modelos grandes con >10.000 meshes esto puede tardar
~100–200 ms; es aceptable para interacción de usuario.

Tras filtrar, calcula la bounding box de los meshes visibles y llama a `fitCameraToBox` (modo 3D)
o `fitCamera2DToBox` (modo 2D).

---

### Vista cenital (`fitCamera2DToBox`)

Posiciona la cámara sobre el centro XZ de la bounding box, a una distancia equivalente a
`maxExtent * 2 + elevaciónPlanta * 0.5`. No cambia el FOV ni el tipo de cámara (sigue siendo
`PerspectiveCamera`). La perspectiva es mínima desde esa distancia y el resultado visual es
prácticamente ortogonal para modelos de edificación estándar.

---

### Elementos DOM añadidos

```html
<!-- En el canvas (viewport) -->
<button class="view-toggle-btn" id="btn-view-2d" hidden title="Switch to 2D top-down view">2D</button>

<!-- En el panel lateral, entre .tree-mode-bar y #element-tree -->
<div class="storey-bar" id="storey-bar" hidden aria-label="Floor / storey filter"></div>
```

---

## Limitaciones y riesgos

| Limitación | Detalle |
|---|---|
| Elementos sin planta | Elementos sin `IfcRelContainedInSpatialStructure` no tienen storey asignado y se ocultan en todos los filtros de planta. Siempre se ven con **All**. |
| Cámara en 2D | Se usa `PerspectiveCamera` reposicionada, no `OrthographicCamera`. Con modelos muy anchos puede haber ligera distorsión en bordes. |
| Orden de plantas | El orden sigue el árbol `IfcRelAggregates`. En IFC mal formados puede no ser ascendente por cota. |
| Modelos sin espacial | Si el IFC no tiene estructura espacial, la barra de plantas no aparece. |
| Vista 2D al cambiar de IFC | Al limpiar el modelo se restaura automáticamente el modo 3D. |

---

## Verificación manual

1. Cargar un IFC con varias plantas (p.ej. `Duplex_A_20110907.ifc`).
2. Verificar que aparece la barra de plantas con un botón por planta más **All**.
3. Pulsar una planta → sólo se ven los elementos de esa planta; la cámara hace fit.
4. Pulsar **All** → se restauran todos los elementos.
5. Pulsar **2D** → la cámara sube al cénit y se desactiva la rotación.
6. Intentar orbitar en modo 2D → no debe rotar, sólo pan y zoom.
7. Pulsar **3D** → la cámara vuelve a la posición guardada antes de entrar en 2D.
8. Combinar: seleccionar planta + activar 2D → vista de plano de planta.
9. Cambiar de planta en modo 2D → el fit se adapta y mantiene la vista cenital.
10. Cargar un IFC sin estructura espacial → la barra de plantas no aparece; el botón 2D sí.

---

## Relación con el plan de desarrollo

Esta funcionalidad extiende el **Módulo de visualización IFC** (sección 5.1 de `plan_desarrollo.md`)
añadiendo capacidades de navegación espacial por planta al visor ya implementado.

No forma parte del MVP de carga de propiedades IFC→GIS (HU-01 a HU-11), pero es un evolutivo
directo de la Fase B (árbol espacial) que reutiliza la estructura `SpatialNode` y el índice
`IfcRelContainedInSpatialStructure` ya construidos al cargar el modelo.

Se relaciona con **HU-E04** (huella geográfica de planta) pero no la implementa: aquí solo se
filtra la visualización 3D, no se genera geometría GIS.
