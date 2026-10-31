export type Author = {
  name: string;
  given?: string;
  family?: string;
  institutional?: boolean;
  role: string;
};
export type Location = {
  id: number;
  room: string;
  bookcase: string;
  shelf: string;
  item_count: number;
  work_count: number;
};
export type Item = {
  id: number;
  location_id: number | null;
  location: string;
  code: string;
  notes: string;
  legacy_barcode: string;
  purchase_price: string | null;
  estimated_value: string | null;
  reported_value: string | null;
  currency: string;
  acquired_on: string | null;
  acquired_from: string;
  condition: string;
  cataloged_on: string | null;
};
export type Publisher = {
  id: number;
  name: string;
  default_city: string;
  work_count: number;
};
export type Work = {
  publisher_id?: number | null;
  id?: number;
  kind: string;
  title: string;
  subtitle: string;
  year: number | null;
  edition: string;
  language: string;
  pages: string;
  publisher: string;
  city: string;
  journal: string;
  volume: string;
  issue: string;
  url: string;
  accessed: string | null;
  notes: string;
  abnt_reference: string;
  pending: boolean;
  tags: string[];
  subjects: string[];
  ddc: string[];
  ddc_wording: string[];
  lcc: string[];
  series: string[];
  original_title: string;
  original_language: string;
  binding: string;
  publication_statement: string;
  physical_description: string;
  private_notes: string;
  authors: Author[];
  identifiers: { scheme: string; value: string }[];
  items?: Item[];
  documents?: { id: number; name: string; size: number }[];
  cover_url?: string | null;
  candidate_key?: string;
  candidate_index?: number;
};
export function blankWork(): Work {
  return {
    kind: "book",
    title: "",
    subtitle: "",
    year: null,
    edition: "",
    language: "",
    pages: "",
    publisher_id: null,
    publisher: "",
    city: "",
    journal: "",
    volume: "",
    issue: "",
    url: "",
    accessed: null,
    notes: "",
    abnt_reference: "",
    pending: false,
    tags: [],
    subjects: [],
    ddc: [],
    ddc_wording: [],
    lcc: [],
    series: [],
    original_title: "",
    original_language: "",
    binding: "",
    publication_statement: "",
    physical_description: "",
    private_notes: "",
    authors: [],
    identifiers: [],
  };
}
let csrf = "";
export async function request(path: string, method = "GET", body?: unknown) {
  const multipart = body instanceof FormData;
  const response = await fetch("/api" + path, {
    method,
    headers: {
      ...(multipart ? {} : { "Content-Type": "application/json" }),
      "X-CSRFToken": csrf,
    },
    body:
      body === undefined ? undefined : multipart ? body : JSON.stringify(body),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok)
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : "Não foi possível concluir. Confira os campos ou entre novamente.",
    );
  if (data.csrf) csrf = data.csrf;
  return data;
}
// Reads a server-sent events response ("data: {json}\n\n") as it arrives.
export async function* streamEvents(path: string) {
  const response = await fetch("/api" + path, {
    headers: { Accept: "text/event-stream" },
  });
  if (!response.ok || !response.body) {
    const data = await response.json().catch(() => ({}));
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : "Não foi possível concluir a busca.",
    );
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    let cut;
    while ((cut = buffer.indexOf("\n\n")) >= 0) {
      const chunk = buffer.slice(0, cut);
      buffer = buffer.slice(cut + 2);
      if (chunk.startsWith("data: ")) yield JSON.parse(chunk.slice(6));
    }
    if (done) return;
  }
}
