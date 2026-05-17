import { defineConfig, devices } from "@playwright/test";

/**
 * Configuracao dos testes e2e (Playwright).
 *
 * Pre-requisitos para executar:
 *   1. Stack no ar:  docker compose up -d  (com migrations + seed aplicados)
 *   2. Navegador:     npx playwright install chromium
 *   3. Rodar:         npm run test:e2e
 */
export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 30_000,
  expect: { timeout: 10_000 },
  retries: 0,
  reporter: "list",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3001",
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
