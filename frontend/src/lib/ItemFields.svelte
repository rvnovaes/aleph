<script lang="ts">
  import type { Item, Location } from "./api";
  let {
    item,
    locations,
    busy,
    onSave,
  }: {
    item: Item;
    locations: Location[];
    busy: boolean;
    onSave: (item: Item) => void;
  } = $props();
</script>

<details style="margin:1rem 0">
  <summary
    >Dados do exemplar e valores em R$ {item.reported_value
      ? "· valor informado: R$ " + item.reported_value.replace(".", ",")
      : ""}</summary
  >
  <div class="grid" style="margin-top:1rem">
    <label
      >Localização do exemplar<select
        value={item.location_id ?? ""}
        onchange={(e) =>
          (item.location_id = e.currentTarget.value
            ? Number(e.currentTarget.value)
            : null)}
        ><option value="">Localização não informada</option
        >{#each locations as place}<option value={place.id}
            >{[place.room, place.bookcase, place.shelf]
              .filter(Boolean)
              .join(" / ")}</option
          >{/each}</select
      ></label
    >
    <label
      >Código de barras antigo<input bind:value={item.legacy_barcode} /></label
    >
    <label
      >Preço de compra (R$)<input
        inputmode="decimal"
        placeholder="0,00"
        value={item.purchase_price ?? ""}
        oninput={(e) => (item.purchase_price = e.currentTarget.value || null)}
      /></label
    >
    <label
      >Valor estimado (R$)<input
        inputmode="decimal"
        placeholder="0,00"
        value={item.estimated_value ?? ""}
        oninput={(e) => (item.estimated_value = e.currentTarget.value || null)}
      /></label
    >
    <label
      >Valor informado na origem (R$)<input
        inputmode="decimal"
        placeholder="0,00"
        value={item.reported_value ?? ""}
        oninput={(e) => (item.reported_value = e.currentTarget.value || null)}
      /></label
    >
    <label
      >Data de aquisição<input
        type="date"
        value={item.acquired_on ?? ""}
        oninput={(e) => (item.acquired_on = e.currentTarget.value || null)}
      /></label
    >
    <label>Onde adquiriu<input bind:value={item.acquired_from} /></label>
    <label>Estado de conservação<input bind:value={item.condition} /></label>
    <label
      >Data do cadastro original<input
        type="date"
        value={item.cataloged_on ?? ""}
        oninput={(e) => (item.cataloged_on = e.currentTarget.value || null)}
      /></label
    >
    <label>Notas do exemplar<textarea bind:value={item.notes}></textarea></label
    >
  </div>
  <p class="muted">
    Valor informado preserva o preço genérico do catálogo antigo, sem presumir
    compra ou avaliação.
  </p>
  <button type="button" disabled={busy} onclick={() => onSave(item)}
    >Salvar dados do exemplar</button
  >
</details>
