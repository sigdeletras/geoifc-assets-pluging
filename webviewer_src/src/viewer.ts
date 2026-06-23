import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import {
  IfcAPI,
  type FlatMesh,
  type PlacedGeometry,
  IFCWALL, IFCWALLSTANDARDCASE,
  IFCDOOR, IFCDOORSTANDARDCASE,
  IFCWINDOW, IFCWINDOWSTANDARDCASE,
  IFCSLAB, IFCPLATE,
  IFCBEAM,
  IFCCOLUMN, IFCCOLUMNSTANDARDCASE,
  IFCMEMBER,
  IFCROOF,
  IFCSTAIR, IFCSTAIRFLIGHT,
  IFCRAMP,
  IFCRAILING,
  IFCCOVERING,
  IFCCURTAINWALL,
  IFCFURNISHINGELEMENT,
  IFCSPACE,
  IFCBUILDINGSTOREY,
  IFCSITE,
  IFCBUILDING,
  IFCPILE, IFCFOOTING,
  IFCBUILDINGELEMENTPROXY,
  IFCFLOWSEGMENT, IFCFLOWTERMINAL, IFCFLOWFITTING, IFCFLOWCONTROLLER,
  IFCDUCTSEGMENT, IFCPIPESEGMENT, IFCPIPEFITTING,
  IFCRELDEFINESBYPROPERTIES,
  IFCRELAGGREGATES,
  IFCRELCONTAINEDINSPATIALSTRUCTURE,
  IFCPROJECT,
} from "web-ifc";

import "./viewer.css";

// ── Types ─────────────────────────────────────────────────────────────────────

type ViewerPayload = {
  kind?: string;
  source?: string;
  dataBase64?: string;
  modelUrl?: string;
};

type ViewMode = "category" | "spatial";

interface IFCElement {
  expressId: number;
  name: string;
  category: string;
}

interface PropEntry {
  key: string;
  value: string;
}

interface PSet {
  name: string;
  props: PropEntry[];
}

interface SpatialNode {
  expressId: number;
  name: string;
  typeLabel: string;
  typeCss: string;          // CSS class suffix: project | site | building | storey | space | other
  children: SpatialNode[];
  elements: IFCElement[];
  totalCount: number;       // total elements in subtree (recursive)
}

// ── IFC category labels ───────────────────────────────────────────────────────

const CATEGORY_NAMES: Record<number, string> = {
  [IFCWALL]: "Walls",
  [IFCWALLSTANDARDCASE]: "Walls",
  [IFCDOOR]: "Doors",
  [IFCDOORSTANDARDCASE]: "Doors",
  [IFCWINDOW]: "Windows",
  [IFCWINDOWSTANDARDCASE]: "Windows",
  [IFCSLAB]: "Slabs / Floors",
  [IFCPLATE]: "Slabs / Floors",
  [IFCBEAM]: "Beams",
  [IFCCOLUMN]: "Columns",
  [IFCCOLUMNSTANDARDCASE]: "Columns",
  [IFCMEMBER]: "Members / Frames",
  [IFCROOF]: "Roofs",
  [IFCSTAIR]: "Stairs",
  [IFCSTAIRFLIGHT]: "Stairs",
  [IFCRAMP]: "Ramps",
  [IFCRAILING]: "Railings",
  [IFCCOVERING]: "Coverings",
  [IFCCURTAINWALL]: "Curtain Walls",
  [IFCFURNISHINGELEMENT]: "Furniture",
  [IFCSPACE]: "Spaces",
  [IFCBUILDINGSTOREY]: "Storeys",
  [IFCSITE]: "Sites",
  [IFCBUILDING]: "Buildings",
  [IFCPILE]: "Foundations",
  [IFCFOOTING]: "Foundations",
  [IFCBUILDINGELEMENTPROXY]: "Generic Elements",
  [IFCFLOWSEGMENT]: "MEP — Segments",
  [IFCFLOWFITTING]: "MEP — Fittings",
  [IFCFLOWTERMINAL]: "MEP — Terminals",
  [IFCFLOWCONTROLLER]: "MEP — Controllers",
  [IFCDUCTSEGMENT]: "MEP — Ducts",
  [IFCPIPESEGMENT]: "MEP — Pipes",
  [IFCPIPEFITTING]: "MEP — Pipe Fittings",
};

function typeCodeToCategory(code: number): string {
  return CATEGORY_NAMES[code] ?? "Other";
}

const SPATIAL_TYPE_META: Record<
  number,
  { label: string; css: string }
> = {
  [IFCPROJECT]: { label: "Project", css: "project" },
  [IFCSITE]: { label: "Site", css: "site" },
  [IFCBUILDING]: { label: "Building", css: "building" },
  [IFCBUILDINGSTOREY]: { label: "Storey", css: "storey" },
  [IFCSPACE]: { label: "Space", css: "space" },
};

