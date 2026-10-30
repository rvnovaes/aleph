import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests/browser",
  workers: 1,
  use: {
    baseURL: process.env.ALEPH_URL || "http://127.0.0.1:8088",
    headless: true,
    launchOptions: {
      executablePath:
        process.env.PLAYWRIGHT_EXECUTABLE_PATH || "/usr/bin/google-chrome",
      args: ["--no-sandbox"],
    },
  },
});
