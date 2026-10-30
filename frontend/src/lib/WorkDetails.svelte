<script lang="ts">
  import type { Work } from "./api";
  let {
    work,
    onEdit,
    onBack,
    onCover,
    backLabel,
  }: {
    work: Work;
    onEdit: () => void;
    onBack: () => void;
    onCover: (work: Work) => void;
    backLabel: string;
  } = $props();
  const reference = $derived(work.abnt_reference || "");
  let referenceError = $state("");
  let copied = $state(false);
  let viewer = $state<number | null>(null);
  async function copyReference() {
    try {
      await navigator.clipboard.writeText(reference);
      copied = true;
    } catch {
      referenceError =
        "Não foi possível copiar automaticamente. Selecione o texto abaixo e copie.";
    }
  }
  const roles: Record<string, string> = {
    author: "Autor",
    editor: "Organizador",
    translator: "Tradutor",
    illustrator: "Ilustrador",
    introduction: "Introdução",
    foreword: "Prefácio",
    afterword: "Posfácio",
    contributor: "Colaborador",
    cartographer: "Cartógrafo",
    adapter: "Adaptador",
  };
  const metadata = $derived([
    ["Editora", work.publisher],
    ["Cidade de publicação", work.city],
    ["Ano", work.year],
    ["Edição", work.edition],
    ["Idioma", work.language],
    ["Páginas", work.pages],
    ["Periódico", work.journal],
    ["Volume", work.volume],
    ["Número", work.issue],
    ["Título original", work.original_title],
    ["Idioma original", work.original_language],
    ["Formato", work.binding],
    ["Descrição física", work.physical_description],
    ["Publicação original", work.publication_statement],
    ["Data de acesso", date(work.accessed)],
  ]);
  const lists = $derived([
    ["Etiquetas pessoais", work.tags],
    ["Assuntos", work.subjects],
    ["CDD", work.ddc],
    ["Descrição CDD", work.ddc_wording],
    ["LCC", work.lcc],
    ["Séries", work.series],
  ] as [string, string[]][]);
  function date(value: string | null | undefined) {
    return value ? value.split("-").reverse().join("/") : "";
  }
  function money(value: string | null, currency: string) {
    return value === null
      ? ""
      : new Intl.NumberFormat("pt-BR", { style: "currency", currency }).format(
          Number(value),
        );
  }
</script>

