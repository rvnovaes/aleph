import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
const credentials = JSON.parse(readFileSync("/tmp/aleph-e2e.json", "utf8"));

test("cadastro abre pronto para o leitor e busca ao ler o ISBN", async ({
  page,
}) => {
  const lookups: string[] = [];
  // The search streams progress events; answer with a short, fixed stream.
  await page.route("**/api/v1/lookup/stream?**", (route) => {
    lookups.push(new URL(route.request().url()).searchParams.get("value")!);
    const events = [
      { type: "plan", steps: ["UFSC", "UFMG", "Open Library"] },
      { type: "step", source: "UFSC", status: "running" },
      { type: "step", source: "UFSC", status: "done", count: 0 },
      { type: "step", source: "UFMG", status: "running" },
      { type: "step", source: "UFMG", status: "done", count: 1 },
      { type: "step", source: "Open Library", status: "skipped" },
      {
        type: "result",
        candidates: [
          {
            source: "Zeus · UFMG",
            data: { title: "Livro lido pelo leitor", authors: [] },
          },
        ],
        key: "",
        warnings: [],
      },
    ];
    return route.fulfill({
      contentType: "text/event-stream",
      body: events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join(""),
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
  const panel = page.getByLabel("Andamento da busca");
  await expect(panel).toContainText("Busca concluída");
  await expect(panel).toContainText("UFSC: não encontrado");
  await expect(panel).toContainText("UFMG: 1 resultado");
  await expect(panel).toContainText("Demais fontes não consultadas");
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
