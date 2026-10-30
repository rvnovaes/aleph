import CSL from "citeproc";
import { request, type Work } from "./api";
async function render(records: Record<string, unknown>[]): Promise<string> {
  const [style, locale] = await Promise.all([
    fetch("/styles/abnt.csl").then((r) => {
      if (!r.ok) throw new Error("Estilo ABNT indisponível.");
      return r.text();
    }),
    fetch("/styles/locales-pt-BR.xml").then((r) => {
      if (!r.ok) throw new Error("Idioma ABNT indisponível.");
      return r.text();
    }),
  ]);
  const items = Object.fromEntries(
    records.map((item) => [String(item.id), item]),
  );
  const processor = new CSL.Engine(
    { retrieveLocale: () => locale, retrieveItem: (id) => items[id] },
    style,
    "pt-BR",
  );
  processor.setOutputFormat("text");
  processor.updateItems(Object.keys(items));
  return processor.makeBibliography()[1].join("\n").trim();
}
export async function bibliography(ids: number[]): Promise<string> {
  return render(
    await Promise.all(ids.map((id) => request(`/v1/works/${id}/csl`))),
  );
}
export async function bibliographyFromForm(work: Work): Promise<string> {
  return render([await request("/v1/citation-preview", "POST", work)]);
}
