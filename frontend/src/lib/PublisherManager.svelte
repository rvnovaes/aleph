<script lang="ts">
  import { request, type Publisher } from "./api";
  let {
    publishers,
    onChanged,
  }: { publishers: Publisher[]; onChanged: () => Promise<void> } = $props();
  let query = $state("");
  let page = $state(1);
  const pageSize = 20;
  let id = $state<number | null>(null);
  let name = $state("");
  let city = $state("");
  let busy = $state(false);
  let error = $state("");
  let notice = $state("");
  const visible = $derived(
    publishers.filter((p) =>
      (p.name + " " + p.default_city)
        .toLocaleLowerCase()
        .includes(query.toLocaleLowerCase()),
    ),
  );
  const pageCount = $derived(Math.max(1, Math.ceil(visible.length / pageSize)));
  const currentPage = $derived(Math.min(page, pageCount));
  const pageRows = $derived(
    visible.slice((currentPage - 1) * pageSize, currentPage * pageSize),
  );
  function edit(p?: Publisher) {
    id = p?.id ?? null;
    name = p?.name ?? "";
    city = p?.default_city ?? "";
    error = "";
    notice = "";
    document.getElementById("publisher-name")?.focus();
  }
  async function save(event: SubmitEvent) {
    event.preventDefault();
    busy = true;
    error = "";
    notice = "";
    try {
      await request(
        "/v1/publishers" + (id ? "/" + id : ""),
        id ? "PUT" : "POST",
        { name, default_city: city },
      );
      await onChanged();
      id = null;
      name = "";
      city = "";
      notice =
        "Editora salva. As cidades dos livros existentes foram preservadas.";
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      busy = false;
    }
  }
</script>

{#snippet pagination(label: string)}
  <nav class="actions" aria-label={label} style="margin:1rem 0">
    <button
      type="button"
      class="secondary"
      disabled={currentPage === 1}
      onclick={() => (page = currentPage - 1)}>Anterior</button
    >
    <span aria-live="polite">Página {currentPage} de {pageCount}</span>
    <button
      type="button"
      class="secondary"
      disabled={currentPage === pageCount}
      onclick={() => (page = currentPage + 1)}>Próxima</button
    >
  </nav>
{/snippet}

<main>
  <h1>Editoras</h1>
  <p class="muted">
    Cadastre a cidade padrão para novos livros. Cada edição mantém sua própria
    cidade de publicação.
  </p>
  {#if error}<div class="alert" role="alert">{error}</div>{/if}
  {#if notice}<div class="alert success" role="status">{notice}</div>{/if}
  <form class="card grid" onsubmit={save}>
    <h2 class="wide">{id ? "Editar editora" : "Nova editora"}</h2>
    <label
      >Nome da editora<input
        id="publisher-name"
        bind:value={name}
        maxlength="300"
        required
      /></label
    >
    <label
      >Cidade padrão<input
        bind:value={city}
        maxlength="300"
        placeholder="Ex.: São Paulo"
      /></label
    >
    <div class="wide actions">
      <button disabled={busy}
        >{id ? "Salvar editora" : "Cadastrar editora"}</button
      >
      {#if id}<button
          type="button"
          class="secondary"
          onclick={() => edit()}
          disabled={busy}>Cancelar edição</button
        >{/if}
    </div>
  </form>
  <label
    >Buscar editora ou cidade<input
      type="search"
      bind:value={query}
      oninput={() => (page = 1)}
    /></label
  >
  <p class="muted" role="status">
    {#if visible.length}
      Mostrando {(currentPage - 1) * pageSize + 1}–{Math.min(
        currentPage * pageSize,
        visible.length,
      )} de {visible.length} editoras
    {:else}Nenhuma editora encontrada.{/if}
  </p>
  {#if visible.length}{@render pagination("Paginação de editoras")}{/if}
  {#each pageRows as publisher}
    <article class="card row">
      <div>
        <strong>{publisher.name}</strong>
        <div class="muted">
          {publisher.default_city || "Cidade padrão não definida"} · {publisher.work_count}
          livros/artigos
        </div>
      </div>
      <button
        class="secondary"
        onclick={() => edit(publisher)}
        disabled={busy}
        aria-label={"Editar " + publisher.name}>Editar</button
      >
    </article>
  {/each}
  {#if visible.length}{@render pagination(
      "Paginação de editoras no rodapé",
    )}{/if}
</main>
