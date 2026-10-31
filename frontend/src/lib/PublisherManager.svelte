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
  let selected = $state<number[]>([]);
  let targetId = $state(0);
  let merging = $state(false);
  const selectedPublishers = $derived(
    publishers.filter((p) => selected.includes(p.id)),
  );
  const target = $derived(selectedPublishers.find((p) => p.id === targetId));
  const source = $derived(selectedPublishers.find((p) => p.id !== targetId));
  function toggle(publisherId: number) {
    selected = selected.includes(publisherId)
      ? selected.filter((n) => n !== publisherId)
      : [...selected, publisherId];
    merging = false;
  }
  async function merge() {
    if (!target || !source || selected.length !== 2) return;
    busy = true;
    error = "";
    notice = "";
    try {
      const result = await request(
        `/v1/publishers/${target.id}/merge/${source.id}`,
        "POST",
        {},
      );
      selected = [];
      merging = false;
      id = null;
      name = "";
      city = "";
      await onChanged();
      notice = `Editoras fundidas. ${result.moved} cadastros transferidos.`;
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      busy = false;
    }
  }
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
  <div class="actions" style="margin:1rem 0">
    <span>{selected.length} editoras selecionadas</span>
    <button
      class="secondary"
      disabled={busy || selected.length !== 2}
      onclick={() => {
        targetId = selected[0];
        merging = true;
      }}>Fundir editoras</button
    >
    {#if selected.length}<button
        class="secondary"
        disabled={busy}
        onclick={() => {
          selected = [];
          merging = false;
        }}>Limpar seleção</button
      >{/if}
  </div>
  {#if merging}
    <section class="card" aria-label="Confirmar fusão de editoras">
      <h2>Fundir editoras</h2>
      <label
        >Editora que será mantida<select bind:value={targetId} disabled={busy}>
          {#each selectedPublishers as publisher}<option value={publisher.id}
              >{publisher.name} — {publisher.default_city ||
                "sem cidade"}</option
            >{/each}
        </select></label
      >
      {#if source && target}
        <p>
          Transferir os {source.work_count} livros/artigos de
          <strong>{source.name}</strong>
          para <strong>{target.name}</strong> e apagar
          <strong>{source.name}</strong>.
        </p>
        <p class="muted">
          A cidade padrão da editora mantida será usada nos novos cadastros. As
          cidades dos livros e as referências ABNT já salvas serão preservadas;
          você pode gerar novamente a referência na edição de cada livro.
        </p>
      {/if}
      <div class="actions">
        <button disabled={busy || !source || !target} onclick={merge}
          >Confirmar fusão e apagar editora incorporada</button
        ><button
          class="secondary"
          disabled={busy}
          onclick={() => (merging = false)}>Cancelar fusão</button
        >
      </div>
    </section>
  {/if}
  {#each pageRows as publisher}
    <article class="card row">
      <div>
        <label
          ><input
            type="checkbox"
            checked={selected.includes(publisher.id)}
            disabled={busy ||
              (!selected.includes(publisher.id) && selected.length >= 2)}
            onchange={() => toggle(publisher.id)}
            aria-label={"Selecionar " + publisher.name}
          /> Selecionar</label
        >
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
