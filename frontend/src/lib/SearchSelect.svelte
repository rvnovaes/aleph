<script lang="ts">
  // Text field with a filtered option list. Single choice (`value`) or several
  // (`values` with `multiple`). With `oncreate`, typed text that matches no
  // option can be registered on the spot.
  type Option = { value: string; label: string };
  let {
    options,
    value = $bindable(""),
    values = $bindable([]),
    multiple = false,
    placeholder = "",
    ariaLabel = undefined,
    emptyLabel = "",
    id = undefined,
    onchange = () => {},
    oncreate = undefined,
  }: {
    options: Option[];
    value?: string;
    values?: string[];
    multiple?: boolean;
    placeholder?: string;
    ariaLabel?: string;
    emptyLabel?: string;
    id?: string;
    onchange?: () => void;
    oncreate?: (text: string) => Promise<string | null>;
  } = $props();

  const uid = "ss-" + Math.random().toString(36).slice(2, 9);
  let text = $state("");
  let open = $state(false);
  let typing = $state(false);
  let active = $state(0);
  let input = $state<HTMLInputElement>();

  const fold = (s: string) =>
    s
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "")
      .toLowerCase();
  const labelOf = (v: string) => options.find((o) => o.value === v)?.label ?? v;

  let shown = $derived.by(() => {
    const words = fold(typing ? text : "")
      .split(/\s+/)
      .filter(Boolean);
    return options.filter(
      (o) =>
        !(multiple && values.includes(o.value)) &&
        words.every((w) => fold(o.label).includes(w)),
    );
  });
  let canCreate = $derived(
    !!oncreate &&
      typing &&
      text.trim() !== "" &&
      !options.some((o) => fold(o.label) === fold(text.trim())),
  );
  // Rows: optional "clear" row, matching options, optional "create" row.
  let rows = $derived([
    ...(!multiple && emptyLabel && !typing
      ? [{ kind: "clear" as const, value: "", label: emptyLabel }]
      : []),
    ...shown.slice(0, 200).map((o) => ({ kind: "option" as const, ...o })),
    ...(canCreate
      ? [
          {
            kind: "create" as const,
            value: "",
            label: `+ Cadastrar “${text.trim()}”`,
          },
        ]
      : []),
  ]);
  let display = $derived(
    typing || multiple ? text : value ? labelOf(value) : "",
  );

  function close() {
    open = false;
    typing = false;
    text = "";
  }
  async function pick(row: (typeof rows)[number]) {
    let chosen = row.value;
    if (row.kind === "create") {
      const created = await oncreate!(text.trim());
      if (created === null) return;
      chosen = created;
    }
    if (multiple) {
      if (chosen && !values.includes(chosen)) values = [...values, chosen];
      text = "";
      typing = false;
      active = 0;
      input?.focus();
    } else {
      value = chosen;
      close();
    }
    onchange();
  }
  function remove(v: string) {
    values = values.filter((x) => x !== v);
    onchange();
  }
  function keydown(e: KeyboardEvent) {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      open = true;
      const step = e.key === "ArrowDown" ? 1 : -1;
      active = (active + step + rows.length) % Math.max(rows.length, 1);
    } else if (e.key === "Enter") {
      if (!open || !rows.length) return;
      e.preventDefault();
      pick(rows[Math.min(active, rows.length - 1)]);
    } else if (e.key === "Escape") {
      if (open) {
        e.preventDefault();
        close();
      }
    } else if (
      e.key === "Backspace" &&
      multiple &&
      !text &&
      values.length
    ) {
      remove(values[values.length - 1]);
    }
  }
</script>

<div class="search-select" class:multiple>
  <!-- Input first, so a wrapping <label> names it (not a chip button). -->
  <input
    bind:this={input}
    {id}
    role="combobox"
    aria-label={ariaLabel}
    aria-expanded={open}
    aria-controls={uid}
    aria-autocomplete="list"
    aria-activedescendant={open && rows.length
      ? `${uid}-${Math.min(active, rows.length - 1)}`
      : undefined}
    autocomplete="off"
    placeholder={multiple && values.length ? "" : placeholder}
    value={display}
    oninput={(e) => {
      text = e.currentTarget.value;
      typing = true;
      open = true;
      active = 0;
    }}
    onfocus={(e) => {
      open = true;
      active = 0;
      if (!multiple) e.currentTarget.select();
    }}
    onblur={() => setTimeout(close, 150)}
    onkeydown={keydown}
  />
  {#if multiple}
    {#each values as v}<span class="chip"
        >{labelOf(v)}<button
          type="button"
          aria-label={"Remover " + labelOf(v)}
          onclick={() => remove(v)}>×</button
        ></span
      >{/each}
  {/if}
  {#if open && rows.length}
    <ul id={uid} role="listbox">
      {#each rows as row, i}
        <li
          id={`${uid}-${i}`}
          role="option"
          aria-selected={i === active}
          class:active={i === active}
          class:create={row.kind === "create"}
          onmousedown={(e) => {
            e.preventDefault();
            pick(row);
          }}
          onmousemove={() => (active = i)}
        >
          {row.label}
        </li>
      {/each}
    </ul>
  {/if}
</div>

<style>
  .search-select {
    position: relative;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.3rem;
    min-width: 220px;
  }
  .search-select.multiple {
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 0.25rem 0.4rem;
    background: var(--surface);
  }
  .search-select input {
    order: 1;
    flex: 1;
    min-width: 8rem;
  }
  .search-select.multiple input {
    border: 0;
    background: transparent;
    padding: 0.35rem 0.2rem;
    outline: none;
  }
  .chip {
    display: inline-flex;
    align-items: center;
    gap: 0.2rem;
    padding: 0.15rem 0.2rem 0.15rem 0.55rem;
    border-radius: 999px;
    background: var(--bg);
    border: 1px solid var(--border);
    font-size: 0.85rem;
  }
  .chip button {
    padding: 0 0.35rem;
    background: transparent;
    color: inherit;
    border: 0;
    line-height: 1.2;
  }
  ul {
    position: absolute;
    top: calc(100% + 4px);
    left: 0;
    right: 0;
    z-index: 20;
    max-height: 16rem;
    overflow-y: auto;
    margin: 0;
    padding: 0.25rem;
    list-style: none;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    box-shadow: 0 8px 24px rgb(0 0 0 / 18%);
  }
  li {
    padding: 0.4rem 0.6rem;
    border-radius: 6px;
    cursor: pointer;
  }
  li.active {
    background: var(--bg);
    outline: 1px solid var(--accent);
  }
  li.create {
    color: var(--accent);
    font-weight: 600;
  }
</style>
