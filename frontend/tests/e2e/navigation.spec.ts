import { expect, test } from "@playwright/test";

/**
 * Fluxo principal da Sprint 2: login -> planta baixa -> clique no ativo ->
 * visualizacao da telemetria. Requer a stack no ar e o seed aplicado.
 */
test("login -> planta -> ativo -> telemetria", async ({ page }) => {
  // 1. Login (mock)
  await page.goto("/login");
  await page.getByLabel("Usuario").fill("admin");
  await page.getByLabel("Senha").fill("admin123");
  await page.getByRole("button", { name: /Entrar/i }).click();
  await expect(page).toHaveURL(/\/dashboard/);

  // 2. Abrir a planta baixa pela arvore de hierarquia
  await page
    .getByRole("link", { name: /Planta/i })
    .first()
    .click();
  await expect(page).toHaveURL(/\/plant\//);

  // 3. Clicar no marcador do ativo MTR-001 no mapa interativo
  await page.locator('[data-asset-tag="MTR-001"]').click();
  await expect(page).toHaveURL(/\/asset\/MTR-001/);

  // 4. Confirmar que a telemetria do ativo aparece
  await expect(page.getByText(/Telemetria em tempo real/i)).toBeVisible();
});