// ── DOM refs ──────────────────────────────────────────────────────────────────

const canvas = document.getElementById("viewer-canvas") as HTMLCanvasElement;
const sourceName = document.getElementById("source-name") as HTMLElement;
const sourceStatus = document.getElementById("source-status") as HTMLElement;
const sourceKind = document.getElementById("source-kind") as HTMLElement;
const viewportStatus = document.getElementById("viewport-status") as HTMLElement;
const elementTreeEl = document.getElementById("element-tree") as HTMLElement;
const elementPropsEl = document.getElementById("element-props") as HTMLElement;
const treeModeBar = document.getElementById("tree-mode-bar") as HTMLElement;
const btnModeCat = document.getElementById("btn-mode-cat") as HTMLButtonElement;
const btnModeSpatial = document.getElementById("btn-mode-spatial") as HTMLButtonElement;

// ── Viewer state ──────────────────────────────────────────────────────────────

let _initError: string | null = null;
let ifcApi: IfcAPI | null = null;
let currentModelId: number | null = null;
let modelGroup: THREE.Group | null = null;
let renderer: THREE.WebGLRenderer | null = null;
let scene: THREE.Scene | null = null;
let camera: THREE.PerspectiveCamera | null = null;
let controls: OrbitControls | null = null;

// Element tree state (Phase A)
let elementsByCategory: Map<string, IFCElement[]> | null = null;
const propSetIndex = new Map<number, number[]>();
let selectedExpressId: number | null = null;
const savedMaterials = new Map<THREE.Mesh, THREE.Material | THREE.Material[]>();

// Spatial tree state (Phase B)
let spatialRoot: SpatialNode | null = null;
let viewMode: ViewMode = "category";

// Ray-casting (Phase B)
const raycaster = new THREE.Raycaster();
let _mouseDownPos: { x: number; y: number } | null = null;

// ── Status helpers ────────────────────────────────────────────────────────────

function setStatus(message: string): void {
  if (sourceStatus) sourceStatus.textContent = message;
  if (viewportStatus) viewportStatus.textContent = message;
}

function sourceBaseName(source?: string): string {
  if (!source) return "No IFC selected";
  return String(source).split(/[\\/]/).pop() || source;
}

function escHtml(str: string): string {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// ── window.GeoIfcViewer ───────────────────────────────────────────────────────

window.GeoIfcViewer = {
  async openReference(payload: ViewerPayload) {
    if (_initError) {
      setStatus(`3D renderer unavailable: ${_initError}`);
      return;
    }
    sourceName.textContent = sourceBaseName(payload.source);
    sourceKind.textContent = payload.kind || "-";
    try {
      await loadIfc(payload);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setStatus(`IFC viewer error: ${message}`);
      console.error(error);
    }
  },
};

// ── Three.js core ─────────────────────────────────────────────────────────────

function resize(): void {
  if (!renderer || !camera) return;
  const rect = canvas.getBoundingClientRect();
  const width = Math.max(1, Math.floor(rect.width));
  const height = Math.max(1, Math.floor(rect.height));
  renderer.setSize(width, height, false);
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
}

function animate(): void {
  if (!renderer || !scene || !camera || !controls) return;
  resize();
  controls.update();
  renderer.render(scene, camera);
  window.requestAnimationFrame(animate);
}

function fitCameraToBox(box: THREE.Box3): void {
  if (!camera || !controls || box.isEmpty()) return;
  const center = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3());
  const maxSize = Math.max(size.x, size.y, size.z);
  const distance = Math.max(maxSize * 1.8, 1);
  controls.target.copy(center);
  camera.position.set(
    center.x + distance,
    center.y + distance * 0.7,
    center.z + distance,
  );
  camera.near = Math.max(distance / 1000, 0.05);
  camera.far = distance * 100;
  camera.updateProjectionMatrix();
  controls.update();
}

function fitCameraToModel(group: THREE.Group): void {
  fitCameraToBox(new THREE.Box3().setFromObject(group));
}

// ── Element highlight ─────────────────────────────────────────────────────────

const HIGHLIGHT_MAT = new THREE.MeshStandardMaterial({
  color: 0xff7700,
  emissive: 0xff3300,
  emissiveIntensity: 0.35,
  roughness: 0.4,
  metalness: 0.05,
  side: THREE.DoubleSide,
});

function clearHighlight(): void {
  for (const [mesh, mat] of savedMaterials) {
    mesh.material = mat;
  }
  savedMaterials.clear();
}

