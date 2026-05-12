import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Прокси на FastAPI: запросы с того же origin, что и dev-сервер (без CORS в браузере)
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
    },
  },
});
