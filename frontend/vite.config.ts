
// @lovable.dev/vite-tanstack-config already includes:
// - TanStack devtools
// - tanstackStart
// - viteReact
// - tailwindcss
// - tsConfigPaths
// - nitro
// - VITE_* environment injection
// - @ path alias
// - React/TanStack deduplication
// - Error logger plugins
// - Sandbox detection
//
// Do NOT add these plugins manually.

import { defineConfig } from "@lovable.dev/vite-tanstack-config";

export default defineConfig({
  tanstackStart: {
    // Custom SSR server entry
    server: {
      entry: "server",
    },
  },

  vite: {
    server: {
      proxy: {
        // Authentication endpoints
        "/auth": {
          target: "http://127.0.0.1:8000",
          changeOrigin: true,
        },

        // Backend API endpoints
        "/api": {
          target: "http://127.0.0.1:8000",
          changeOrigin: true,
        },

        "/modules": {
          target: "http://127.0.0.1:8000",
          changeOrigin: true,
        },
        "/subjects": {
          target: "http://127.0.0.1:8000",
          changeOrigin: true,
        },
        "/teaching-assignments": {
          target: "http://127.0.0.1:8000",
          changeOrigin: true,
        },
        "/quizzes": {
          target: "http://127.0.0.1:8000",
          changeOrigin: true,
        },
        "/attempts": {
          target: "http://127.0.0.1:8000",
          changeOrigin: true,
        },
        "/students": {
          target: "http://127.0.0.1:8000",
          changeOrigin: true,
        },
        "/uploads": {
          target: "http://127.0.0.1:8000",
          changeOrigin: true,
        },
        // Backend health endpoint
        "/health": {
          target: "http://127.0.0.1:8000",
          changeOrigin: true,
        },
      },
    },
  },
});
