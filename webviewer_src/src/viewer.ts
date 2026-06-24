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
const btnCollapseTree = document.getElementById("btn-collapse-tree") as HTMLButtonElement;
const btnExport = document.getElementById("btn-export") as HTMLButtonElement;
const exportMenu = document.getElementById("export-menu") as HTMLElement;
const storeyBarEl = document.getElementById("storey-bar") as HTMLElement;
const btn2DView = document.getElementById("btn-view-2d") as HTMLButtonElement;
const treeSearchBarEl = document.getElementById("tree-search-bar") as HTMLElement;
const treeSearchInputEl = document.getElementById("tree-search-input") as HTMLInputElement;
const treeSearchClearEl = document.getElementById("tree-search-clear") as HTMLButtonElement;
const propsSearchBarEl = document.getElementById("props-search-bar") as HTMLElement;
const propsSearchInputEl = document.getElementById("props-search-input") as HTMLInputElement;
const propsSearchClearEl = document.getElementById("props-search-clear") as HTMLButtonElement;

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

// Last rendered element props (for export)
let _lastProps: { expressId: number; name: string; category: string; direct: PropEntry[]; psets: PSet[] } | null = null;
const savedMaterials = new Map<THREE.Mesh, THREE.Material | THREE.Material[]>();

// Spatial tree state (Phase B)
let spatialRoot: SpatialNode | null = null;
let viewMode: ViewMode = "category";

// Storey filter state (Phase D)
let storeys: SpatialNode[] = [];
const elementToStorey = new Map<number, number>(); // element expressId → storey expressId
let activeStoreyId: number | null = null;

