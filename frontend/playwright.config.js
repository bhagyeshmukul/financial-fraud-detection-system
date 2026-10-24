/** Exercise a running app in Chromium and preserve failure screenshots/traces. */
import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  // One worker avoids competing with ML serving on the laptop.
  workers: 1,
  timeout: 60000,
  expect: { timeout: 15000 },
  use: {
    baseURL: process.env.WEB_URL || "http://127.0.0.1:5173",
    headless: true,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  reporter: [
    ["list"],
    ["json", { outputFile: "../artifacts/browser-tests.json" }],
  ],
});
