<script lang="ts">
  import "../style.css";
  import { updated } from "$app/state";
  let { children } = $props();
</script>

{#if updated.current}
  <aside class="update-notice" role="status">
    <span
      >Uma nova versão do Aleph está disponível. Salve suas alterações antes de
      atualizar.</span
    >
    <button onclick={() => window.location.reload()}
      >Atualizar aplicativo</button
    >
  </aside>
{/if}
{@render children()}
