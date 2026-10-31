<script lang="ts">
  import WorkDetails from "$lib/WorkDetails.svelte";
  import PublisherManager from "$lib/PublisherManager.svelte";
  import type { Publisher } from "$lib/api";
  import ThemeToggle from "$lib/ThemeToggle.svelte";
  import { onMount } from "svelte";
  import { blankWork, request, type Work, type Location } from "$lib/api";
  import { bibliography, bibliographyFromForm } from "$lib/citations";
  import ItemFields from "$lib/ItemFields.svelte";
  import type { Item } from "$lib/api";
  let publishers = $state<Publisher[]>([]);
  async function loadPublishers() {
    publishers = await request("/v1/publishers");
  }
  function selectPublisher(value: string) {
    form.publisher = value;
    const found = publishers.find(
      (p) => p.name.toLocaleLowerCase() === value.trim().toLocaleLowerCase(),
    );
    form.publisher_id = found?.id ?? null;
    if (found?.default_city && !form.city.trim())
      form.city = found.default_city;
  }
  let tagFilter = $state(""),
    tagOptions = $state<string[]>([]),
    unlocated = $state(false);
  const listFields: {
    key: "tags" | "subjects" | "ddc" | "ddc_wording" | "lcc" | "series";
    label: string;
  }[] = [
    { key: "tags", label: "Etiquetas pessoais" },
    { key: "subjects", label: "Assuntos bibliográficos" },
    { key: "ddc", label: "CDD — códigos" },
    { key: "ddc_wording", label: "CDD — descrições" },
    { key: "lcc", label: "LCC — códigos" },
    { key: "series", label: "Série / coleção editorial" },
  ];
  async function saveItem(item: Item) {
    await run(async () => {
      const payload = { ...item };
      for (const field of [
        "purchase_price",
        "estimated_value",
        "reported_value",
      ] as const) {
        const value = payload[field]?.trim();
        payload[field] = value
          ? value.includes(",")
            ? value.replaceAll(".", "").replace(",", ".")
            : value
          : null;
      }
      await request("/v1/items/" + item.id, "PUT", payload);
      form.items = (await request("/v1/works/" + form.id)).items;
      notice = "Dados do exemplar salvos.";
    });
  }
  import LocationBrowser from "$lib/LocationBrowser.svelte";
  let locationBrowse = $state<{
    room: string | null;
    bookcase: string | null;
    location: number | null;
    q: string;
    page: number;
  }>({ room: null, bookcase: null, location: null, q: "", page: 1 });
  let fromLocations = $state(false);
  let coverDialog = $state<HTMLDialogElement>();
  let enlargedCover = $state<{ url: string; title: string } | null>(null);
  function showCover(work: Work) {
    if (!work.cover_url) return;
    enlargedCover = { url: work.cover_url, title: work.title };
    coverDialog?.showModal();
  }
  let user = $state<string | null>(null),
    ready = $state(false),
    busy = $state(false),
    username = $state(""),
    password = $state(""),
    error = $state(""),
    notice = $state("");
  let screen = $state("catalog"),
    works = $state<Work[]>([]),
    locations = $state<Location[]>([]),
    count = $state(0),
    totalCount = $state(0),
    page = $state(1),
    q = $state(""),
    kind = $state(""),
    filterLocation = $state(""),
    pending = $state(false);
  let selected = $state<number[]>([]),
    reference = $state(""),
    form = $state<Work>(blankWork()),
    locationId = $state("");
  let candidates = $state<{ source: string; data: Partial<Work> }[]>([]),
    candidateKey = $state(""),
    room = $state(""),
    bookcase = $state(""),
    shelf = $state(""),
    viewer = $state<number | null>(null);
  const fields: {
    key:
      | "subtitle"
      | "edition"
      | "language"
      | "pages"
      | "publisher"
      | "city"
      | "journal"
      | "volume"
      | "issue"
      | "url";
    label: string;
  }[] = [
    { key: "subtitle", label: "Subtítulo" },
    { key: "edition", label: "Edição" },
    { key: "language", label: "Idioma" },
    { key: "pages", label: "Páginas / intervalo" },
    { key: "city", label: "Cidade de publicação" },
    { key: "journal", label: "Periódico (artigos)" },
    { key: "volume", label: "Volume" },
    { key: "issue", label: "Número" },
    { key: "url", label: "URL" },
  ];
  async function run(action: () => Promise<void>) {
    busy = true;
    error = "";
    notice = "";
    try {
      await action();
    } catch (e) {
      error = e instanceof Error ? e.message : "Ocorreu um erro.";
    } finally {
      busy = false;
    }
  }
  async function load() {
    const params = new URLSearchParams({
      q,
      page: String(page),
      kind,
      pending: String(pending),
      unlocated: String(unlocated),
    });
    if (filterLocation) params.set("location", filterLocation);
    if (tagFilter) params.set("tag", tagFilter);
    const data = await request("/v1/works?" + params);
    works = data.results;
    count = data.count;
    totalCount = data.total_count;
    locations = await request("/v1/locations");
    tagOptions = await request("/v1/tags");
    await loadPublishers();
  }
  onMount(() => {
    run(async () => {
      const s = await request("/session");
      user = s.username;
      if (user) await load();
    }).finally(() => (ready = true));
  });
  async function login() {
    await run(async () => {
      const d = await request("/login", "POST", { username, password });
      user = d.username;
      password = "";
      await load();
    });
  }
  function newWork() {
    form = blankWork();
    fromLocations = false;
    screen = "edit";
    candidates = [];
    viewer = null;
    reference = "";
    error = "";
    notice = "";
  }
  async function open(id: number, viaLocations = false) {
    await run(async () => {
      fromLocations = viaLocations;
      form = await request("/v1/works/" + id);
      screen = "details";
      viewer = null;
      reference = "";
      candidates = [];
    });
  }
  async function search(identifier: { scheme: string; value: string }) {
    if (busy || !identifier.value.trim()) return;
    const { scheme, value } = identifier;
    await run(async () => {
      candidates = [];
      candidateKey = "";
      const r = await request(
        "/v1/lookup?" +
          new URLSearchParams({
            scheme,
            value: value.trim(),
            enrich: String(Boolean(form.id)),
          }),
      );
      if (r.existing_id) {
        form = await request("/v1/works/" + r.existing_id);
        notice = "Já está no catálogo. Adicione outra cópia se necessário.";
        candidates = [];
        return;
      }
      candidates = r.candidates;
      candidateKey = r.key || "";
      notice =
        r.warnings.join(" ") ||
        (candidates.length
          ? "Confira e escolha o resultado."
          : "Nenhum resultado. Complete a ficha ou salve como pendente.");
      if (!form.id && !candidates.length) {
        form.pending = true;
        if (!form.title) form.title = "Cadastro pendente — " + value;
      }
    });
  }
  function choose(index: number) {
    const candidate = candidates[index];
    if (form.id) {
      const merged = { ...form } as Record<string, unknown>;
      for (const [key, value] of Object.entries(candidate.data)) {
        if (
          !merged[key] ||
          (Array.isArray(merged[key]) && !(merged[key] as unknown[]).length)
        )
          merged[key] = value;
      }
      form = merged as Work;
    } else form = { ...blankWork(), ...candidate.data };
    selectPublisher(form.publisher);
    form.candidate_key = candidateKey;
    form.candidate_index = index;
    notice = "Confira a edição e os autores antes de salvar.";
  }
  async function regenerateReference() {
    await run(async () => {
      form.abnt_reference = await bibliographyFromForm(form);
      notice =
        "Referência gerada com os dados do formulário. Salve o cadastro para gravá-la.";
    });
  }
  async function save(next = false) {
    await run(async () => {
      const created = !form.id;
      if (created && !form.abnt_reference.trim())
        form.abnt_reference = await bibliographyFromForm(form);
      const data = await request(
        "/v1/works" + (form.id ? "/" + form.id : ""),
        form.id ? "PUT" : "POST",
        form,
      );
      form.id = data.id;
      await loadPublishers();
      if (created && locationId)
        await request(`/v1/works/${data.id}/items`, "POST", {
          location_id: Number(locationId),
          notes: "",
        });
      if (next) {
        newWork();
        notice = "Salvo. Pronto para o próximo livro.";
        setTimeout(() => document.getElementById("add-isbn")?.focus(), 0);
      } else {
        form = await request("/v1/works/" + data.id);
        screen = "details";
        reference = "";
        notice = "Cadastro salvo.";
      }
    });
  }
  async function addCopy() {
    await run(async () => {
      await request(`/v1/works/${form.id}/items`, "POST", {
        location_id: Number(locationId),
        notes: "",
      });
      form = await request("/v1/works/" + form.id);
      notice = "Exemplar adicionado.";
    });
  }
  async function upload(event: Event) {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    await run(async () => {
      const data = new FormData();
      data.append("file", file);
      await request(`/v1/works/${form.id}/pdfs`, "POST", data);
      form = await request("/v1/works/" + form.id);
      notice = "PDF disponível.";
    });
    input.value = "";
  }
  async function uploadCover(event: Event) {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    await run(async () => {
      if (file.size > 10 * 1024 * 1024)
        throw new Error("A capa deve ter no máximo 10 MB.");
      const data = new FormData();
      data.append("file", file);
      await request(`/v1/works/${form.id}/cover`, "POST", data);
      form.cover_url = (await request("/v1/works/" + form.id)).cover_url;
      notice = "Capa otimizada e salva. O original não foi armazenado.";
    });
    input.value = "";
  }
  async function refs(ids: number[]) {
    await run(async () => {
      reference = await bibliography(ids);
      try {
        await navigator.clipboard.writeText(reference);
        notice = "Referência copiada.";
      } catch {
        notice = "Selecione e copie a referência abaixo.";
      }
    });
  }
