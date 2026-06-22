import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { IfcAPI, type FlatMesh, type PlacedGeometry } from "web-ifc";

import "./viewer.css";

type ViewerPayload = {
  kind?: string;
  source?: string;
  dataBase64?: string;
  modelUrl?: string;
};

// DOM elements — getElementById never throws
const canvas = document.getElementById("viewer-canvas") as HTMLCanvasElement;
const sourceName = document.getElementById("source-name") as HTMLElement;
const sourceStatus = document.getElementById("source-status") as HTMLElement;
const sourceKind = document.getElementById("source-kind") as HTMLElement;
const viewportStatus = document.getElementById("viewport-status") as HTMLElement;

function setStatus(message: string) {
  if (sourceStatus) sourceStatus.textContent = message;
  if (viewportStatus) viewportStatus.textContent = message;
}

function sourceBaseName(source?: string) {
  if (!source) return "No IFC selected";
  return String(source).split(/[\\/]/).pop() || source;
}

// Viewer state — Three.js objects are null if WebGL init failed
let _initError: string | null = null;
let ifcApi: IfcAPI | null = null;
let currentModelId: number | null = null;
let modelGroup: THREE.Group | null = null;
let renderer: THREE.WebGLRenderer | null = null;
let scene: THREE.Scene | null = null;
let camera: THREE.PerspectiveCamera | null = null;
let controls: OrbitControls | null = null;

