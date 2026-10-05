import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 开发代理：/api → 后端 8805（同源相对路径，前端代码不写绝对地址）
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5805,
    proxy: {
      "/api": { target: "http://127.0.0.1:8805", changeOrigin: true },
    },
  },
  preview: {
    port: 5805,
    proxy: {
      "/api": { target: "http://127.0.0.1:8805", changeOrigin: true },
    },
  },
});