// 2D top-down view state (Phase D)
let is2DView = false;
let saved3DCamera: { pos: THREE.Vector3; target: THREE.Vector3 } | null = null;

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
  if (typeof val === "number") {
    if (Number.isInteger(val)) return String(val);
    return parseFloat(val.toFixed(2)).toString();
  }
  if (typeof val === "boolean") return String(val);
  if (Array.isArray(val)) return null;
  if (typeof val === "object") {
    const obj = val as Record<string, unknown>;
    if (obj["type"] === 5) return null; // REF — skip relation handles
    if ("value" in obj) {
      const v = obj["value"];
      if (v === null || v === undefined || v === "") return null;
      if (typeof v === "object") return null;
      if (typeof v === "number") {
        if (Number.isInteger(v)) return String(v);
        return parseFloat(v.toFixed(2)).toString();
      }
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
              "CountValue", "WeightValue", "TimeValue", "NumberValue",
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

// ── 2D top-down view (Phase D) ────────────────────────────────────────────────

function getVisibleBoundingBox(): THREE.Box3 {
  const box = new THREE.Box3();
  modelGroup?.traverse((obj) => {
    const mesh = obj as THREE.Mesh;
    if (mesh.isMesh && mesh.visible) box.expandByObject(mesh);
  });
  if (box.isEmpty() && modelGroup) box.setFromObject(modelGroup);
  return box;
}

function fitCamera2DToBox(box: THREE.Box3): void {
  if (!camera || !controls || box.isEmpty()) return;
  const center = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3());
  const maxExtent = Math.max(size.x, size.z, 1);
  const elevHeight = size.y;
  const distance = maxExtent * 2;
  controls.target.set(center.x, center.y, center.z);
  camera.position.set(center.x, center.y + distance + elevHeight * 0.5 + 1, center.z);
  const pCam = camera as THREE.PerspectiveCamera;
  pCam.near = Math.max(0.05, distance / 100);
  pCam.far = (distance + elevHeight) * 4;
  pCam.updateProjectionMatrix();
  controls.update();
}

function switchTo2DView(): void {
  if (!camera || !controls || !modelGroup) return;
  is2DView = true;
  saved3DCamera = { pos: camera.position.clone(), target: controls.target.clone() };
  // Change up vector to avoid gimbal singularity when looking straight down Y axis
  camera.up.set(0, 0, -1);
  fitCamera2DToBox(getVisibleBoundingBox());
  controls.enableRotate = false;
  controls.screenSpacePanning = true;
  controls.update();
  btn2DView.classList.add("active-2d");
  btn2DView.textContent = "3D";
  btn2DView.title = "Switch to 3D view";
}

function switchTo3DView(): void {
  if (!camera || !controls) return;
  is2DView = false;
  camera.up.set(0, 1, 0);
  if (saved3DCamera) {
    camera.position.copy(saved3DCamera.pos);
    controls.target.copy(saved3DCamera.target);
    saved3DCamera = null;
  }
  controls.enableRotate = true;
  controls.screenSpacePanning = false;
  controls.update();
  btn2DView.classList.remove("active-2d");
  btn2DView.textContent = "2D";
  btn2DView.title = "Switch to 2D top-down view";
}

btn2DView.addEventListener("click", () => {
  if (is2DView) switchTo3DView();
  else switchTo2DView();
});

// ── Storey filter (Phase D) ───────────────────────────────────────────────────

function collectStoreyElements(node: SpatialNode, storeyId: number): void {
  for (const el of node.elements) {
    elementToStorey.set(el.expressId, storeyId);
  }
  for (const child of node.children) {
    collectStoreyElements(child, storeyId);
  }
}

function collectStoreys(node: SpatialNode): void {
  if (node.typeCss === "storey") {
    storeys.push(node);
    collectStoreyElements(node, node.expressId);
  } else {
    for (const child of node.children) {
      collectStoreys(child);
    }
  }
}

function buildStoreyIndex(root: SpatialNode): void {
  storeys = [];
  elementToStorey.clear();
  collectStoreys(root);
}

function updateStoreyBarUI(): void {
  storeyBarEl.querySelectorAll<HTMLButtonElement>(".storey-btn").forEach((btn) => {
    const eid = btn.dataset.eid !== undefined ? Number(btn.dataset.eid) : null;
    btn.classList.toggle("active", eid === activeStoreyId);
  });
}

function notifyStoreySelected(storeyId: number | null, storeyName: string | null): void {
  fetch(`${window.location.origin}/transfer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ type: "storey_selected", storey_id: storeyId, storey_name: storeyName }),
  }).catch(() => {
    // Non-critical: viewer remains fully functional if server is unavailable
  });
}

function filterByStorey(storeyId: number | null): void {
  const storeyNode = storeyId !== null ? storeys.find((s) => s.expressId === storeyId) : null;
  activeStoreyId = storeyId;
  modelGroup?.traverse((obj) => {
    const mesh = obj as THREE.Mesh;
    if (!mesh.isMesh) return;
    const expressId = mesh.userData.expressID as number | undefined;
    if (expressId === undefined) return;
    mesh.visible = storeyId === null || elementToStorey.get(expressId) === storeyId;
  });

  const box = getVisibleBoundingBox();
  if (is2DView) {
    fitCamera2DToBox(box);
  } else {
    fitCameraToBox(box);
  }
  updateStoreyBarUI();
  renderActiveTree();
  notifyStoreySelected(storeyId, storeyNode?.name ?? null);
}

function renderStoreyBar(): void {
  storeyBarEl.innerHTML = "";
  if (storeys.length === 0) {
    storeyBarEl.hidden = true;
    return;
  }

  const allBtn = document.createElement("button");
  allBtn.className = "storey-btn" + (activeStoreyId === null ? " active" : "");
  allBtn.textContent = "All";
  allBtn.title = "Show all storeys";
  allBtn.addEventListener("click", () => filterByStorey(null));
  storeyBarEl.appendChild(allBtn);

  for (const storey of storeys) {
    const btn = document.createElement("button");
    btn.className = "storey-btn" + (activeStoreyId === storey.expressId ? " active" : "");
    const label = storey.name || `Storey #${storey.expressId}`;
    btn.textContent = label;
    btn.title = label;
    btn.dataset.eid = String(storey.expressId);
    btn.addEventListener("click", () => filterByStorey(storey.expressId));
    storeyBarEl.appendChild(btn);
  }

  storeyBarEl.hidden = false;
}

// ── Model state management ────────────────────────────────────────────────────

function clearModel(): void {
  if (!scene) return;

  reset2DState();
  resetStoreyState();
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
  storeyBarEl.hidden = true;
  btn2DView.hidden = true;
  treeSearchBarEl.hidden = true;
  treeSearchInputEl.value = "";
  treeSearchClearEl.hidden = true;
  propsSearchBarEl.hidden = true;
  propsSearchInputEl.value = "";
  propsSearchClearEl.hidden = true;
  elementTreeEl.innerHTML =
    '<p class="panel-hint">Load an IFC model to browse elements.</p>';
  elementPropsEl.hidden = true;
  elementPropsEl.innerHTML = "";
  _lastProps = null;
}

function reset2DState(): void {
  if (is2DView) {
    is2DView = false;
    if (camera) camera.up.set(0, 1, 0);
    if (controls) {
      controls.enableRotate = true;
      controls.screenSpacePanning = false;
    }
    btn2DView.classList.remove("active-2d");
    btn2DView.textContent = "2D";
    btn2DView.title = "Switch to 2D top-down view";
    saved3DCamera = null;
  }
}

function resetStoreyState(): void {
  storeys = [];
  elementToStorey.clear();
  activeStoreyId = null;
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
  treeSearchInputEl.value = "";
  treeSearchClearEl.hidden = true;
  renderActiveTree();
}

btnModeCat.addEventListener("click", () => switchViewMode("category"));
btnModeSpatial.addEventListener("click", () => switchViewMode("spatial"));
btnCollapseTree.addEventListener("click", () => {
  elementTreeEl.querySelectorAll<HTMLDetailsElement>("details").forEach((d) => { d.open = false; });
});

function renderActiveTree(): void {
  if (viewMode === "spatial" && spatialRoot !== null) {
    renderSpatialTree();
  } else {
    renderCategoryTree();
  }
  const q = treeSearchInputEl.value.trim();
  if (q) applyTreeFilter(q);
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
    const filtered = activeStoreyId === null
      ? elements
      : elements.filter((el) => elementToStorey.get(el.expressId) === activeStoreyId);
    if (filtered.length === 0) continue;

    const details = document.createElement("details");
    details.className = "tree-cat";
    details.open = false;

    const summary = document.createElement("summary");
    summary.innerHTML =
      `<span class="cat-label">${escHtml(category)}</span>` +
      `<span class="cat-count">${filtered.length}</span>`;
    details.appendChild(summary);

    const ul = document.createElement("ul");
    ul.className = "tree-list";
    for (const el of filtered) {
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

  if (activeStoreyId !== null) {
    const activeStorey = storeys.find((s) => s.expressId === activeStoreyId);
    if (activeStorey) {
      appendSpatialNode(activeStorey, frag);
    }
  } else {
    appendSpatialNode(spatialRoot, frag);
  }

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
  details.open = false;

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
  const label = el.name.trim() || `${el.category} #${el.expressId}`;
  btn.textContent = label;
  btn.title = `${label}  (#${el.expressId})`;
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
    propsSearchBarEl.hidden = true;
    propsSearchInputEl.value = "";
    propsSearchClearEl.hidden = true;
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
    `<div class="prop-col-resizer"></div>` +
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

// ── Search / filter ───────────────────────────────────────────────────────────

function applyTreeFilter(query: string): void {
  const q = query.toLowerCase().trim();
  if (!q) {
    elementTreeEl.querySelectorAll<HTMLElement>("li").forEach((li) => { li.hidden = false; });
    elementTreeEl.querySelectorAll<HTMLDetailsElement>(".tree-cat").forEach((d) => { d.hidden = false; });
    return;
  }
  elementTreeEl.querySelectorAll<HTMLButtonElement>(".tree-item").forEach((btn) => {
    (btn.parentElement as HTMLLIElement).hidden = !btn.textContent!.toLowerCase().includes(q);
  });
  const allDetails = Array.from(
    elementTreeEl.querySelectorAll<HTMLDetailsElement>(".tree-cat"),
  ).reverse();
  for (const details of allDetails) {
    const hasVisible = details.querySelectorAll<HTMLElement>("li:not([hidden])").length > 0;
    details.hidden = !hasVisible;
    if (hasVisible) details.open = true;
  }
}

function applyPropsFilter(query: string): void {
  const q = query.toLowerCase().trim();
  if (!q) {
    elementPropsEl.querySelectorAll<HTMLElement>(".prop-row").forEach((r) => { r.hidden = false; });
    elementPropsEl.querySelectorAll<HTMLElement>(".pset-block").forEach((b) => { b.hidden = false; });
    return;
  }
  elementPropsEl.querySelectorAll<HTMLElement>(".prop-row").forEach((row) => {
    const key = row.querySelector(".prop-key")?.textContent?.toLowerCase() ?? "";
    const val = row.querySelector(".prop-val")?.textContent?.toLowerCase() ?? "";
    row.hidden = !key.includes(q) && !val.includes(q);
  });
  elementPropsEl.querySelectorAll<HTMLElement>(".pset-block").forEach((block) => {
    const visibleRows = block.querySelectorAll<HTMLElement>(".prop-row:not([hidden])").length;
    block.hidden = visibleRows === 0;
    if (visibleRows > 0) block.classList.remove("collapsed");
  });
}

function psetGroupHtml(label: string, rows: string[]): string {
  const isCollapsed = localStorage.getItem(`geoifc.pset.${label}`) === "1";
  const collapsedClass = isCollapsed ? " collapsed" : "";
  return (
    `<div class="pset-block${collapsedClass}">` +
    `<div class="pset-name" data-label="${escHtml(label)}">` +
    `<span class="pset-chevron"></span>` +
    `${escHtml(label)}` +
    `</div>` +
    `<div class="pset-rows">` +
    rows.join("\n") +
    `</div>` +
    `</div>`
  );
}

function renderProps(expressId: number, direct: PropEntry[], psets: PSet[]): void {
  const el = elementsByCategory
    ? [...elementsByCategory.values()].flat().find((e) => e.expressId === expressId)
    : null;

  const rawName = el?.name ?? "";
  const category = el?.category ?? "Unknown";
  const name = rawName.trim() || `${category} #${expressId}`;
  _lastProps = { expressId, name, category, direct, psets };

  const parts: string[] = [];
  parts.push(
    `<div class="props-header">`,
    `  <span class="props-title">${escHtml(name)}</span>`,
    `  <span class="props-meta">${escHtml(category)} · #${expressId}</span>`,
    `</div>`,
    `<div class="props-body">`,
  );

  if (direct.length > 0) {
    const rows = direct.map(({ key, value }) => propRow("", key, value));
    parts.push(psetGroupHtml("Attributes", rows));
  }

  for (const pset of psets) {
    const rows = pset.props.map(({ key, value }) => propRow(pset.name, key, value));
    parts.push(psetGroupHtml(pset.name, rows));
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

  elementPropsEl.querySelectorAll<HTMLElement>(".pset-name").forEach((nameEl) => {
    const block = nameEl.closest<HTMLElement>(".pset-block")!;
    nameEl.addEventListener("click", () => {
      const label = nameEl.dataset.label ?? "";
      block.classList.toggle("collapsed");
      if (block.classList.contains("collapsed")) {
        localStorage.setItem(`geoifc.pset.${label}`, "1");
      } else {
        localStorage.removeItem(`geoifc.pset.${label}`);
      }
    });
  });

  propsSearchBarEl.hidden = false;
  propsSearchInputEl.value = "";
  propsSearchClearEl.hidden = true;
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

  // Build storey index and render filter bar (Phase D)
  if (spatialRoot !== null) {
    buildStoreyIndex(spatialRoot);
    renderStoreyBar();
  }

  // Show mode bar and search bar; activate category view by default; spatial if structure found
  treeModeBar.hidden = false;
  treeSearchBarEl.hidden = false;
  treeSearchInputEl.value = "";
  treeSearchClearEl.hidden = true;
  btnModeSpatial.disabled = spatialRoot === null;
  viewMode = spatialRoot !== null ? "spatial" : "category";
  btnModeCat.classList.toggle("active", viewMode === "category");
  btnModeSpatial.classList.toggle("active", viewMode === "spatial");
  renderActiveTree();

  // Show 2D toggle button when geometry is available (Phase D)
  btn2DView.hidden = meshCount === 0;

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
    const data = (await res.json()) as { version: number; ifc_url: string | null; ifc_name: string | null };
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
          source: data.ifc_name ?? data.ifc_url,
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

// ── Export ────────────────────────────────────────────────────────────────────

function _downloadBlob(content: string, filename: string, mime: string): void {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function _ifcBaseName(): string {
  const src = sourceName.textContent ?? "ifc";
  return src.replace(/\.[^.]+$/, "").replace(/[^a-zA-Z0-9_-]/g, "_") || "ifc";
}

function _spatialNodeToObj(node: SpatialNode): object {
  return {
    expressId: node.expressId,
    name: node.name,
    type: node.typeLabel,
    totalElements: node.totalCount,
    elements: node.elements.map((e) => ({ expressId: e.expressId, name: e.name, category: e.category })),
    children: node.children.map(_spatialNodeToObj),
  };
}

function exportSpatialJson(): void {
  if (!spatialRoot) return;
  _downloadBlob(
    JSON.stringify(_spatialNodeToObj(spatialRoot), null, 2),
    `${_ifcBaseName()}_spatial.json`,
    "application/json",
  );
}

function exportCategoriesJson(): void {
  if (!elementsByCategory) return;
  const obj: Record<string, object[]> = {};
  for (const [cat, els] of elementsByCategory) {
    obj[cat] = els.map((e) => ({ expressId: e.expressId, name: e.name }));
  }
  _downloadBlob(JSON.stringify(obj, null, 2), `${_ifcBaseName()}_categories.json`, "application/json");
}

function exportPropsJson(): void {
  if (!_lastProps) return;
  const { expressId, name, category, direct, psets } = _lastProps;
  const obj = {
    expressId,
    name,
    category,
    attributes: Object.fromEntries(direct.map((p) => [p.key, p.value])),
    propertySets: Object.fromEntries(psets.map((ps) => [ps.name, Object.fromEntries(ps.props.map((p) => [p.key, p.value]))])),
  };
  _downloadBlob(JSON.stringify(obj, null, 2), `${_ifcBaseName()}_element_${expressId}.json`, "application/json");
}

function exportPropsCsv(): void {
  if (!_lastProps) return;
  const { expressId, direct, psets } = _lastProps;
  const rows: string[][] = [["pset", "key", "value"]];
  for (const { key, value } of direct) rows.push(["Attributes", key, value]);
  for (const ps of psets) {
    for (const { key, value } of ps.props) rows.push([ps.name, key, value]);
  }
  const csv = rows.map((r) => r.map((c) => `"${c.replace(/"/g, '""')}"`).join(",")).join("\r\n");
  _downloadBlob(csv, `${_ifcBaseName()}_element_${expressId}.csv`, "text/csv");
}

function _openExportMenu(): void {
  const noSpatial = !spatialRoot;
  const noCat = !elementsByCategory || elementsByCategory.size === 0;
  const noProps = !_lastProps;
  (document.getElementById("export-spatial-json") as HTMLButtonElement).disabled = noSpatial;
  (document.getElementById("export-cat-json") as HTMLButtonElement).disabled = noCat;
  (document.getElementById("export-props-json") as HTMLButtonElement).disabled = noProps;
  (document.getElementById("export-props-csv") as HTMLButtonElement).disabled = noProps;

  const panel = document.querySelector<HTMLElement>(".viewer-panel")!;
  const panelRect = panel.getBoundingClientRect();
  const btnRect = btnExport.getBoundingClientRect();
  exportMenu.style.top = `${btnRect.bottom - panelRect.top + 4}px`;
  exportMenu.style.right = `${panelRect.right - btnRect.right}px`;
  exportMenu.hidden = false;
}

btnExport.addEventListener("click", (e) => {
  e.stopPropagation();
  if (!exportMenu.hidden) { exportMenu.hidden = true; return; }
  _openExportMenu();
});

document.addEventListener("click", () => { exportMenu.hidden = true; });
exportMenu.addEventListener("click", (e) => e.stopPropagation());

document.getElementById("export-spatial-json")!.addEventListener("click", () => { exportSpatialJson(); exportMenu.hidden = true; });
document.getElementById("export-cat-json")!.addEventListener("click", () => { exportCategoriesJson(); exportMenu.hidden = true; });
document.getElementById("export-props-json")!.addEventListener("click", () => { exportPropsJson(); exportMenu.hidden = true; });
document.getElementById("export-props-csv")!.addEventListener("click", () => { exportPropsCsv(); exportMenu.hidden = true; });

// ── Tree search ───────────────────────────────────────────────────────────────

treeSearchInputEl.addEventListener("input", () => {
  const q = treeSearchInputEl.value;
  treeSearchClearEl.hidden = !q;
  applyTreeFilter(q);
});

treeSearchClearEl.addEventListener("click", () => {
  treeSearchInputEl.value = "";
  treeSearchClearEl.hidden = true;
  applyTreeFilter("");
  treeSearchInputEl.focus();
});

// ── Props search ──────────────────────────────────────────────────────────────

propsSearchInputEl.addEventListener("input", () => {
  const q = propsSearchInputEl.value;
  propsSearchClearEl.hidden = !q;
  applyPropsFilter(q);
});

propsSearchClearEl.addEventListener("click", () => {
  propsSearchInputEl.value = "";
  propsSearchClearEl.hidden = true;
  applyPropsFilter("");
  propsSearchInputEl.focus();
});

// ── Props key-column resize ───────────────────────────────────────────────────

const PROPS_KEY_STORAGE = "geoifc-prop-key-width";
const PROPS_KEY_MIN = 60;
const PROPS_KEY_MAX = 300;
const PROPS_KEY_DEFAULT = 110;

{
  const saved = parseInt(localStorage.getItem(PROPS_KEY_STORAGE) ?? "", 10);
  const w = isNaN(saved) ? PROPS_KEY_DEFAULT : Math.max(PROPS_KEY_MIN, Math.min(PROPS_KEY_MAX, saved));
  elementPropsEl.style.setProperty("--prop-key-width", `${w}px`);
}

let _propResizing = false;
let _propStartX = 0;
let _propStartWidth = 0;
let _propResizerEl: HTMLElement | null = null;

elementPropsEl.addEventListener("mousedown", (e: MouseEvent) => {
  const target = e.target as HTMLElement;
  if (!target.classList.contains("prop-col-resizer")) return;
  _propResizing = true;
  _propResizerEl = target;
  _propStartX = e.clientX;
  _propStartWidth = parseInt(elementPropsEl.style.getPropertyValue("--prop-key-width") || String(PROPS_KEY_DEFAULT), 10);
  target.classList.add("dragging");
  document.body.style.cursor = "col-resize";
  document.body.style.userSelect = "none";
  e.preventDefault();
});

document.addEventListener("mousemove", (e: MouseEvent) => {
  if (!_propResizing) return;
  const dx = e.clientX - _propStartX;
  const newWidth = Math.max(PROPS_KEY_MIN, Math.min(PROPS_KEY_MAX, _propStartWidth + dx));
  elementPropsEl.style.setProperty("--prop-key-width", `${newWidth}px`);
});

document.addEventListener("mouseup", () => {
  if (!_propResizing) return;
  _propResizing = false;
  _propResizerEl?.classList.remove("dragging");
  _propResizerEl = null;
  document.body.style.cursor = "";
  document.body.style.userSelect = "";
  const finalWidth = parseInt(elementPropsEl.style.getPropertyValue("--prop-key-width") || String(PROPS_KEY_DEFAULT), 10);
  localStorage.setItem(PROPS_KEY_STORAGE, String(finalWidth));
});

// ── Panel resize ──────────────────────────────────────────────────────────────

const _shell = document.querySelector<HTMLElement>(".viewer-shell");
const _resizerEl = document.getElementById("panel-resizer");

if (_shell && _resizerEl) {
  const STORAGE_KEY = "geoifc-panel-width";
  const MIN_WIDTH = 180;
  const MAX_WIDTH = 700;
  const DEFAULT_WIDTH = 270;

  const savedWidth = parseInt(localStorage.getItem(STORAGE_KEY) ?? "", 10);
  const initialWidth = isNaN(savedWidth) ? DEFAULT_WIDTH : Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, savedWidth));
  _shell.style.gridTemplateColumns = `minmax(0, 1fr) 4px ${initialWidth}px`;

  let _resizing = false;
  let _startX = 0;
  let _startWidth = 0;

  _resizerEl.addEventListener("mousedown", (e: MouseEvent) => {
    _resizing = true;
    _startX = e.clientX;
    _startWidth = parseInt(_shell.style.gridTemplateColumns.split(" ").pop() ?? String(DEFAULT_WIDTH), 10);
    _resizerEl.classList.add("dragging");
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    e.preventDefault();
  });

  document.addEventListener("mousemove", (e: MouseEvent) => {
    if (!_resizing) return;
    const dx = _startX - e.clientX;
    const newWidth = Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, _startWidth + dx));
    _shell.style.gridTemplateColumns = `minmax(0, 1fr) 4px ${newWidth}px`;
  });

  document.addEventListener("mouseup", () => {
    if (!_resizing) return;
    _resizing = false;
    _resizerEl.classList.remove("dragging");
    document.body.style.cursor = "";
    document.body.style.userSelect = "";
    const finalWidth = parseInt(_shell.style.gridTemplateColumns.split(" ").pop() ?? String(DEFAULT_WIDTH), 10);
    localStorage.setItem(STORAGE_KEY, String(finalWidth));
  });
}
