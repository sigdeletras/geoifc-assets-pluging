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
  IFCPILE, IFCFOOTING,
  IFCBUILDINGELEMENTPROXY,
  IFCFLOWSEGMENT, IFCFLOWTERMINAL, IFCFLOWFITTING, IFCFLOWCONTROLLER,
  IFCDUCTSEGMENT, IFCPIPESEGMENT, IFCPIPEFITTING,
  IFCRELDEFINESBYPROPERTIES,
} from "web-ifc";

import "./viewer.css";

// ── Types ─────────────────────────────────────────────────────────────────────

type ViewerPayload = {
  kind?: string;
  source?: string;
  dataBase64?: string;
  modelUrl?: string;
};

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

// ── DOM refs ──────────────────────────────────────────────────────────────────

const canvas = document.getElementById("viewer-canvas") as HTMLCanvasElement;
const sourceName = document.getElementById("source-name") as HTMLElement;
const sourceStatus = document.getElementById("source-status") as HTMLElement;
const sourceKind = document.getElementById("source-kind") as HTMLElement;
const viewportStatus = document.getElementById("viewport-status") as HTMLElement;
const elementTreeEl = document.getElementById("element-tree") as HTMLElement;
const elementPropsEl = document.getElementById("element-props") as HTMLElement;

// ── Viewer state ──────────────────────────────────────────────────────────────

let _initError: string | null = null;
let ifcApi: IfcAPI | null = null;
let currentModelId: number | null = null;
let modelGroup: THREE.Group | null = null;
let renderer: THREE.WebGLRenderer | null = null;
let scene: THREE.Scene | null = null;
let camera: THREE.PerspectiveCamera | null = null;
let controls: OrbitControls | null = null;

// Element tree state
let elementsByCategory: Map<string, IFCElement[]> | null = null;
// propSetIndex[expressId] → list of propertySet expressIDs
const propSetIndex = new Map<number, number[]>();
let selectedExpressId: number | null = null;
const savedMaterials = new Map<THREE.Mesh, THREE.Material | THREE.Material[]>();

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
      console.warn("openReference called but renderer init failed:", _initError);
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

// ── IFC attribute helpers ─────────────────────────────────────────────────────

function extractAttrValue(val: unknown): string | null {
  if (val === null || val === undefined) return null;
  if (typeof val === "string") return val || null;
  if (typeof val === "number") return String(val);
  if (typeof val === "boolean") return String(val);
  if (Array.isArray(val)) return null;
  if (typeof val === "object") {
    const obj = val as Record<string, unknown>;
    // REF (type=5): relation handle — not a displayable value
    if (obj["type"] === 5) return null;
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

          // IfcPropertySingleValue → NominalValue
          let propVal: string | null = null;
          const nomVal = prop["NominalValue"];
          if (nomVal && typeof nomVal === "object") {
            propVal = extractAttrValue((nomVal as Record<string, unknown>)["value"]);
          }
          // IfcQuantity variants
          if (propVal === null) {
            for (const qKey of [
              "LengthValue", "AreaValue", "VolumeValue",
              "CountValue", "WeightValue", "TimeValue",
            ]) {
              const qv = extractAttrValue(prop[qKey]);
              if (qv !== null) {
                propVal = qv;
                break;
              }
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
  elementTreeEl.innerHTML =
    '<p class="panel-hint">Load an IFC model to browse elements.</p>';
  elementPropsEl.hidden = true;
  elementPropsEl.innerHTML = "";
}

// ── Property set index (built once per model load) ────────────────────────────

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
      } catch {
        /* skip individual relation errors */
      }
    }
  } catch {
    /* IFCRELDEFINESBYPROPERTIES not present in this model */
  }
}

// ── Element index (built once per model load) ─────────────────────────────────

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
    } catch {
      /* skip unreadable element */
    }
  }

  const grouped = new Map<string, IFCElement[]>();
  for (const el of elements) {
    if (!grouped.has(el.category)) grouped.set(el.category, []);
    grouped.get(el.category)!.push(el);
  }
  for (const arr of grouped.values()) {
    arr.sort((a, b) => a.name.localeCompare(b.name));
  }
  elementsByCategory = new Map(
    [...grouped.entries()].sort(([a], [b]) => a.localeCompare(b)),
  );

  renderTree();
}

// ── Tree rendering ────────────────────────────────────────────────────────────

function renderTree(): void {
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
      const li = document.createElement("li");
      const btn = document.createElement("button");
      btn.className = "tree-item";
      btn.textContent = el.name;
      btn.title = `${el.name}  (#${el.expressId})`;
      btn.dataset.eid = String(el.expressId);
      btn.addEventListener("click", () => selectElement(el.expressId));
      li.appendChild(btn);
      ul.appendChild(li);
    }

    details.appendChild(ul);
    frag.appendChild(details);
  }

  elementTreeEl.innerHTML = "";
  elementTreeEl.appendChild(frag);
}

// ── Element selection ─────────────────────────────────────────────────────────

function selectElement(expressId: number): void {
  // Toggle: click the same element again to deselect
  if (selectedExpressId === expressId) {
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

  // Zoom + highlight in the 3D viewport
  zoomToElement(expressId);
  highlightElement(expressId);

  // Show properties
  if (ifcApi !== null && currentModelId !== null) {
    const direct = readDirectAttrs(ifcApi, currentModelId, expressId);
    const psets = readPropertySets(ifcApi, currentModelId, expressId);
    renderProps(expressId, direct, psets);
  }
}

// ── Props rendering ───────────────────────────────────────────────────────────

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
      parts.push(
        `<div class="prop-row">` +
        `<span class="prop-key">${escHtml(key)}</span>` +
        `<span class="prop-val">${escHtml(value)}</span>` +
        `</div>`,
      );
    }
    parts.push(`</div>`);
  }

  for (const pset of psets) {
    parts.push(
      `<div class="pset-block"><div class="pset-name">${escHtml(pset.name)}</div>`,
    );
    for (const { key, value } of pset.props) {
      parts.push(
        `<div class="prop-row">` +
        `<span class="prop-key">${escHtml(key)}</span>` +
        `<span class="prop-val">${escHtml(value)}</span>` +
        `</div>`,
      );
    }
    parts.push(`</div>`);
  }

  if (direct.length === 0 && psets.length === 0) {
    parts.push(`<p class="panel-hint">No readable properties found.</p>`);
  }

  parts.push(`</div>`);

  elementPropsEl.innerHTML = parts.join("\n");
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

  buildPropSetIndex(api, modelId);
  buildElementIndex(api, modelId);

  setStatus(`IFC ready: ${meshCount} elements`);
}

// ── WebGL initialisation ──────────────────────────────────────────────────────
// Three attempts in order of decreasing quality:
//   1. Standard WebGL with antialias
//   2. Low-power hardware WebGL
//   3. Explicit software context (enables SwiftShader with --enable-unsafe-swiftshader)

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
// The Python subprocess increments "version" each time set_ifc_path() is called.
// We reload only when the version changes, without restarting the subprocess.

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

// Initial poll after 800 ms (let WASM init settle), then every 1.5 s.
setTimeout(() => {
  void pollCurrentIfc();
  setInterval(() => void pollCurrentIfc(), 1500);
}, 800);
