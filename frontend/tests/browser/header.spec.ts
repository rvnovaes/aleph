import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
const credentials = JSON.parse(readFileSync("/tmp/aleph-e2e.json", "utf8"));

test("barra superior: catálogo, +, engrenagem, tema e sair", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByLabel("Usuário", { exact: true }).fill(credentials.username);
  await page.getByLabel("Senha", { exact: true }).fill(credentials.password);
  await page.getByRole("button", { name: "Entrar", exact: true }).click();

  const nav = page.getByRole("navigation", { name: "Navegação" });
  await expect(nav.getByText(/^Sair/)).toBeVisible();
  const names = await nav
    .locator(":scope > button, :scope > .menu-wrap > button")
    .evaluateAll((els) =>
      els.map((e) => e.getAttribute("aria-label") ?? e.textContent?.trim()),
    );
  expect(names[0]).toBe("Catálogo");
  expect(names[1]).toBe("Cadastrar livro ou artigo");
  expect(names[2]).toBe("Configurações");
  expect(names[3]).toMatch(/^Ativar modo/);
  expect(names[4]).toMatch(/^Sair/);

  // The gear holds Localizações and Editoras; Escape closes it.
  await page.getByRole("button", { name: "Configurações" }).click();
  await expect(page.getByRole("menuitem")).toHaveText([
    "Localizações",
    "Editoras",
  ]);
  await page.keyboard.press("Escape");
  await expect(page.getByRole("menu")).toBeHidden();

  // "+" opens the add form ready for the barcode reader.
  await nav.getByRole("button", { name: "Cadastrar livro ou artigo" }).click();
  await expect(page.locator("#scan-isbn")).toBeFocused();

  // Catalog filter for PDF / physical books.
  await page.getByRole("button", { name: "Catálogo", exact: true }).click();
  const media = page.getByLabel("Formato");
  const listed = page.waitForRequest((r) => r.url().includes("media=pdf"));
  await media.selectOption("pdf");
  await listed;
});
