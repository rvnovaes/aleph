import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
const credentials = JSON.parse(readFileSync("/tmp/aleph-e2e.json", "utf8"));

test("idioma cadastrável, etiquetas múltiplas e localização pesquisável", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await page.getByLabel("Usuário", { exact: true }).fill(credentials.username);
  await page.getByLabel("Senha", { exact: true }).fill(credentials.password);
  await page.getByRole("button", { name: "Entrar", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Minha biblioteca" }),
  ).toBeVisible();

  // Theme button shows only its icon.
  await expect(page.locator(".theme-toggle")).toHaveText(/^\s*[☀☾]\s*$/);

  // Two books with tags, the second one in a new language.
  for (const [title, tags, lang] of [
    ["Livro das duas etiquetas", "Filosofia\nPlatão", "Portug"],
    ["Livro de uma etiqueta", "Filosofia", "Tupi (tup)"],
  ]) {
    await page
      .getByRole("button", { name: "+ Cadastrar livro ou artigo" })
      .click();
    await page.getByLabel("Título", { exact: true }).fill(title);
    await page.getByLabel("Etiquetas pessoais").fill(tags);
    await page.getByLabel("Idioma", { exact: true }).fill(lang);
    if (lang.startsWith("Tupi")) {
      await page
        .getByRole("option", { name: "+ Cadastrar “Tupi (tup)”" })
        .click();
      await expect(page.getByRole("status")).toContainText(
        "Idioma “Tupi” cadastrado",
      );
    } else {
      await page.getByRole("option", { name: "Português (por)" }).click();
    }
    await page
      .getByRole("button", { name: "Salvar cadastro", exact: true })
      .click();
    await expect(
      page.getByText("Cadastro salvo.", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText(lang.startsWith("Tupi") ? "tup" : "por").first(),
    ).toBeVisible();
    await page.getByRole("button", { name: "Catálogo", exact: true }).click();
  }

  // Tags: type to pick several; the list narrows to books with all of them.
  const tagField = page.getByLabel("Filtrar por etiquetas");
  await tagField.fill("filo");
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("button", { name: "Livro de uma etiqueta" }),
  ).toBeVisible();
  await tagField.fill("plat");
  await page.getByRole("option", { name: "Platão" }).click();
  await expect(
    page.getByRole("button", { name: "Livro das duas etiquetas" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Livro de uma etiqueta" }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Remover Platão" }).click();
  await expect(
    page.getByRole("button", { name: "Livro de uma etiqueta" }),
  ).toBeVisible();

  // Location filter accepts typing.
  await page
    .getByRole("combobox", { name: "Localização", exact: true })
    .fill("piloto");
  await expect(
    page.getByRole("option", { name: "Escritório piloto / 03 / 02" }),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  expect(errors).toEqual([]);
});

test("exclui editora só quando não tem cadastros", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Usuário", { exact: true }).fill(credentials.username);
  await page.getByLabel("Senha", { exact: true }).fill(credentials.password);
  await page.getByRole("button", { name: "Entrar", exact: true }).click();
  await page.getByRole("button", { name: "Configurações" }).click();
  await page.getByRole("menuitem", { name: "Editoras" }).click();
  await page.getByLabel("Nome da editora").fill("Editora vazia de teste");
  await page.getByRole("button", { name: "Cadastrar editora" }).click();
  await expect(page.getByText("Editora salva.")).toBeVisible();
  // The publisher created by the catalog test has a book: button stays disabled.
  await expect(
    page.getByRole("button", { name: "Excluir Editora de teste", exact: true }),
  ).toBeDisabled();
  page.once("dialog", (d) => d.accept());
  await page
    .getByRole("button", { name: "Excluir Editora vazia de teste" })
    .click();
  await expect(page.getByRole("status").first()).toContainText(
    "Editora “Editora vazia de teste” excluída",
  );
  await expect(
    page.locator("article strong", { hasText: "Editora vazia de teste" }),
  ).toHaveCount(0);
});
