import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import CSL from "citeproc";
const style = readFileSync("static/styles/abnt.csl", "utf8");
const locale = readFileSync("static/styles/locales-pt-BR.xml", "utf8");
function render(item) {
  const engine = new CSL.Engine(
    { retrieveLocale: () => locale, retrieveItem: () => item },
    style,
    "pt-BR",
  );
  engine.setOutputFormat("text");
  engine.updateItems([item.id]);
  return engine.makeBibliography()[1].join("\n");
}
test("livro com autor, cidade, editora, ano e edição", () => {
  const text = render({
    id: "1",
    type: "book",
    title: "Dom Casmurro",
    author: [{ family: "Assis", given: "Machado de" }],
    publisher: "Editora Exemplo",
    "publisher-place": "São Paulo",
    edition: "2",
    issued: { "date-parts": [[2025]] },
  });
  for (const value of [
    "ASSIS",
    "Machado de",
    "Dom Casmurro",
    "São Paulo",
    "Editora Exemplo",
    "2025",
    "2",
  ])
    assert.ok(text.includes(value), text);
});
test("artigo com DOI, periódico, volume e páginas", () => {
  const text = render({
    id: "2",
    type: "article-journal",
    title: "Artigo de exemplo",
    author: [
      { family: "Silva", given: "Ana" },
      { family: "Souza", given: "José" },
    ],
    "container-title": "Revista de Estudos",
    volume: "3",
    issue: "2",
    page: "10-20",
    DOI: "10.1234/example",
    issued: { "date-parts": [[2025]] },
  });
  for (const value of [
    "SILVA",
    "SOUZA",
    "Revista de Estudos",
    "10",
    "20",
    "10.1234/example",
  ])
    assert.ok(text.includes(value), text);
});
test("organizador e tradutor não são perdidos", () => {
  const text = render({
    id: "3",
    type: "book",
    title: "Coletânea",
    editor: [{ family: "Silva", given: "Ana" }],
    translator: [{ family: "Souza", given: "José" }],
    issued: { "date-parts": [[2025]] },
  });
  assert.ok(text.includes("Silva") || text.includes("SILVA"), text);
  assert.ok(text.includes("Souza") || text.includes("SOUZA"), text);
});