function highlightElement(expressId: number): void {
  clearHighlight();
  modelGroup?.traverse((obj) => {
    const mesh = obj as THREE.Mesh;
    if (mesh.isMesh && mesh.userData.expressID === expressId) {
      savedMaterials.set(mesh, mesh.material);
      mesh.material = HIGHLIGHT_MAT;
    }
  });
}

function zoomToElement(expressId: number): void {
  const box = new THREE.Box3();
  modelGroup?.traverse((obj) => {
    const mesh = obj as THREE.Mesh;
    if (mesh.isMesh && mesh.userData.expressID === expressId) {
      box.expandByObject(mesh);
    }
  });
  fitCameraToBox(box);
}

// ── Ray-casting (Phase B) ────────────────────────────────────────────────────

canvas.addEventListener("mousedown", (e) => {
  _mouseDownPos = { x: e.clientX, y: e.clientY };
});

canvas.addEventListener("click", (e) => {
  if (!_mouseDownPos || !camera || !modelGroup) return;
  const dx = e.clientX - _mouseDownPos.x;
  const dy = e.clientY - _mouseDownPos.y;
  _mouseDownPos = null;
  // Ignore drags (orbit/pan); only act on genuine clicks
  if (Math.sqrt(dx * dx + dy * dy) > 4) return;

  const rect = canvas.getBoundingClientRect();
  raycaster.setFromCamera(
    new THREE.Vector2(
      ((e.clientX - rect.left) / rect.width) * 2 - 1,
      -((e.clientY - rect.top) / rect.height) * 2 + 1,
    ),
    camera,
  );

  const meshes: THREE.Object3D[] = [];
  modelGroup.traverse((obj) => {
    if ((obj as THREE.Mesh).isMesh) meshes.push(obj);
  });

  const hits = raycaster.intersectObjects(meshes, false);
  if (hits.length > 0) {
    const expressId = (hits[0].object as THREE.Mesh).userData.expressID;
    if (typeof expressId === "number") selectElement(expressId);
  }
});

// ── IFC attribute helpers ─────────────────────────────────────────────────────

function extractAttrValue(val: unknown): string | null {
  if (val === null || val === undefined) return null;
  if (typeof val === "string") return val || null;
  if (typeof val === "number") return String(val);
  if (typeof val === "boolean") return String(val);
  if (Array.isArray(val)) return null;
  if (typeof val === "object") {
    const obj = val as Record<string, unknown>;
    if (obj["type"] === 5) return null; // REF — skip relation handles
    if ("value" in obj) {
      const v = obj["value"];
      if (v === null || v === undefined || v === "") return null;
      if (typeof v === "object") return null;
      return String(v);
    }
  }
  return null;
}

function extractName(line: Record<string, unknown>): string {
  return extractAttrValue(line["Name"]) ?? "";
}

function resolveRef(val: unknown): number | null {
  if (typeof val === "number") return val;
  if (val && typeof val === "object") {
    const obj = val as Record<string, unknown>;
    if (typeof obj["value"] === "number") return obj["value"] as number;
    if (typeof obj["expressID"] === "number") return obj["expressID"] as number;
  }
  return null;
}

function resolveRefArray(val: unknown): number[] {
  if (!val) return [];
  if (Array.isArray(val)) {
    return val.map(resolveRef).filter((id): id is number => id !== null);
  }
  const single = resolveRef(val);
  return single !== null ? [single] : [];
}

// ── Property reading ──────────────────────────────────────────────────────────

const SKIP_ATTRS = new Set([
  "expressID", "type",
  "OwnerHistory", "ObjectPlacement", "Representation",
  "HasAssignments", "IsDecomposedBy", "Decomposes",
  "HasAssociations", "IsDefinedBy", "ReferencedBy",
  "ContainedInStructure", "HasOpenings", "ConnectedTo",
]);

function readDirectAttrs(api: IfcAPI, modelId: number, expressId: number): PropEntry[] {
  try {
    const line = api.GetLine(modelId, expressId, false) as Record<string, unknown>;
    const props: PropEntry[] = [];
    for (const [key, val] of Object.entries(line)) {
      if (SKIP_ATTRS.has(key)) continue;
      const strVal = extractAttrValue(val);
      if (strVal !== null) props.push({ key, value: strVal });
    }
    return props;
  } catch {
    return [];
  }
}

