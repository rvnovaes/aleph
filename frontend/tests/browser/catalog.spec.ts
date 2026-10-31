import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
const credentials = JSON.parse(readFileSync("/tmp/aleph-e2e.json", "utf8"));
test("login, localização, cadastro, busca e referência", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Entre na sua biblioteca." }),
  ).toBeVisible();
  await page.getByLabel("Usuário", { exact: true }).fill(credentials.username);
  await page.getByLabel("Senha", { exact: true }).fill(credentials.password);
  await page.getByRole("button", { name: "Entrar", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Minha biblioteca" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Configurações" }).click();
  await page.getByRole("menuitem", { name: "Localizações" }).click();
  await page.getByLabel("Ambiente", { exact: true }).fill("Escritório piloto");
  await page.getByLabel("Estante", { exact: true }).fill("03");
  await page.getByLabel("Prateleira", { exact: true }).fill("02");
  await page.getByRole("button", { name: "Adicionar localização" }).click();
  await expect(page.getByRole("status")).toContainText("Localização salva");
  await page.getByRole("button", { name: "Catálogo", exact: true }).click();
  await page
    .getByRole("button", { name: "+ Cadastrar livro ou artigo" })
    .click();
  await page
    .getByLabel("Título", { exact: true })
    .fill("Livro do teste de navegação");
  await page.getByLabel("Ano", { exact: true }).fill("2025");
  await page.getByLabel("Editora", { exact: true }).fill("Editora de teste");
  await page.getByLabel("Cidade de publicação").fill("São Paulo");
  await page.getByRole("button", { name: "+ Autor ou responsável" }).click();
  await page.getByLabel("Nome completo").fill("Ana Silva");
  await page.getByLabel("Prenomes").fill("Ana");
  await page.getByLabel("Sobrenome").fill("Silva");
  await page
    .getByLabel("Localização para o próximo exemplar")
    .fill("piloto 02");
  await page
    .getByRole("option", { name: "Escritório piloto / 03 / 02" })
    .click();
  await page
    .getByRole("button", { name: "Salvar cadastro", exact: true })
    .click();
  await expect(
    page.getByText("Cadastro salvo.", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Código do exemplar", { exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel("Título", { exact: true })).toHaveCount(0);
  await expect(page.getByLabel("Referência ABNT para copiar")).toHaveValue(
    /SILVA, Ana/,
  );
  await page.getByRole("button", { name: "Editar", exact: true }).click();
  await page
    .getByLabel("Observações", { exact: true })
    .fill("Edição ainda não salva");
  await page
    .getByLabel("Enviar ou substituir capa")
    .setInputFiles("/tmp/aleph-e2e-cover.jpg");
  await expect(page.getByRole("status")).toContainText(
    "Capa otimizada e salva",
  );
  await expect(page.getByLabel("Observações", { exact: true })).toHaveValue(
    "Edição ainda não salva",
  );
  const cover = page.getByAltText("Capa de Livro do teste de navegação");
  await expect(cover).toBeVisible();
  await expect
    .poll(() => cover.evaluate((img: HTMLImageElement) => img.naturalWidth))
    .toBe(600);
  expect(
    await cover.evaluate((img: HTMLImageElement) => img.naturalHeight),
  ).toBe(900);
  await page
    .getByLabel("Enviar PDF (até 100 MB)")
    .setInputFiles("/tmp/aleph-e2e.pdf");
  await expect(page.getByRole("status")).toContainText("PDF disponível");
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("link", { name: "Baixar", exact: true }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("aleph-e2e.pdf");
  await page.getByRole("button", { name: "Ler", exact: true }).click();
  await expect(page.getByTitle("Leitor de PDF")).toBeVisible();
  await page
    .getByRole("button", { name: "Cancelar edição e voltar aos detalhes" })
    .click();
  await expect(page.getByLabel("Referência ABNT para copiar")).toHaveValue(
    /SILVA, Ana/,
  );
  await expect(page.getByLabel("Título", { exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "Editar", exact: true }).click();
  await page
    .getByLabel("Referência ABNT salva", { exact: true })
    .fill("Referência revisada manualmente.");
  await page
    .getByRole("button", { name: "Salvar cadastro", exact: true })
    .click();
  await expect(page.getByLabel("Referência ABNT para copiar")).toHaveValue(
    "Referência revisada manualmente.",
  );
  await page.getByRole("button", { name: "Editar", exact: true }).click();
  await page.getByLabel("Cidade de publicação").fill("Recife");
  await expect(
    page.getByLabel("Referência ABNT salva", { exact: true }),
  ).toHaveValue("Referência revisada manualmente.");
  await page
    .getByRole("button", { name: "Gerar novamente", exact: true })
    .click();
  await expect(
    page.getByLabel("Referência ABNT salva", { exact: true }),
  ).toHaveValue(/Recife/);
  await page
    .getByRole("button", { name: "Salvar cadastro", exact: true })
    .click();
  await expect(page.getByLabel("Referência ABNT para copiar")).toHaveValue(
    /Recife/,
  );
  await page.getByRole("button", { name: "Catálogo", exact: true }).click();
  await page.getByLabel("Buscar no acervo").fill("navegação");
  await page.getByRole("button", { name: "Buscar", exact: true }).click();
  await expect(
    page.getByRole("button", {
      name: "Livro do teste de navegação",
      exact: true,
    }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Livro do teste de navegação", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Editar", exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel("Título", { exact: true })).toHaveCount(0);
  await page
    .getByRole("button", {
      name: "Ampliar capa de Livro do teste de navegação",
      exact: true,
    })
    .click();
  await expect(
    page.getByRole("dialog", { name: "Capa ampliada" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Fechar capa" }).click();
  await page.getByRole("button", { name: "Ler", exact: true }).click();
  await expect(page.getByTitle("Leitor de PDF")).toBeVisible();
  await page.screenshot({ path: "/tmp/aleph-details.png", fullPage: true });
  await expect(
    page.getByAltText("Capa de Livro do teste de navegação"),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Sair · " + credentials.username })
    .click();
  await expect(
    page.getByRole("heading", { name: "Entre na sua biblioteca." }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});
