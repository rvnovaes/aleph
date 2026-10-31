<script lang="ts">
  import { request, type Location, type Work } from "./api";
  type Selection = {
    room: string | null;
    bookcase: string | null;
    location: number | null;
    q: string;
    page: number;
  };
  let {
    locations,
    selection = $bindable(),
    onOpen,
    onCover,
  }: {
    locations: Location[];
    selection: Selection;
    onOpen: (id: number) => void;
    onCover: (work: Work) => void;
  } = $props();
  let works = $state<Work[]>([]),
    count = $state(0),
    loading = $state(false),
    error = $state("");
  let search = $state(selection.q);
  const roomPlaces = $derived(
    locations.filter((l) => l.room === selection.room),
  );
  const shelfPlaces = $derived(
    roomPlaces.filter((l) => l.bookcase === selection.bookcase),
  );
  const rooms = $derived([...new Set(locations.map((l) => l.room))]);
  const bookcases = $derived([...new Set(roomPlaces.map((l) => l.bookcase))]);
  const current = $derived(locations.find((l) => l.id === selection.location));
  function navigate(
    room: string | null,
    bookcase: string | null = null,
    location: number | null = null,
  ) {
    selection = { room, bookcase, location, q: "", page: 1 };
    search = "";
  }
  function copies(places: Location[]) {
    return places.reduce((n, l) => n + l.item_count, 0);
  }
  $effect(() => {
    const state = { ...selection };
    // Counts changing after adding/moving an item also refresh the visible records.
    const revision = locations;
    void revision;
    let cancelled = false;
    works = [];
    count = 0;
    error = "";
    if (state.room === null) {
      loading = false;
      return;
    }
    loading = true;
    const params = new URLSearchParams({
      room: state.room,
      q: state.q,
      page: String(state.page),
    });
    if (state.bookcase !== null) params.set("bookcase", state.bookcase);
    if (state.location !== null) params.set("location", String(state.location));
    request("/v1/works?" + params)
      .then((data) => {
        if (!cancelled) {
          works = data.results;
          count = data.count;
        }
      })
      .catch((e) => {
        if (!cancelled) error = e.message;
      })
      .finally(() => {
        if (!cancelled) loading = false;
      });
    return () => {
      cancelled = true;
    };
  });
</script>

<section aria-label="Navegador por localização">
  <h2>Explorar por localização</h2>
  <nav class="actions location-breadcrumb" aria-label="Caminho da localização">
    <button class="secondary" onclick={() => navigate(null)}
      >Todos os ambientes</button
    >
    {#if selection.room !== null}<span aria-hidden="true">›</span><button
        class="secondary"
        onclick={() => navigate(selection.room)}>{selection.room}</button
      >{/if}
    {#if selection.bookcase !== null}<span aria-hidden="true">›</span><button
        class="secondary"
        onclick={() => navigate(selection.room, selection.bookcase)}
        >{selection.bookcase || "Sem estante"}</button
      >{/if}
    {#if current}<span aria-hidden="true">›</span><span aria-current="page"
        >{current.shelf || "Sem prateleira"}</span
      >{/if}
  </nav>
  <div class="location-grid">
    {#if selection.room === null}
      {#each rooms as name}<button
          class="location-tile"
          onclick={() => navigate(name)}
          ><strong>{name}</strong><small
            >{copies(locations.filter((l) => l.room === name))} exemplares</small
          ><span>Explorar ambiente →</span></button
        >{/each}
    {:else if selection.bookcase === null}
      {#each bookcases as name}<button
          class="location-tile"
          onclick={() => navigate(selection.room, name)}
          ><strong>{name || "Sem estante"}</strong><small
            >{copies(roomPlaces.filter((l) => l.bookcase === name))} exemplares</small
          ><span>Explorar estante →</span></button
        >{/each}
    {:else if selection.location === null}
      {#each shelfPlaces as place}<button
          class="location-tile"
          onclick={() => navigate(selection.room, selection.bookcase, place.id)}
          ><strong>{place.shelf || "Sem prateleira"}</strong><small
            >{place.work_count} títulos · {place.item_count} exemplares</small
          ><span>Ver livros →</span></button
        >{/each}
    {/if}
  </div>
  {#if !locations.length}<p class="muted">
      Cadastre sua primeira localização abaixo para organizar o acervo.
    </p>
  {:else if selection.room === null}<p class="muted">
      Escolha um ambiente para ver os livros e navegar pelas estantes e
      prateleiras.
    </p>
  {:else}
    <h2>Livros nesta localização</h2>
    <form
      class="actions"
      onsubmit={(e) => {
        e.preventDefault();
        selection = { ...selection, q: search, page: 1 };
      }}
    >
      <input
        aria-label="Buscar nesta localização"
        placeholder="Título, autor, ISBN ou editora"
        bind:value={search}
        style="flex:1;min-width:180px"
      /><button disabled={loading}>Buscar nesta localização</button>
    </form>
    {#if error}<p class="alert" role="alert">{error}</p>{/if}
    {#if loading}<p role="status">Carregando livros…</p>{:else}<p class="muted">
        {count} títulos encontrados
      </p>
      {#if !works.length}<div class="card">
          {selection.q
            ? "Nenhum título corresponde à busca nesta localização."
            : "Ainda não há livros nesta localização. Associe um exemplar a ela na ficha do livro."}
        </div>{/if}
      {#each works as work}<article class="card row">
          <div class="actions" style="align-items:flex-start">
            {#if work.cover_url}<button
                class="cover-button"
                aria-label={"Ampliar capa de " + work.title}
                onclick={() => onCover(work)}
                ><img
                  class="cover-thumb"
                  src={work.cover_url}
                  alt={"Capa de " + work.title}
                  width="120"
                  height="180"
                  loading="lazy"
                /></button
              >{/if}
            <div>
              <button class="book-title" onclick={() => onOpen(work.id!)}
                >{work.title}</button
              >
              <p class="muted">
                {work.authors.map((a) => a.name).join("; ") ||
                  "Autoria não informada"} · {work.year || "Sem data"}
              </p>
              <small
                >{work.items
                  ?.filter((i) =>
                    selection.location !== null
                      ? i.location_id === selection.location
                      : shelfPlaces.length && selection.bookcase !== null
                        ? shelfPlaces.some((l) => l.id === i.location_id)
                        : roomPlaces.some((l) => l.id === i.location_id),
                  )
                  .map((i) => i.location)
                  .join(" · ")}</small
              >
            </div>
          </div>
        </article>{/each}
      <div class="actions">
        <button
          class="secondary"
          disabled={selection.page <= 1}
          onclick={() =>
            (selection = { ...selection, page: selection.page - 1 })}
          >Anterior</button
        ><span>Página {selection.page}</span><button
          class="secondary"
          disabled={selection.page * 30 >= count}
          onclick={() =>
            (selection = { ...selection, page: selection.page + 1 })}
          >Próxima</button
        >
      </div>
    {/if}
  {/if}
</section>