function readPropertySets(api: IfcAPI, modelId: number, expressId: number): PSet[] {
  const psets: PSet[] = [];
  const psetIds = propSetIndex.get(expressId) ?? [];

  for (const psId of psetIds) {
    try {
      const ps = api.GetLine(modelId, psId, false) as Record<string, unknown>;
      const psetName = extractName(ps) || "PropertySet";
      const props: PropEntry[] = [];

      const propRefs = resolveRefArray(ps["HasProperties"] ?? ps["Quantities"]);
      for (const propId of propRefs) {
        try {
          const prop = api.GetLine(modelId, propId, false) as Record<string, unknown>;
          const propName = extractName(prop) || `#${propId}`;

          let propVal: string | null = null;
          const nomVal = prop["NominalValue"];
          if (nomVal && typeof nomVal === "object") {
            propVal = extractAttrValue((nomVal as Record<string, unknown>)["value"]);
          }
          if (propVal === null) {
            for (const qKey of [
              "LengthValue", "AreaValue", "VolumeValue",
              "CountValue", "WeightValue", "TimeValue",
            ]) {
              const qv = extractAttrValue(prop[qKey]);
              if (qv !== null) { propVal = qv; break; }
            }
          }
          if (propVal !== null) props.push({ key: propName, value: propVal });
        } catch {
          /* skip unreadable property */
        }
      }

      if (props.length > 0) psets.push({ name: psetName, props });
    } catch {
      /* skip unreadable property set */
    }
  }
  return psets;
}

// ── Model state management ────────────────────────────────────────────────────

function clearModel(): void {
  if (!scene) return;

  clearHighlight();
  selectedExpressId = null;
  elementsByCategory = null;
  spatialRoot = null;
  propSetIndex.clear();

  if (modelGroup) {
    scene.remove(modelGroup);
    modelGroup.traverse((object) => {
      const mesh = object as THREE.Mesh;
      mesh.geometry?.dispose();
      (mesh.material as THREE.Material | undefined)?.dispose();
    });
  }
  modelGroup = new THREE.Group();
  scene.add(modelGroup);

  if (currentModelId !== null && ifcApi) {
    ifcApi.CloseModel(currentModelId);
    currentModelId = null;
  }

  clearTreeUI();
}

function clearTreeUI(): void {
  treeModeBar.hidden = true;
  elementTreeEl.innerHTML =
    '<p class="panel-hint">Load an IFC model to browse elements.</p>';
  elementPropsEl.hidden = true;
  elementPropsEl.innerHTML = "";
}

// ── Property set index ────────────────────────────────────────────────────────

function buildPropSetIndex(api: IfcAPI, modelId: number): void {
  propSetIndex.clear();
  try {
    const relIds = api.GetLineIDsWithType(modelId, IFCRELDEFINESBYPROPERTIES);
    for (let i = 0; i < relIds.size(); i++) {
      try {
        const rel = api.GetLine(modelId, relIds.get(i), false) as Record<string, unknown>;
        const psId = resolveRef(rel["RelatingPropertyDefinition"]);
        if (psId === null) continue;
        for (const objId of resolveRefArray(rel["RelatedObjects"])) {
          if (!propSetIndex.has(objId)) propSetIndex.set(objId, []);
          propSetIndex.get(objId)!.push(psId);
        }
      } catch { /* skip individual relation errors */ }
    }
  } catch { /* IFCRELDEFINESBYPROPERTIES not present */ }
}

// ── Element index (Phase A) ───────────────────────────────────────────────────

function buildElementIndex(api: IfcAPI, modelId: number): void {
  const seenIds = new Set<number>();
  modelGroup?.traverse((obj) => {
    const mesh = obj as THREE.Mesh;
    if (mesh.isMesh && typeof mesh.userData.expressID === "number") {
      seenIds.add(mesh.userData.expressID);
    }
  });

  const elements: IFCElement[] = [];
  for (const expressId of seenIds) {
    try {
      const line = api.GetLine(modelId, expressId, false) as Record<string, unknown>;
      elements.push({
        expressId,
        name: extractName(line) || `Element #${expressId}`,
        category: typeCodeToCategory(line["type"] as number),
      });
    } catch { /* skip unreadable element */ }
  }

  const grouped = new Map<string, IFCElement[]>();
  for (const el of elements) {
    if (!grouped.has(el.category)) grouped.set(el.category, []);
    grouped.get(el.category)!.push(el);
  }
  for (const arr of grouped.values()) arr.sort((a, b) => a.name.localeCompare(b.name));
  elementsByCategory = new Map(
    [...grouped.entries()].sort(([a], [b]) => a.localeCompare(b)),
  );
}

// ── Spatial tree (Phase B) ────────────────────────────────────────────────────