</script>

<svelte:head><title>Aleph · Minha biblioteca</title></svelte:head>
<div class="shell">
  <header class="header">
    <a class="brand-link" href="/" aria-label="Aleph — página inicial">
      <img src="/aleph-icon.png" width="52" height="52" alt="" />
      <div>
        <span class="brand">Aleph</span>
        <div class="muted brand-caption">Sua biblioteca, no lugar certo.</div>
      </div>
    </a>
    <div class="actions header-actions">
      <ThemeToggle />
      {#if user}<nav class="actions" aria-label="Navegação">
          <button
            class="secondary"
            onclick={() =>
              run(async () => {
                screen = "catalog";
                reference = "";
                await load();
              })}>Catálogo</button
          ><button
            class="secondary"
            onclick={() =>
              run(async () => {
                locations = await request("/v1/locations");
                screen = "locations";
              })}>Localizações</button
          ><button
            class="secondary"
            onclick={() =>
              run(async () => {
                await loadPublishers();
                screen = "publishers";
                reference = "";
              })}>Editoras</button
          ><button
            class="secondary"
            onclick={() =>
              run(async () => {
                await request("/logout", "POST");
                user = null;
                works = [];
                form = blankWork();
                viewer = null;
                reference = "";
                selected = [];
              })}>Sair · {user}</button
          >
        </nav>{/if}
    </div>
  </header>
  {#if error}<div class="alert" role="alert">{error}</div>{/if}{#if notice}<div
      class="alert success"
      role="status"
    >
      {notice}
    </div>{/if}
  {#if !ready}<p>Carregando biblioteca…</p>{:else if !user}
    <main class="login-layout">
      <div class="login-art">
        <img
          class="login-logo"
          src="/aleph-logo.png"
          alt="Aleph — Biblioteca pessoal"
          width="880"
          height="1024"
        />
      </div>
      <section class="login card">
        <small>ACERVO PESSOAL</small>
        <h1>Entre na sua biblioteca.</h1>
        <p class="muted">Livros, artigos e arquivos, reunidos em um lugar.</p>
        <form
          class="grid"
          onsubmit={(e) => {
            e.preventDefault();
            login();
          }}
        >
          <label class="wide"
            >Usuário<input
              autocomplete="username"
              bind:value={username}
              required
            /></label
          ><label class="wide"
            >Senha<input
              type="password"
              autocomplete="current-password"
              bind:value={password}
              required
            /></label
          ><button class="wide" disabled={busy}>Entrar</button>
        </form>
      </section>
    </main>
  {:else if screen === "catalog"}
    <main>
      <div class="row">
        <div>
          <small>MEU ACERVO</small>
          <div class="library-heading">
            <h1>Minha biblioteca</h1>
            <span class="library-count" aria-label="Total de cadastros no acervo">{totalCount.toLocaleString("pt-BR")} cadastros</span>
          </div>
          <p class="muted">
            {count} registros · livros, artigos e leituras digitais
          </p>
        </div>
        <button onclick={newWork}>+ Cadastrar livro ou artigo</button>
      </div>
      <form
        class="toolbar"
        onsubmit={(e) => {
          e.preventDefault();
          page = 1;
          run(load);
        }}
      >
        <input
          aria-label="Buscar no acervo"
          placeholder="Título, autor, ISBN, DOI ou editora"
          bind:value={q}
        /><select aria-label="Tipo" bind:value={kind}
          ><option value="">Todos os tipos</option><option value="book"
            >Livros</option
          ><option value="article-journal">Artigos</option></select
        ><select aria-label="Localização" bind:value={filterLocation}
          ><option value="">Todas as localizações</option
          >{#each locations as l}<option value={l.id}
              >{[l.room, l.bookcase, l.shelf]
                .filter(Boolean)
                .join(" / ")}</option
            >{/each}</select
        ><button disabled={busy}>Buscar</button><label
          style="flex-direction:row;align-items:center"
          ><input type="checkbox" bind:checked={pending} /> Apenas pendentes</label
        >
      </form>
      <div class="actions" style="margin-bottom:1rem">
        <label
          >Filtrar por etiqueta<select
            bind:value={tagFilter}
            onchange={() => {
              page = 1;
              run(load);
            }}
            ><option value="">Todas as etiquetas</option
            >{#each tagOptions as tag}<option value={tag}>{tag}</option
              >{/each}</select
          ></label
        >
        <label style="flex-direction:row;align-items:center"
          ><input
            type="checkbox"
            bind:checked={unlocated}
            onchange={() => {
              page = 1;
              filterLocation = "";
              run(load);
            }}
          /> Exemplares sem localização</label
        >
      </div>
      {#if selected.length}<div class="actions" style="margin-bottom:1rem">
          <button disabled={busy} onclick={() => refs(selected)}
            >Copiar bibliografia ({selected.length})</button
          ><button class="secondary" onclick={() => (selected = [])}
            >Limpar seleção</button
          >
        </div>{/if}
      {#if !works.length}<div class="card">
          <h2>{q ? "Nenhum resultado" : "Sua próxima leitura começa aqui"}</h2>
          <p class="muted">
            Cadastre pelo ISBN ou DOI. Você também pode preencher os dados
            manualmente.
          </p>
        </div>{/if}
      {#each works as work}<article class="card row">
          <div class="actions" style="align-items:flex-start">
            {#if work.cover_url}<button
                class="cover-button"
                aria-label={"Ampliar capa de " + work.title}
                onclick={() => showCover(work)}
                ><img
                  src={work.cover_url}
                  alt={"Capa de " + work.title}
                  width="72"
                  height="108"
                  loading="lazy"
                  class="cover-thumb"
                /></button
              >{/if}
            <input
              aria-label={"Selecionar " + work.title}
              type="checkbox"
              checked={selected.includes(work.id!)}
              onchange={(e) =>
                (selected = e.currentTarget.checked
                  ? [...selected, work.id!]
                  : selected.filter((id) => id !== work.id))}
            />
            <div>
              <div class="actions">
                <span class="tag"
                  >{work.kind === "book" ? "Livro" : "Artigo"}</span
                >{#if work.pending}<span class="tag">Pendente</span>{/if}
              </div>
              <button
                class="book-title"
                style="margin:.6rem 0"
                onclick={() => open(work.id!)}>{work.title}</button
              >
              <div class="muted">
                {work.authors.map((a) => a.name).join("; ") ||
                  "Autoria não informada"} · {work.year || "Sem data"}
              </div>
              <div class="actions">
                {#each work.tags ?? [] as tag}<button
                    class="secondary"
                    style="padding:.2rem .5rem;font-size:.8rem"
                    onclick={() => {
                      tagFilter = tag;
                      page = 1;
                      run(load);
                    }}>{tag}</button
                  >{/each}
              </div>
              <small
                >{work.publisher}
                {work.items?.length
                  ? " · " + work.items.map((i) => i.location).join("; ")
                  : ""}</small
              >
            </div>
          </div>
          <span class="tag">{work.documents?.length || 0} PDFs</span>
        </article>{/each}
      <div class="actions">
        <button
          class="secondary"
          disabled={page === 1 || busy}
          onclick={() => {
            page--;
            run(load);
          }}>Anterior</button
        ><span>Página {page}</span><button
          class="secondary"
          disabled={page * 30 >= count || busy}
          onclick={() => {
            page++;
            run(load);
          }}>Próxima</button
        >
      </div>
    </main>
  {:else if screen === "details"}
    {#key form.id}
      <WorkDetails
        work={form}
        onCover={showCover}
        onEdit={() => {
          screen = "edit";
          reference = "";
        }}
        backLabel={fromLocations
          ? "← Voltar à localização"
          : "← Voltar ao catálogo"}
        onBack={() =>
          run(async () => {
            if (fromLocations) {
              locations = await request("/v1/locations");
              screen = "locations";
            } else {
              await load();
              screen = "catalog";
            }
            reference = "";
            notice = "";
          })}
      />
    {/key}
  {:else if screen === "publishers"}
    <PublisherManager {publishers} onChanged={loadPublishers} />
  {:else if screen === "locations"}
    <main>
      <small>ORGANIZAÇÃO DO ACERVO</small>
      <h1>Onde estão seus livros?</h1>
      <LocationBrowser
        {locations}
        bind:selection={locationBrowse}
        onOpen={(id) => open(id, true)}
        onCover={showCover}
      />
      <h2>Cadastrar localização</h2>
      <form
        class="card grid"
        onsubmit={(e) => {
          e.preventDefault();
          run(async () => {
            await request("/v1/locations", "POST", { room, bookcase, shelf });
            locations = await request("/v1/locations");
            notice = "Localização salva.";
          });
        }}
      >
        <label
          >Ambiente<input
            bind:value={room}
            placeholder="Escritório"
            required
          /></label
        ><label
          >Estante<input
            bind:value={bookcase}
            placeholder="Estante 03"
          /></label
        ><label
          >Prateleira<input
            bind:value={shelf}
            placeholder="Prateleira 02"
          /></label
        >
        <div class="actions">
          <button disabled={busy}>Adicionar localização</button>
        </div>
      </form>
    </main>
  {:else}
    <main>
      {#if fromLocations}<button
          class="secondary"
          style="margin-bottom:1rem"
          onclick={() =>
            run(async () => {
              locations = await request("/v1/locations");
              screen = "locations";
            })}>← Voltar à localização</button
        >{/if}
      {#if form.id}<button
          class="secondary"
          style="margin-bottom:1rem"
          disabled={busy}
          onclick={() => open(form.id!, fromLocations)}
          >Cancelar edição e voltar aos detalhes</button
        >{/if}
      <small>{form.id ? "EDITAR CADASTRO" : "CADASTRO RÁPIDO"}</small>
      <h1>{form.id ? form.title : "Adicione uma nova leitura"}</h1>
      <form
        onsubmit={(e) => {
          e.preventDefault();
          save();
        }}
      >
        <section class="card" aria-labelledby="identifier-heading">
          <h2 id="identifier-heading">ISBN e DOI</h2>
          <p class="muted">
            Confira, digite ou escaneie o código. Use Buscar dados para
            consultar as fontes bibliográficas; os resultados aparecem abaixo.
          </p>
          {#if !form.identifiers.some((identifier) => identifier.scheme === "isbn")}
            <p>Nenhum ISBN cadastrado.</p>
          {/if}
          {#each form.identifiers as identifier, index}
            <div
              class="actions"
              style="margin-bottom:.8rem;align-items:flex-end"
            >
              <label
                >Tipo de identificador
                <select bind:value={identifier.scheme}>
                  <option value="isbn">ISBN</option><option value="doi"
                    >DOI</option
                  >
                </select>
              </label>
              <label style="flex:1;min-width:200px"
                >{identifier.scheme.toUpperCase()}
                <input
                  bind:value={identifier.value}
                  onkeydown={(event) => {
                    if (event.key === "Enter") {
                      event.preventDefault();
                      search(identifier);
                    }
                  }}
                  maxlength="300"
                  required
                  placeholder={identifier.scheme === "isbn"
                    ? "ISBN de 10 ou 13 caracteres"
                    : "10.…/…"}
                />
              </label>
              <button
                type="button"
                class="secondary"
                aria-label={"Remover " + identifier.scheme.toUpperCase()}
                onclick={() => form.identifiers.splice(index, 1)}
                >Remover</button
              >
              <button
                type="button"
                class="secondary"
                disabled={busy || !identifier.value.trim()}
                aria-label={"Buscar dados por " +
                  identifier.scheme.toUpperCase()}
                onclick={() => search(identifier)}
                >{busy ? "Aguarde…" : "Buscar dados"}</button
              >
            </div>
          {/each}
          <div class="actions">
            <button
              type="button"
              class="secondary"
              id="add-isbn"
              onclick={() =>
                form.identifiers.push({ scheme: "isbn", value: "" })}
              >+ ISBN</button
            >
            <button
              type="button"
              class="secondary"
              onclick={() =>
                form.identifiers.push({ scheme: "doi", value: "" })}
              >+ DOI</button
            >
          </div>
          {#each candidates as candidate, index}<div
              class="card"
              style="margin-top:1rem"
            >
              <span class="tag">{candidate.source}</span>
              <h2>{candidate.data.title}</h2>
              <p>{candidate.data.authors?.map((a) => a.name).join("; ")}</p>
              <p class="muted">
                {candidate.data.publisher} · {candidate.data.year} · {candidate
                  .data.edition} · {candidate.data.pages}
              </p>
              <button
                type="button"
                class="secondary"
                onclick={() => choose(index)}
                >{form.id
                  ? "Preencher campos vazios"
                  : "Usar esta ficha"}</button
              >
            </div>{/each}
        </section>
        <section class="card">
          <h2>Dados bibliográficos</h2>
          <div class="grid">
            <label
              >Tipo<select bind:value={form.kind}
                ><option value="book">Livro</option><option
                  value="article-journal">Artigo</option
                ></select
              ></label
            ><label
              >Ano<input
                type="number"
                min="1"
                max="9999"
                value={form.year ?? ""}
                oninput={(e) =>
                  (form.year = e.currentTarget.value
                    ? Number(e.currentTarget.value)
                    : null)}
              /></label
            ><label class="wide"
              >Título<input
                bind:value={form.title}
                required
                maxlength="1000"
              /></label
            ><label
              >Editora
              <input
                aria-label="Editora"
                list="publisher-options"
                value={form.publisher}
                maxlength="300"
                oninput={(e) => selectPublisher(e.currentTarget.value)}
              />
              <datalist id="publisher-options"
                >{#each publishers as publisher}<option value={publisher.name}
                    >{publisher.default_city}</option
                  >{/each}</datalist
              >
              <small
                >Selecione uma editora cadastrada ou digite um novo nome. A
                cidade padrão preenche apenas uma cidade vazia.</small
              >
            </label>{#each fields as field}<label
                >{field.label}<input bind:value={form[field.key]} /></label
              >{/each}<label
              >Data de acesso<input
                type="date"
                value={form.accessed ?? ""}
                oninput={(e) => (form.accessed = e.currentTarget.value || null)}
              /></label
            ><label class="wide"
              >Observações<textarea bind:value={form.notes}></textarea></label
            ><label style="flex-direction:row"
              ><input type="checkbox" bind:checked={form.pending} /> Cadastro pendente
              de revisão</label
            >
          </div>
        </section>
        <section class="card">
          <h2>Referência ABNT</h2>
          <label
            >Referência ABNT salva<textarea
              bind:value={form.abnt_reference}
              maxlength="20000"></textarea></label
          >
          <p class="muted">
            Texto editável. Gerar novamente substitui este texto usando os dados
            atuais do formulário. Salve o cadastro para gravar a referência
            junto com as demais alterações.
          </p>
          <button
            type="button"
            class="secondary"
            disabled={busy || !form.title.trim()}
            onclick={regenerateReference}>Gerar novamente</button
          >
        </section>
        <section class="card">
          <h2>Assuntos e informações complementares</h2>
          <p class="muted">
            Nas listas abaixo, informe um valor por linha. Etiquetas pessoais e
            assuntos importados permanecem separados.
          </p>
          <div class="grid">
            {#each listFields as field}<label
                >{field.label}<textarea
                  value={(form[field.key] ?? []).join("\n")}
                  onchange={(e) =>
                    (form[field.key] = e.currentTarget.value
                      .split("\n")
                      .map((v) => v.trim())
                      .filter(Boolean))}></textarea></label
              >{/each}
            <label
              >Título original<input bind:value={form.original_title} /></label
            >
            <label
              >Idioma original<input
                bind:value={form.original_language}
              /></label
            >
            <label
              >Formato / encadernação<input bind:value={form.binding} /></label
            >
            <label
              >Descrição física<input
                bind:value={form.physical_description}
              /></label
            >
            <label
              >Publicação original (texto completo)<textarea
                bind:value={form.publication_statement}></textarea></label
            >
            <label
              >Notas privadas originais<textarea bind:value={form.private_notes}
              ></textarea></label
            >
          </div>
        </section>
        <section class="card">
          <h2>Autores e responsáveis</h2>
          <p class="muted">
            A ordem será usada na referência. Confira prenomes e sobrenome para
            formatar a ABNT.
          </p>
          {#each form.authors as author, index}<div class="author">
              <label
                >Nome completo<input bind:value={author.name} required /></label
              ><label>Prenomes<input bind:value={author.given} /></label><label
                >Sobrenome<input bind:value={author.family} /></label
              ><label
                >Papel<select bind:value={author.role}
                  ><option value="author">Autor</option><option value="editor"
                    >Organizador</option
                  ><option value="translator">Tradutor</option
                  >{#if !["author", "editor", "translator"].includes(author.role)}<option
                      value={author.role}>{author.role}</option
                    >{/if}</select
                ></label
              ><button
                type="button"
                class="secondary"
                onclick={() => form.authors.splice(index, 1)}>Remover</button
              >
            </div>{/each}<button
            type="button"
            class="secondary"
            onclick={() =>
              form.authors.push({
                name: "",
                given: "",
                family: "",
                role: "author",
              })}>+ Autor ou responsável</button
          >
        </section>
        <section class="card">
          <h2>Exemplares físicos</h2>
          <label
            >Localização para o próximo exemplar<select bind:value={locationId}
              ><option value="">Sem exemplar físico / selecionar depois</option
              >{#each locations as l}<option value={l.id}
                  >{[l.room, l.bookcase, l.shelf]
                    .filter(Boolean)
                    .join(" / ")}</option
                >{/each}</select
            ></label
          >{#if !locations.length}<p class="muted">
              Cadastre as localizações no menu antes de iniciar uma prateleira.
            </p>{/if}{#if form.id}<button
              type="button"
              style="margin-top:1rem"
              disabled={!locationId || busy}
              onclick={addCopy}>Adicionar exemplar aqui</button
            >{/if}{#each form.items ?? [] as item}<div
              class="card"
              style="margin-top:1rem"
            >
              <strong>{item.location}</strong>
              <p><small>Código interno: {item.code}</small></p>
              <ItemFields {item} {locations} {busy} onSave={saveItem} />
              <div class="actions">
                <button
                  type="button"
                  class="secondary"
                  disabled={!locationId || busy}
                  onclick={() =>
                    run(async () => {
                      await request("/v1/items/" + item.id, "PUT", {
                        location_id: Number(locationId),
                        notes: item.notes,
                      });
                      form = await request("/v1/works/" + form.id);
                    })}>Mover para localização selecionada</button
                ><button
                  type="button"
                  class="secondary"
                  onclick={() => {
                    if (confirm("Remover este exemplar?"))
                      run(async () => {
                        await request("/v1/items/" + item.id, "DELETE");
                        form = await request("/v1/works/" + form.id);
                      });
                  }}>Remover exemplar</button
                >
              </div>
            </div>{/each}
        </section>
        <div class="actions">
          <button disabled={busy}>Salvar cadastro</button>{#if !form.id}<button
              type="button"
              disabled={busy || !form.title.trim()}
              onclick={() => save(true)}>Salvar e cadastrar próximo</button
            >{:else}<button type="button" class="secondary" onclick={newWork}
              >Próximo livro</button
            >{/if}
        </div>
      </form>
      <section class="card" style="margin-top:1.5rem">
        <h2>Capa</h2>
        <p class="muted">
          JPEG ou PNG, até 10 MB e 20 megapixels. Salvamos somente a versão
          otimizada em WebP, 600 × 900 pixels, sem cortar ou deformar a imagem.
        </p>
        {#if form.cover_url}<img
            src={form.cover_url}
            alt={"Capa de " + form.title}
            width="180"
            height="270"
            class="cover-preview"
          />{/if}
        {#if form.id}
          <label
            >Enviar ou substituir capa<input
              type="file"
              accept="image/jpeg,image/png,.jpg,.jpeg,.png"
              onchange={uploadCover}
              disabled={busy}
            /></label
          >
          {#if form.cover_url}<button
              class="secondary"
              style="margin-top:1rem"
              disabled={busy}
              onclick={() => {
                if (confirm("Remover a capa deste cadastro?"))
                  run(async () => {
                    await request(`/v1/works/${form.id}/cover`, "DELETE");
                    form.cover_url = null;
                    notice = "Capa removida.";
                  });
              }}>Remover capa</button
            >{/if}
        {:else}<p class="muted">Salve o cadastro para enviar uma capa.</p>{/if}
      </section>
      <section class="card" style="margin-top:1.5rem">
        <h2>Arquivos PDF</h2>
        {#if form.id}<label
            >Enviar PDF (até 100 MB)<input
              type="file"
              accept="application/pdf,.pdf"
              disabled={busy}
              onchange={upload}
            /></label
          >{#each form.documents ?? [] as doc}<div
              class="row"
              style="margin-top:1rem"
            >
              <span
                >{doc.name}
                <small>({(doc.size / 1024 / 1024).toFixed(1)} MB)</small></span
              >
              <div class="actions">
                <button
                  class="secondary"
                  onclick={() => (viewer = viewer === doc.id ? null : doc.id)}
                  >Ler</button
                ><a
                  class="button secondary"
                  href={"/api/pdfs/" + doc.id + "?download=1"}>Baixar</a
                >
              </div>
            </div>{/each}{:else}<p class="muted">
            Salve o cadastro para anexar PDFs.
          </p>{/if}{#if viewer}<iframe
            title="Leitor de PDF"
            src={"/api/pdfs/" + viewer}
          ></iframe>
          <p>
            <a href={"/api/pdfs/" + viewer} target="_blank" rel="noreferrer"
              >Abrir leitor em outra aba</a
            >
          </p>{/if}
      </section>
    </main>
  {/if}
  {#if reference}<section class="card" style="margin-top:1rem">
      <h2>Referências ABNT</h2>
      <p class="muted">
        Confira os dados antes de usar. Campos ausentes podem resultar em
        referências incompletas.
      </p>
      <textarea
        aria-label="Referências para copiar"
        readonly
        value={reference}
        style="min-height:180px"></textarea>
    </section>{/if}
</div>
<dialog
  bind:this={coverDialog}
  class="cover-modal"
  aria-label="Capa ampliada"
  onclose={() => (enlargedCover = null)}
  onclick={(event) => {
    if (event.target === event.currentTarget) coverDialog?.close();
  }}
  onkeydown={(event) => {
    if (event.key === "Escape") coverDialog?.close();
  }}
>
  <div class="cover-modal-content">
    <button
      class="secondary cover-modal-close"
      onclick={() => coverDialog?.close()}>Fechar capa</button
    >
    {#if enlargedCover}
      <img
        src={enlargedCover.url}
        alt={"Capa ampliada de " + enlargedCover.title}
      />
      <p>{enlargedCover.title}</p>
    {/if}
  </div>
</dialog>

<style>
  .library-heading { display: flex; align-items: center; flex-wrap: wrap; gap: 0.75rem; }
  .library-count { font-size: 0.9rem; font-weight: 600; border: 1px solid currentColor; border-radius: 999px; padding: 0.25rem 0.65rem; }
</style>
