import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
const credentials = JSON.parse(readFileSync("/tmp/aleph-e2e.json", "utf8"));

test("cadastro abre pronto para o leitor e busca ao ler o ISBN", async ({
  page,
}) => {
  const lookups: string[] = [];
  await page.route("**/api/v1/lookup?**", (route) => {
    lookups.push(new URL(route.request().url()).searchParams.get("value")!);
    return route.fulfill({
      json: {
        candidates: [
          {
            source: "Teste",
            data: { title: "Livro lido pelo leitor", authors: [] },
          },
        ],
        key: "",
        warnings: [],
      },
    });
  });
  await page.goto("/");
  await page.getByLabel("Usuário", { exact: true }).fill(credentials.username);
  await page.getByLabel("Senha", { exact: true }).fill(credentials.password);
  await page.getByRole("button", { name: "Entrar", exact: true }).click();
  await page
    .getByRole("button", { name: "+ Cadastrar livro ou artigo" })
    .click();

  const field = page.locator("#scan-isbn");
  await expect(field).toBeFocused();
  await expect(page.getByLabel("Tipo de identificador")).toHaveValue("isbn");

  // Reader that ends with Enter: exactly one search.
  await page.keyboard.type("9788535912258", { delay: 5 });
  await page.keyboard.press("Enter");
  await expect(page.getByText("Livro lido pelo leitor")).toBeVisible();
  await page.waitForTimeout(500);
  expect(lookups).toEqual(["9788535912258"]);

  // Reader without Enter: the search starts by itself on a valid ISBN.
  await field.fill("");
  await page.keyboard.type("8571643296", { delay: 5 });
  await expect.poll(() => lookups.length).toBe(2);
  expect(lookups[1]).toBe("8571643296");

  // An incomplete code does not search.
  await field.fill("97885");
  await page.waitForTimeout(500);
  expect(lookups.length).toBe(2);
});