function buildSpatialTree(api: IfcAPI, modelId: number): void {
  // Fast lookup from expressID → element data (built by buildElementIndex)
  const elementById = new Map<number, IFCElement>();
  if (elementsByCategory) {
    for (const els of elementsByCategory.values()) {
      for (const el of els) elementById.set(el.expressId, el);
    }
  }

  // 1. Decomposition map: parentId → childIds (IFCRELAGGREGATES)
  const decomposedBy = new Map<number, number[]>();
  try {
    const relIds = api.GetLineIDsWithType(modelId, IFCRELAGGREGATES);
    for (let i = 0; i < relIds.size(); i++) {
      try {
        const rel = api.GetLine(modelId, relIds.get(i), false) as Record<string, unknown>;
        const parentId = resolveRef(rel["RelatingObject"]);
        if (parentId === null) continue;
        const childIds = resolveRefArray(rel["RelatedObjects"]);
        const existing = decomposedBy.get(parentId) ?? [];
        decomposedBy.set(parentId, existing.concat(childIds));
      } catch { /* skip */ }
    }
  } catch { /* IFCRELAGGREGATES not available */ }

  // 2. Containment map: structureId → element expressIds (IFCRELCONTAINEDINSPATIALSTRUCTURE)
  const containedIn = new Map<number, number[]>();
  try {
    const relIds = api.GetLineIDsWithType(modelId, IFCRELCONTAINEDINSPATIALSTRUCTURE);
    for (let i = 0; i < relIds.size(); i++) {
      try {
        const rel = api.GetLine(modelId, relIds.get(i), false) as Record<string, unknown>;
        const structId = resolveRef(rel["RelatingStructure"]);
        if (structId === null) continue;
        const elemIds = resolveRefArray(rel["RelatedElements"]);
        const existing = containedIn.get(structId) ?? [];
        containedIn.set(structId, existing.concat(elemIds));
      } catch { /* skip */ }
    }
  } catch { /* IFCRELCONTAINEDINSPATIALSTRUCTURE not available */ }

  // 3. Find IfcProject root
  try {
    const projectIds = api.GetLineIDsWithType(modelId, IFCPROJECT);
    if (projectIds.size() === 0) return;
    spatialRoot = buildSpatialNode(
      api, modelId, projectIds.get(0), decomposedBy, containedIn, elementById,
    );
  } catch { /* skip */ }
}

function buildSpatialNode(
  api: IfcAPI,
  modelId: number,
  expressId: number,
  decomposedBy: Map<number, number[]>,
  containedIn: Map<number, number[]>,
  elementById: Map<number, IFCElement>,
): SpatialNode {
  let name = `#${expressId}`;
  let typeCode = 0;
  try {
    const line = api.GetLine(modelId, expressId, false) as Record<string, unknown>;
    name = extractName(line) || name;
    typeCode = line["type"] as number;
  } catch { /* keep defaults */ }

  const meta = SPATIAL_TYPE_META[typeCode];
  const typeLabel = meta?.label ?? "Element";
  const typeCss = meta?.css ?? "other";

  // Recurse into decomposition children (spatial structure: Site → Building → Storey → Space)
  const children = (decomposedBy.get(expressId) ?? []).map((childId) =>
    buildSpatialNode(api, modelId, childId, decomposedBy, containedIn, elementById),
  );

  // Physical elements directly contained in this spatial node
  const elements = (containedIn.get(expressId) ?? [])
    .map((eid) => elementById.get(eid))
    .filter((e): e is IFCElement => e !== undefined)
    .sort((a, b) => a.name.localeCompare(b.name));

  const totalCount =
    elements.length +
    children.reduce((sum, c) => sum + c.totalCount, 0);

  return { expressId, name, typeLabel, typeCss, children, elements, totalCount };
}

// ── View mode management ──────────────────────────────────────────────────────

function switchViewMode(mode: ViewMode): void {
  viewMode = mode;
  btnModeCat.classList.toggle("active", mode === "category");
  btnModeSpatial.classList.toggle("active", mode === "spatial");
  btnModeSpatial.disabled = spatialRoot === null;
  renderActiveTree();
}

btnModeCat.addEventListener("click", () => switchViewMode("category"));
btnModeSpatial.addEventListener("click", () => switchViewMode("spatial"));

function renderActiveTree(): void {
  if (viewMode === "spatial" && spatialRoot !== null) {
    renderSpatialTree();
  } else {
    renderCategoryTree();
  }
}

// ── Category tree (Phase A) ───────────────────────────────────────────────────

function renderCategoryTree(): void {
  if (!elementsByCategory || elementsByCategory.size === 0) {
    elementTreeEl.innerHTML =
      '<p class="panel-hint">No elements with geometry found.</p>';
    return;
  }

  const frag = document.createDocumentFragment();

  for (const [category, elements] of elementsByCategory) {
    const details = document.createElement("details");
    details.className = "tree-cat";
    details.open = true;

    const summary = document.createElement("summary");
    summary.innerHTML =
      `<span class="cat-label">${escHtml(category)}</span>` +
      `<span class="cat-count">${elements.length}</span>`;
    details.appendChild(summary);

    const ul = document.createElement("ul");
    ul.className = "tree-list";
    for (const el of elements) {
      ul.appendChild(makeElementLi(el));
    }
    details.appendChild(ul);
    frag.appendChild(details);
  }

  elementTreeEl.innerHTML = "";
  elementTreeEl.appendChild(frag);
}

