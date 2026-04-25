import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  preview: {
    allowedHosts: ["welcoming-transformation-production.up.railway.app"],
    port: process.env.PORT || 4173,
    host: "0.0.0.0",
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
  },
});