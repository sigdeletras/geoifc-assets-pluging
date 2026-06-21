import { defineConfig } from "vite";

export default defineConfig({
  root: "webviewer_src",
  base: "./",
  build: {
    outDir: "../geoifcassets/webviewer",
    emptyOutDir: true,
    target: "es2020",
    rollupOptions: {
      output: {
        entryFileNames: "assets/[name].js",
        chunkFileNames: "assets/[name].js",
        assetFileNames: "assets/[name][extname]",
      },
    },
  },
});
