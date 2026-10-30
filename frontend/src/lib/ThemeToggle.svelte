<script lang="ts">
  import { onMount } from "svelte";
  let dark = $state(false);
  onMount(() => {
    dark = document.documentElement.dataset.theme === "dark";
    const media = matchMedia("(prefers-color-scheme: dark)");
    const followSystem = () => {
      try {
        if (localStorage.getItem("aleph-theme")) return;
      } catch {}
      dark = media.matches;
      document.documentElement.dataset.theme = dark ? "dark" : "light";
    };
    media.addEventListener("change", followSystem);
    return () => media.removeEventListener("change", followSystem);
  });
  function toggle() {
    dark = !dark;
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    try {
      localStorage.setItem("aleph-theme", dark ? "dark" : "light");
    } catch {}
  }
</script>

<button
  class="secondary theme-toggle"
  onclick={toggle}
  aria-label={dark ? "Ativar modo claro" : "Ativar modo escuro"}
  title={dark ? "Ativar modo claro" : "Ativar modo escuro"}
>
  <span aria-hidden="true">{dark ? "☀" : "☾"}</span>
  {dark ? "Modo claro" : "Modo escuro"}
</button>