// ── Spatial tree (Phase B) rendering ─────────────────────────────────────────

function renderSpatialTree(): void {
  if (!spatialRoot) {
    elementTreeEl.innerHTML =
      '<p class="panel-hint">No spatial structure found in this model.</p>';
    return;
  }

  const frag = document.createDocumentFragment();
  appendSpatialNode(spatialRoot, frag);
  elementTreeEl.innerHTML = "";
  elementTreeEl.appendChild(frag);
}

function appendSpatialNode(
  node: SpatialNode,
  parent: DocumentFragment | HTMLElement,
): void {
  // Leaf nodes with no children and no elements are skipped (no geometry attached)
  if (node.children.length === 0 && node.elements.length === 0) return;

  const details = document.createElement("details");
  details.className = `tree-cat snode-${node.typeCss}`;
  details.open = node.typeCss !== "space"; // collapse spaces by default

  const summary = document.createElement("summary");
  summary.innerHTML =
    `<span class="snode-type">${escHtml(node.typeLabel)}</span>` +
    `<span class="cat-label">${escHtml(node.name)}</span>` +
    `<span class="cat-count">${node.totalCount}</span>`;
  details.appendChild(summary);

  // Direct elements at this node
  if (node.elements.length > 0) {
    const ul = document.createElement("ul");
    ul.className = "tree-list";
    for (const el of node.elements) ul.appendChild(makeElementLi(el));
    details.appendChild(ul);
  }

  // Child spatial nodes
  for (const child of node.children) {
    appendSpatialNode(child, details);
  }

  parent.appendChild(details);
}

// ── Shared element list item ──────────────────────────────────────────────────

function makeElementLi(el: IFCElement): HTMLLIElement {
  const li = document.createElement("li");
  const btn = document.createElement("button");
  btn.className = "tree-item";
  if (el.expressId === selectedExpressId) btn.classList.add("selected");
  btn.textContent = el.name;
  btn.title = `${el.name}  (#${el.expressId})`;
  btn.dataset.eid = String(el.expressId);
  btn.addEventListener("click", () => selectElement(el.expressId));
  li.appendChild(btn);
  return li;
}

// ── Element selection ─────────────────────────────────────────────────────────

function selectElement(expressId: number): void {
  if (selectedExpressId === expressId) {
    // Toggle deselection
    selectedExpressId = null;
    clearHighlight();
    elementPropsEl.hidden = true;
    elementPropsEl.innerHTML = "";
    document
      .querySelectorAll(".tree-item.selected")
      .forEach((el) => el.classList.remove("selected"));
    return;
  }

  selectedExpressId = expressId;

  // Update tree selection state
  document
    .querySelectorAll(".tree-item.selected")
    .forEach((el) => el.classList.remove("selected"));
  const btn = elementTreeEl.querySelector<HTMLElement>(`[data-eid="${expressId}"]`);
  btn?.classList.add("selected");
  btn?.scrollIntoView({ block: "nearest" });

  // Ensure the containing <details> are open so the button is visible
  let parent = btn?.parentElement;
  while (parent && parent !== elementTreeEl) {
    if (parent.tagName === "DETAILS") (parent as HTMLDetailsElement).open = true;
    parent = parent.parentElement;
  }

  // 3D viewport: zoom + highlight
  zoomToElement(expressId);
  highlightElement(expressId);

  // Properties panel
  if (ifcApi !== null && currentModelId !== null) {
    const direct = readDirectAttrs(ifcApi, currentModelId, expressId);
    const psets = readPropertySets(ifcApi, currentModelId, expressId);
    renderProps(expressId, direct, psets);
  }
}

// ── Props rendering ───────────────────────────────────────────────────────────

function propRow(pset: string, key: string, value: string): string {
  return (
    `<div class="prop-row">` +
    `<span class="prop-key">${escHtml(key)}</span>` +
    `<span class="prop-val">${escHtml(value)}</span>` +
    `<button class="prop-transfer" ` +
    `data-pset="${escHtml(pset)}" data-key="${escHtml(key)}" data-val="${escHtml(value)}" ` +
    `title="Transfer to GIS field">→</button>` +
    `</div>`
  );
}

