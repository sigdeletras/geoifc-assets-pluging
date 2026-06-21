import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { IfcAPI, type FlatMesh, type PlacedGeometry } from "web-ifc";

import "./viewer.css";

type ViewerPayload = {
  kind?: string;
  source?: string;
  dataBase64?: string;
};

const canvas = document.getElementById("viewer-canvas") as HTMLCanvasElement;
const sourceName = document.getElementById("source-name") as HTMLElement;
const sourceStatus = document.getElementById("source-status") as HTMLElement;
const sourceKind = document.getElementById("source-kind") as HTMLElement;
const viewportStatus = document.getElementById("viewport-status") as HTMLElement;

const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setClearColor(0xeef2f6);
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));

const scene = new THREE.Scene();
scene.add(new THREE.HemisphereLight(0xffffff, 0x6b7280, 2.4));

const camera = new THREE.PerspectiveCamera(55, 1, 0.1, 1000000);
camera.position.set(8, 6, 8);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;

const grid = new THREE.GridHelper(20, 20, 0xcfd7df, 0xdfe6ed);
scene.add(grid);

let modelGroup: THREE.Group | null = null;
let ifcApi: IfcAPI | null = null;
let currentModelId: number | null = null;

function resize() {
  const rect = canvas.getBoundingClientRect();
  const width = Math.max(1, Math.floor(rect.width));
  const height = Math.max(1, Math.floor(rect.height));
  renderer.setSize(width, height, false);
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
}

function animate() {
  resize();
  controls.update();
  renderer.render(scene, camera);
  window.requestAnimationFrame(animate);
}

function sourceBaseName(source?: string) {
  if (!source) {
    return "No IFC selected";
  }
  return String(source).split(/[\\/]/).pop() || source;
}

function setStatus(message: string) {
  sourceStatus.textContent = message;
  viewportStatus.textContent = message;
}

async function getIfcApi() {
  if (ifcApi) {
    return ifcApi;
  }
  const api = new IfcAPI();
  api.SetWasmPath("./assets/");
  await api.Init(undefined, true);
  ifcApi = api;
  return api;
}

function clearModel() {
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
  bufferGeometry.applyMatrix4(new THREE.Matrix4().fromArray(placedGeometry.flatTransformation));
  geometry.delete();
  return bufferGeometry;
}

function fitCameraToModel(group: THREE.Group) {
  const box = new THREE.Box3().setFromObject(group);
  if (box.isEmpty()) {
    return;
  }
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
    modelGroup?.add(mesh);
  }
}

async function loadIfc(payload: ViewerPayload) {
  clearModel();
  if (!payload.dataBase64) {
    setStatus("IFC source received. No local IFC bytes were provided.");
    return;
  }

  setStatus("Loading IFC geometry...");
  const api = await getIfcApi();
  const data = decodeBase64(payload.dataBase64);
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
    flatMesh.delete();
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

window.GeoIfcViewer = {
  async openReference(payload: ViewerPayload) {
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

window.addEventListener("resize", resize);
resize();
animate();
