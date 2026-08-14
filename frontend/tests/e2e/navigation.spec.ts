import { expect, test } from "@playwright/test";

/**
 * Fluxo principal: login -> planta baixa -> clique no ativo -> telemetria.
 * Requer a stack no ar e o seed aplicado.
 */
test("login -> planta -> ativo -> telemetria", async ({ page }) => {
  // 1. Login (sem credenciais pré-preenchidas)
  await page.goto("/login");
  await page.getByLabel("Usuário").fill("admin");
  await page.getByLabel("Senha").fill("admin123");
  await page.getByRole("button", { name: /Entrar/i }).click();
  await expect(page).toHaveURL(/\/dashboard/);

  // 2. Abrir a planta baixa pela árvore de hierarquia
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

/** Guard de sessão: rota protegida sem login redireciona para /login. */
test("rota protegida sem sessao redireciona para login", async ({ page }) => {
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/login/);
});

/** Jornada do alerta: a TAG na página de alertas leva direto ao ativo. */
test("alerta -> ativo em um clique", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Usuário").fill("admin");
  await page.getByLabel("Senha").fill("admin123");
  await page.getByRole("button", { name: /Entrar/i }).click();
  await expect(page).toHaveURL(/\/dashboard/);

  await page.goto("/alerts");
  const assetLink = page.getByRole("link", { name: /MTR-001/ }).first();
  // Se houver alerta na lista, o link leva ao ativo em 1 clique.
  if (await assetLink.isVisible().catch(() => false)) {
    await assetLink.click();
    await expect(page).toHaveURL(/\/asset\/MTR-001/);
  }
});
