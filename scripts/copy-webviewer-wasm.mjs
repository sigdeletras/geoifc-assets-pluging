import { copyFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(fileURLToPath(new URL("../package.json", import.meta.url)));
const targetDir = join(root, "geoifcassets", "webviewer", "assets");

mkdirSync(targetDir, { recursive: true });
copyFileSync(
  join(root, "node_modules", "web-ifc", "web-ifc.wasm"),
  join(targetDir, "web-ifc.wasm"),
);