<main>
  <div class="row" style="margin-bottom:1.5rem">
    <button class="secondary" onclick={onBack}>{backLabel}</button>
    <button onclick={onEdit}>Editar</button>
  </div>
  <p class="muted">Detalhes do {work.kind === "book" ? "livro" : "artigo"}</p>
  <section class="card detail-heading">
    {#if work.cover_url}
      <button
        class="cover-button"
        onclick={() => onCover(work)}
        aria-label={"Ampliar capa de " + work.title}
      >
        <img
          class="cover-preview"
          src={work.cover_url}
          alt={"Capa de " + work.title}
          width="180"
          height="270"
        />
      </button>
    {/if}
    <div>
      <span class="tag">{work.kind === "book" ? "Livro" : "Artigo"}</span>
      {#if work.pending}<span class="tag">Pendente de revisão</span>{/if}
      <h1>{work.title}</h1>
      {#if work.subtitle}<p>{work.subtitle}</p>{/if}
      {#each work.authors as author}<p>
          {author.name} <small>· {roles[author.role] || author.role}</small>
        </p>{/each}
      {#if !work.authors.length}<p class="muted">Autoria não informada.</p>{/if}
    </div>
  </section>

  <section class="card">
    <h2>Dados bibliográficos</h2>
    <dl class="detail-grid">
      {#each metadata as [label, value]}{#if value}<div>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>{/if}{/each}
      {#each work.identifiers as identifier}<div>
          <dt>{identifier.scheme.toUpperCase()}</dt>
          <dd>{identifier.value}</dd>
        </div>{/each}
      {#if work.url}<div>
          <dt>Endereço eletrônico</dt>
          <dd>
            <a href={work.url} target="_blank" rel="noreferrer">{work.url}</a>
          </dd>
        </div>{/if}
    </dl>
    {#each lists as [label, values]}
      {#if values?.length}<h3>{label}</h3>
        <div class="actions">
          {#each values as value}<span class="tag">{value}</span>{/each}
        </div>{/if}
    {/each}
    {#if work.notes}<h3>Observações</h3>
      <p class="detail-text">{work.notes}</p>{/if}
    {#if work.private_notes}<h3>Notas privadas</h3>
      <p class="detail-text">{work.private_notes}</p>{/if}
  </section>

  <section class="card">
    <h2>Referência ABNT</h2>
    <p class="muted">
      Referência salva no cadastro. Use Editar para corrigir o texto ou gerar
      novamente com os dados da edição.
    </p>
    {#if reference}
      <textarea
        aria-label="Referência ABNT para copiar"
        readonly
        value={reference}></textarea>
      <button
        class="secondary"
        onclick={copyReference}
        style="margin-top:.75rem">Copiar referência</button
      >
      {#if copied}<span role="status"> Referência copiada.</span>{/if}
    {:else if !referenceError}<p role="status">
        Nenhuma referência salva. Use Editar para gerar ou digitar a referência.
      </p>{/if}
    {#if referenceError}<p class="alert" role="alert">{referenceError}</p>{/if}
  </section>

  <section class="card">
    <h2>Exemplares e localizações</h2>
    {#each work.items ?? [] as item}
      <article class="card">
        <h3>{item.location || "Localização não informada"}</h3>
        <dl class="detail-grid">
          <div>
            <dt>Código do exemplar</dt>
            <dd>{item.code}</dd>
          </div>
          {#if item.legacy_barcode}<div>
              <dt>Código antigo</dt>
              <dd>{item.legacy_barcode}</dd>
            </div>{/if}
          {#if item.purchase_price !== null}<div>
              <dt>Preço de compra</dt>
              <dd>{money(item.purchase_price, item.currency)}</dd>
            </div>{/if}
          {#if item.estimated_value !== null}<div>
              <dt>Valor estimado</dt>
              <dd>{money(item.estimated_value, item.currency)}</dd>
            </div>{/if}
          {#if item.reported_value !== null}<div>
              <dt>Valor informado</dt>
              <dd>{money(item.reported_value, item.currency)}</dd>
            </div>{/if}
          {#if item.acquired_on}<div>
              <dt>Data de aquisição</dt>
              <dd>{date(item.acquired_on)}</dd>
            </div>{/if}
          {#if item.acquired_from}<div>
              <dt>Adquirido de</dt>
              <dd>{item.acquired_from}</dd>
            </div>{/if}
          {#if item.condition}<div>
              <dt>Conservação</dt>
              <dd>{item.condition}</dd>
            </div>{/if}
          {#if item.cataloged_on}<div>
              <dt>Data de catalogação</dt>
              <dd>{date(item.cataloged_on)}</dd>
            </div>{/if}
        </dl>
        {#if item.notes}<p class="detail-text">{item.notes}</p>{/if}
      </article>
    {:else}<p class="muted">Nenhum exemplar cadastrado.</p>{/each}
  </section>
  <section class="card">
    <h2>Arquivos PDF</h2>
    {#each work.documents ?? [] as doc}
      <div class="row" style="margin:1rem 0">
        <span
          >{doc.name}
          <small>({(doc.size / 1024 / 1024).toFixed(1)} MB)</small></span
        >
        <div class="actions">
          <button
            class="secondary"
            onclick={() => (viewer = viewer === doc.id ? null : doc.id)}
            >{viewer === doc.id ? "Fechar leitor" : "Ler"}</button
          >
          <a
            class="button secondary"
            href={"/api/pdfs/" + doc.id + "?download=1"}>Baixar</a
          >
        </div>
      </div>
    {:else}<p class="muted">Nenhum PDF anexado.</p>{/each}
    {#if viewer}<iframe title="Leitor de PDF" src={"/api/pdfs/" + viewer}
      ></iframe>
      <a href={"/api/pdfs/" + viewer} target="_blank" rel="noreferrer"
        >Abrir leitor em outra aba</a
      >{/if}
  </section>
</main>
