import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// base relativa: funziona sia su GitHub Pages (project site) sia in locale
export default defineConfig({
  plugins: [react()],
  base: "./",
});
