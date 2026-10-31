// Same rules as the backend (catalog/services.py): the ABNT style adds
// "ed." and "p." itself, so these fields keep numbers only.
export function cleanEdition(value: string) {
  for (const n of (value ?? "").match(/\d+/g) ?? [])
    if (Number(n) < 1000) return String(Number(n));
  return "";
}
export function cleanPages(value: string, kind = "book") {
  value = value ?? "";
  if (kind === "article-journal") {
    const span = value.match(/(\d+)\s*[-–—]+\s*(\d+)/);
    if (span) return `${Number(span[1])}-${Number(span[2])}`;
  }
  const beforeP = value.match(/(\d+)\s*(?:p\b|pp\b|pág|pag|f\.)/i);
  if (beforeP) return String(Number(beforeP[1]));
  const numbers = (value.match(/\d+/g) ?? []).map(Number);
  return numbers.length ? String(Math.max(...numbers)) : "";
}
// While typing: keep what is already valid, clean anything pasted with text.
export function typedEdition(value: string) {
  return /^\d*$/.test(value) ? value : cleanEdition(value);
}
export function typedPages(value: string, kind: string) {
  const ok = kind === "article-journal" ? /^\d*(-\d*)?$/ : /^\d*$/;
  return ok.test(value) ? value : cleanPages(value, kind);
}