// --- Define window.GeoIfcViewer FIRST so Python polling always finds it.
// openReference checks _initError and falls back gracefully if WebGL failed.
window.GeoIfcViewer = {
  async openReference(payload: ViewerPayload) {
    if (_initError) {
      setStatus(`3D renderer unavailable: ${_initError}`);
      console.warn("openReference called but 3D renderer failed to initialize:", _initError);
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

function resize() {
  if (!renderer || !camera) return;
  const rect = canvas.getBoundingClientRect();
  const width = Math.max(1, Math.floor(rect.width));
  const height = Math.max(1, Math.floor(rect.height));
  renderer.setSize(width, height, false);
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
}

function animate() {
  if (!renderer || !scene || !camera || !controls) return;
  resize();
  controls.update();
  renderer.render(scene, camera);
  window.requestAnimationFrame(animate);
}

async function getIfcApi() {
  if (ifcApi) return ifcApi;
  const api = new IfcAPI();
  api.SetWasmPath("./assets/");
  await api.Init(undefined, true);
  ifcApi = api;
  return api;
}

function clearModel() {
  if (!scene) return;
  if (modelGroup) {
    scene.remove(modelGroup);
    modelGroup.traverse((object: THREE.Object3D) => {
      const mesh = object as THREE.Mesh;
      mesh.geometry?.dispose();
      const material = mesh.material as THREE.Material | undefined;
      material?.dispose();
    });
  }
  modelGroup = new THREE.Group();
  scene.add(modelGroup);

  if (currentModelId !== null && ifcApi) {
    ifcApi.CloseModel(currentModelId);
    currentModelId = null;
  }
}

function decodeBase64(dataBase64: string) {
  const binary = window.atob(dataBase64);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes;
}

function buildGeometry(api: IfcAPI, modelId: number, placedGeometry: PlacedGeometry) {
  const geometry = api.GetGeometry(modelId, placedGeometry.geometryExpressID);
  const vertexData = api.GetVertexArray(
    geometry.GetVertexData(),
    geometry.GetVertexDataSize()
  );
  const indexData = api.GetIndexArray(
    geometry.GetIndexData(),
    geometry.GetIndexDataSize()
  );

  const positions: number[] = [];
  const normals: number[] = [];
  for (let index = 0; index < vertexData.length; index += 6) {
    positions.push(vertexData[index], vertexData[index + 1], vertexData[index + 2]);
    normals.push(vertexData[index + 3], vertexData[index + 4], vertexData[index + 5]);
  }

  const bufferGeometry = new THREE.BufferGeometry();
  bufferGeometry.setAttribute(
    "position",
    new THREE.Float32BufferAttribute(positions, 3)
  );
  bufferGeometry.setAttribute("normal", new THREE.Float32BufferAttribute(normals, 3));
  bufferGeometry.setIndex(Array.from(indexData));
  bufferGeometry.applyMatrix4(
    new THREE.Matrix4().fromArray(placedGeometry.flatTransformation)
  );
  // Use optional chaining — in web-ifc 0.0.77 some objects are stack-allocated
  // and do not expose delete(); calling it unconditionally throws TypeError.
  geometry.delete?.();
  return bufferGeometry;
}

function fitCameraToModel(group: THREE.Group) {
  if (!camera || !controls) return;
  const box = new THREE.Box3().setFromObject(group);
  if (box.isEmpty()) return;
  const center = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3());
  const maxSize = Math.max(size.x, size.y, size.z);
  const distance = Math.max(maxSize * 1.4, 10);

  controls.target.copy(center);
  camera.position.set(center.x + distance, center.y + distance * 0.7, center.z + distance);
  camera.near = Math.max(distance / 1000, 0.1);
  camera.far = distance * 100;
  camera.updateProjectionMatrix();
  controls.update();
}

function addFlatMesh(api: IfcAPI, modelId: number, flatMesh: FlatMesh) {
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
    const mesh = new THREE.Mesh(buildGeometry(api, modelId, placedGeometry), material);
    mesh.userData.expressID = flatMesh.expressID;
    modelGroup.add(mesh);
  }
}

async function loadIfc(payload: ViewerPayload) {
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
  if (modelId < 0) {
    throw new Error("web-ifc could not open the model.");
  }
  currentModelId = modelId;

  let meshCount = 0;
  api.StreamAllMeshes(modelId, (flatMesh) => {
    addFlatMesh(api, modelId, flatMesh);
    // Optional chaining: web-ifc 0.0.77 StreamAllMeshes provides stack-allocated
    // FlatMesh objects in some builds that do not expose delete().
    flatMesh.delete?.();
    meshCount += 1;
    if (meshCount % 25 === 0) {
      setStatus(`Loading IFC geometry... ${meshCount} elements`);
    }
  });

  if (modelGroup) {
    fitCameraToModel(modelGroup);
  }
  setStatus(`IFC geometry loaded: ${meshCount} elements`);
}

// --- Three.js + WebGL initialization (may fail on some QGIS builds)
// Three attempts in order of decreasing quality:
//   1. Standard WebGL (hardware, antialias)
//   2. Low-power hardware WebGL (no antialias)
//   3. Explicit software context with failIfMajorPerformanceCaveat:false
//      (enables SwiftShader when --enable-unsafe-swiftshader is active)
try {
  try {
    renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  } catch {
    try {
      renderer = new THREE.WebGLRenderer({ canvas, antialias: false, powerPreference: "low-power" });
    } catch {
      const softCtx =
        (canvas.getContext("webgl2", { failIfMajorPerformanceCaveat: false }) as WebGL2RenderingContext | null) ||
        (canvas.getContext("webgl", { failIfMajorPerformanceCaveat: false }) as WebGLRenderingContext | null);
      if (!softCtx) throw new Error("WebGL unavailable (hardware and software rendering both failed)");
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

  const grid = new THREE.GridHelper(20, 20, 0xcfd7df, 0xdfe6ed);
  scene.add(grid);

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

// --- Poll /current.json every 1.5 s so the viewer reacts to feature selection
// in QGIS without requiring a subprocess restart. The server increments
// "version" each time set_ifc_path() is called; we reload only on change.
let _pollVersion = -1;

async function pollCurrentIfc() {
  try {
    const res = await fetch("/current.json");
    if (!res.ok) return;
    const data = (await res.json()) as { version: number; ifc_url: string | null };
    if (data.version !== _pollVersion) {
      _pollVersion = data.version;
      if (data.ifc_url) {
        console.log("GeoIFC Assets: new IFC detected (version", data.version, "):", data.ifc_url);
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
    // Server not ready yet or connection closed — ignore silently.
  }
}

// Initial poll after 800 ms (let WASM init settle), then every 1.5 s.
setTimeout(() => {
  void pollCurrentIfc();
  setInterval(() => void pollCurrentIfc(), 1500);
}, 800);
