import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
// http://localhost:5173 — already allowed by the API's CORS config.
export default defineConfig({
    plugins: [react()],
    server: { port: 5173 },
});
