import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
        configure: (proxy) => {
          // Prevent Vite's http-proxy from buffering SSE / streaming responses.
          proxy.on("proxyRes", (_proxyRes, _req, res) => {
            res.setHeader("X-Accel-Buffering", "no");
          });
          proxy.on("error", (_err, _req, res) => {
            if (
              res &&
              typeof (res as import("http").ServerResponse).writeHead ===
                "function"
            ) {
              (res as import("http").ServerResponse).writeHead(502, {
                "Content-Type": "text/plain",
              });
              (res as import("http").ServerResponse).end(
                "Proxy error: backend unreachable",
              );
            }
          });
        },
      },
    },
  },
});
