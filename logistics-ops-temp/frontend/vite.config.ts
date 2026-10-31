import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Em desenvolvimento, /api é encaminhado ao backend: o cookie do refresh token fica same-origin.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": "http://localhost:8000" },
  },
});
