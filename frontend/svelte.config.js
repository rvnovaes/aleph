import adapter from "@sveltejs/adapter-static";
export default {
  kit: {
    version: { pollInterval: 30000 },
    adapter: adapter({ fallback: "index.html" }),
  },
};