function transferProp(pset: string, key: string, value: string, btn: HTMLButtonElement): void {
  btn.disabled = true;
  fetch(`${window.location.origin}/transfer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pset, key, value }),
  })
    .then((r) => {
      if (r.ok) {
        btn.textContent = "✓";
        btn.classList.add("prop-sent");
        btn.style.opacity = "1";
      } else {
        btn.classList.add("prop-error");
        btn.disabled = false;
      }
    })
    .catch(() => {
      btn.classList.add("prop-error");
      btn.disabled = false;
    });
}

function renderProps(expressId: number, direct: PropEntry[], psets: PSet[]): void {
  const el = elementsByCategory
    ? [...elementsByCategory.values()].flat().find((e) => e.expressId === expressId)
    : null;

  const name = el?.name ?? `Element #${expressId}`;
  const category = el?.category ?? "Unknown";

  const parts: string[] = [];
  parts.push(
    `<div class="props-header">`,
    `  <span class="props-title">${escHtml(name)}</span>`,
    `  <span class="props-meta">${escHtml(category)} · #${expressId}</span>`,
    `</div>`,
    `<div class="props-body">`,
  );

  if (direct.length > 0) {
    parts.push(`<div class="pset-block"><div class="pset-name">Attributes</div>`);
    for (const { key, value } of direct) {
      parts.push(propRow("", key, value));
    }
    parts.push(`</div>`);
  }

  for (const pset of psets) {
    parts.push(
      `<div class="pset-block"><div class="pset-name">${escHtml(pset.name)}</div>`,
    );
    for (const { key, value } of pset.props) {
      parts.push(propRow(pset.name, key, value));
    }
    parts.push(`</div>`);
  }

  if (direct.length === 0 && psets.length === 0) {
    parts.push(`<p class="panel-hint">No readable properties found.</p>`);
  }

  parts.push(`</div>`);

  elementPropsEl.innerHTML = parts.join("\n");

  elementPropsEl.querySelectorAll<HTMLButtonElement>(".prop-transfer").forEach((btn) => {
    btn.addEventListener("click", () => {
      transferProp(btn.dataset.pset ?? "", btn.dataset.key ?? "", btn.dataset.val ?? "", btn);
    });
  });

  elementPropsEl.hidden = false;
}

// ── IFC model loading ─────────────────────────────────────────────────────────

function decodeBase64(dataBase64: string): Uint8Array {
  const binary = window.atob(dataBase64);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes;
}

function buildGeometry(
  api: IfcAPI,
  modelId: number,
  placedGeometry: PlacedGeometry,
): THREE.BufferGeometry {
  const geometry = api.GetGeometry(modelId, placedGeometry.geometryExpressID);
  const vertexData = api.GetVertexArray(
    geometry.GetVertexData(),
    geometry.GetVertexDataSize(),
  );
  const indexData = api.GetIndexArray(
    geometry.GetIndexData(),
    geometry.GetIndexDataSize(),
  );

  const positions: number[] = [];
  const normals: number[] = [];
  for (let index = 0; index < vertexData.length; index += 6) {
    positions.push(
      vertexData[index], vertexData[index + 1], vertexData[index + 2],
    );
    normals.push(
      vertexData[index + 3], vertexData[index + 4], vertexData[index + 5],
    );
  }

  const bufferGeometry = new THREE.BufferGeometry();
  bufferGeometry.setAttribute(
    "position",
    new THREE.Float32BufferAttribute(positions, 3),
  );
  bufferGeometry.setAttribute(
    "normal",
    new THREE.Float32BufferAttribute(normals, 3),
  );
  bufferGeometry.setIndex(Array.from(indexData));
  bufferGeometry.applyMatrix4(
    new THREE.Matrix4().fromArray(placedGeometry.flatTransformation),
  );
  geometry.delete?.();
  return bufferGeometry;
}

function addFlatMesh(api: IfcAPI, modelId: number, flatMesh: FlatMesh): void {
  if (!modelGroup) return;
  const geometries = flatMesh.geometries;
  for (let index = 0; index < geometries.size(); index += 1) {
    const placedGeometry = geometries.get(index);
    const color = placedGeometry.color;
    const material = new THREE.MeshStandardMaterial({
      color: new THREE.Color(color.x, color.y, color.z),
      opacity: Math.max(0.15, color.w || 1),
      transparent: color.w < 1,
      roughness: 0.75,
      metalness: 0.05,
      side: THREE.DoubleSide,
    });
    const mesh = new THREE.Mesh(
      buildGeometry(api, modelId, placedGeometry),
      material,
    );
    mesh.userData.expressID = flatMesh.expressID;
    modelGroup.add(mesh);
  }
}

async function getIfcApi(): Promise<IfcAPI> {
  if (ifcApi) return ifcApi;
  const api = new IfcAPI();
  api.SetWasmPath("./assets/");
  await api.Init(undefined, true);
  ifcApi = api;
  return api;
}

async function loadIfc(payload: ViewerPayload): Promise<void> {
  clearModel();

  let data: Uint8Array;

  if (payload.modelUrl) {
    setStatus("Fetching IFC from server...");
    const response = await fetch(payload.modelUrl);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    data = new Uint8Array(await response.arrayBuffer());
  } else if (payload.dataBase64) {
    data = decodeBase64(payload.dataBase64);
  } else {
    setStatus("IFC source received. No IFC data available.");
    return;
  }

  setStatus("Loading IFC geometry...");
  const api = await getIfcApi();
  const modelId = api.OpenModel(data, {
    COORDINATE_TO_ORIGIN: true,
    CIRCLE_SEGMENTS: 16,
  });
  if (modelId < 0) throw new Error("web-ifc could not open the model.");
  currentModelId = modelId;

  let meshCount = 0;
  api.StreamAllMeshes(modelId, (flatMesh) => {
    addFlatMesh(api, modelId, flatMesh);
    flatMesh.delete?.();
    meshCount += 1;
    if (meshCount % 25 === 0) {
      setStatus(`Loading IFC geometry... ${meshCount} elements`);
    }
  });

  if (modelGroup) fitCameraToModel(modelGroup);
  setStatus(`IFC loaded: ${meshCount} elements. Indexing...`);

  // Build Phase A indexes
  buildPropSetIndex(api, modelId);
  buildElementIndex(api, modelId);

  // Build Phase B spatial tree
  buildSpatialTree(api, modelId);

  // Show mode bar; activate category view by default; spatial if structure found
  treeModeBar.hidden = false;
  btnModeSpatial.disabled = spatialRoot === null;
  viewMode = spatialRoot !== null ? "spatial" : "category";
  btnModeCat.classList.toggle("active", viewMode === "category");
  btnModeSpatial.classList.toggle("active", viewMode === "spatial");
  renderActiveTree();

  const hasSpatial = spatialRoot !== null ? " · spatial structure available" : "";
  setStatus(`IFC ready: ${meshCount} elements${hasSpatial}`);
}

// ── WebGL initialisation ──────────────────────────────────────────────────────

try {
  try {
    renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  } catch {
    try {
      renderer = new THREE.WebGLRenderer({
        canvas,
        antialias: false,
        powerPreference: "low-power",
      });
    } catch {
      const softCtx =
        (canvas.getContext("webgl2", {
          failIfMajorPerformanceCaveat: false,
        }) as WebGL2RenderingContext | null) ||
        (canvas.getContext("webgl", {
          failIfMajorPerformanceCaveat: false,
        }) as WebGLRenderingContext | null);
      if (!softCtx) {
        throw new Error(
          "WebGL unavailable (hardware and software rendering both failed)",
        );
      }
      renderer = new THREE.WebGLRenderer({ canvas, context: softCtx, antialias: false });
    }
  }

  renderer.setClearColor(0xeef2f6);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));

  scene = new THREE.Scene();
  scene.add(new THREE.HemisphereLight(0xffffff, 0x6b7280, 2.4));

  camera = new THREE.PerspectiveCamera(55, 1, 0.1, 1000000);
  camera.position.set(8, 6, 8);

  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;

  scene.add(new THREE.GridHelper(20, 20, 0xcfd7df, 0xdfe6ed));

  modelGroup = new THREE.Group();
  scene.add(modelGroup);

  window.addEventListener("resize", resize);
  resize();
  animate();
  console.log("GeoIFC Assets: 3D viewer ready");
} catch (e) {
  _initError = e instanceof Error ? e.message : String(e);
  setStatus(`3D renderer unavailable: ${_initError}`);
  console.error("GeoIFC Assets: renderer init failed:", e);
}

// ── Poll /current.json ────────────────────────────────────────────────────────

let _pollVersion = -1;

async function pollCurrentIfc(): Promise<void> {
  try {
    const res = await fetch("/current.json");
    if (!res.ok) return;
    const data = (await res.json()) as { version: number; ifc_url: string | null };
    if (data.version !== _pollVersion) {
      _pollVersion = data.version;
      if (data.ifc_url) {
        console.log(
          "GeoIFC Assets: new IFC detected (version",
          data.version,
          "):",
          data.ifc_url,
        );
        setStatus("IFC source updated — loading...");
        await window.GeoIfcViewer.openReference({
          modelUrl: data.ifc_url,
          source: data.ifc_url,
          kind: "ifc_url",
        });
      } else {
        setStatus("Select a feature in QGIS to load an IFC.");
        clearModel();
      }
    }
  } catch {
    // Server not ready yet or subprocess restarting — ignore silently.
  }
}

setTimeout(() => {
  void pollCurrentIfc();
  setInterval(() => void pollCurrentIfc(), 1500);
}, 800);
