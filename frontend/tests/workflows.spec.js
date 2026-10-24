import { test, expect } from "@playwright/test";

// These browser tests use the running API and real saved artifacts, not fake metrics.
test("analysis and both model profiles show real evaluation", async ({
  page,
  request,
}) => {
  const report = await (
    await request.get("/api/v1/profiles/banksim/evaluation")
  ).json();
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Understand the evidence." }),
  ).toBeVisible();
  await expect(page.getByLabel("Inspect model")).toHaveValue(
    report.selected_model,
  );
  await expect(
    page.getByText("All model comparisons", { exact: true }),
  ).toBeVisible();
  await expect(page.locator(".metric").first()).toContainText(
    (report.models[report.selected_model].test.accuracy * 100).toFixed(2),
  );
  await page.getByLabel("Dataset profile").selectOption("credit_card");
  await expect(
    page.getByText("ULB research benchmark", { exact: false }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Model evaluation", exact: true }),
  ).toBeVisible();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download full report" }).click();
  expect((await download).suggestedFilename()).toContain(
    "credit_card-evaluation.json",
  );
});
test("payment scoring persists, review survives reload, and replay runs", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: /Live demo/ }).click();
  await page
    .getByRole("button", { name: "Load labelled fraud example" })
    .click();
  await page
    .getByRole("button", { name: "Score transaction", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Prediction result" }),
  ).toBeVisible();
  await expect(
    page.getByText("earlier payments in the previous 7 days.", {
      exact: false,
    }),
  ).toBeVisible();
  await page.getByRole("button", { name: /Analyst review/ }).click();
  await page.getByRole("button", { name: "open", exact: true }).first().click();
  await page.getByLabel("Review notes").fill("Browser-tested investigation.");
  await page.getByLabel("Review state").selectOption("under_review");
  await page.getByRole("button", { name: "Save review", exact: true }).click();
  await page.getByLabel("Review filter").selectOption("under_review");
  await expect(
    page.getByRole("button", { name: "under review", exact: true }).first(),
  ).toBeVisible();
  await page.reload();
  await page.getByRole("button", { name: /Analyst review/ }).click();
  await page.getByLabel("Review filter").selectOption("under_review");
  await expect(
    page.getByRole("button", { name: "under review", exact: true }).first(),
  ).toBeVisible();
  await page.getByRole("button", { name: /Live demo/ }).click();
  await page.getByRole("button", { name: "Play replay", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Pause replay", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Prediction result" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Pause replay", exact: true }).click();
});
test("labelled CSV scoring and real service health", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Transaction CSV").setInputFiles({
    name: "analysis.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(
      "step,customer,merchant,category,amount,fraud\n1,Ctest,Mtest,es_food,10,0\n2,Ctest,Mtest,es_travel,200,1\n",
    ),
  });
  await page.getByRole("button", { name: "Score CSV", exact: true }).click();
  await expect(page.getByText("2 rows scored", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Your uploaded data", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: /Service health/ }).click();
  await expect(page.getByText("Ready", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Observed traffic" }),
  ).toBeVisible();
});
test("API failures have readable UI feedback", async ({ page }) => {
  await page.route("**/api/v1/profiles/banksim/evaluation", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({
        detail: "Evaluation unavailable for browser failure test.",
      }),
    }),
  );
  await page.goto("/");
  await expect(page.getByRole("alert")).toContainText(
    "Evaluation unavailable for browser failure test.",
  );
  await expect(
    page.getByRole("heading", { name: "Evaluation unavailable", exact: true }),
  ).toBeVisible();
});
test("mobile layout retains controls without page overflow", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(page.getByLabel("Dataset profile")).toBeVisible();
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > innerWidth,
  );
  expect(overflow).toBe(false);
  await page.getByRole("button", { name: /Live demo/ }).click();
  await expect(
    page.getByRole("heading", { name: "Score a payment" }),
  ).toBeVisible();
});

test("credit-card demo scores the original 30 signals", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Dataset profile").selectOption("credit_card");
  await page.getByRole("button", { name: /Live demo/ }).click();
  await page
    .getByRole("button", { name: "Load labelled fraud example" })
    .click();
  await expect(page.getByLabel("V28", { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "Score transaction", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Prediction result" }),
  ).toBeVisible();
  await expect(
    page.getByText(
      "PCA components have no published business interpretation.",
      { exact: true },
    ),
  ).toBeVisible();
});

test("manual scoring and Auto show the actual recorded candidate", async ({
  page,
  request,
}) => {
  // Read the frozen decision so a future run can legitimately promote routing.
  const report = await (
    await request.get("/api/v1/profiles/banksim/evaluation")
  ).json();
  await page.goto("/");
  await page.getByRole("button", { name: /Live demo/ }).click();
  await page
    .getByLabel("Prediction model", { exact: true })
    .selectOption("random_forest");
  await page
    .getByRole("button", { name: "Load labelled fraud example" })
    .click();
  await page
    .getByRole("button", { name: "Score transaction", exact: true })
    .click();
  await expect(page.getByLabel("Model decision")).toContainText(
    "random_forest · requested random_forest",
  );
  await page
    .getByLabel("Prediction model", { exact: true })
    .selectOption("auto");
  const response = page.waitForResponse(
    (result) =>
      result.url().endsWith("/banksim/predictions") &&
      result.request().method() === "POST",
  );
  await page
    .getByRole("button", { name: "Score transaction", exact: true })
    .click();
  const result = await (await response).json();
  expect(result.requested_model).toBe("auto");
  expect(result.routing_status).toBe(
    report.auto_policy.router_promoted ? "routed" : "fallback",
  );
  await expect(page.getByLabel("Model decision")).toContainText(
    "requested auto",
  );
  await page.getByRole("button", { name: /Analyst review/ }).click();
  await expect(page.locator("tbody tr").first()).toContainText(
    `${result.used_model} · Auto`,
  );
});

test("CSV model selection reaches the API and downloadable results", async ({
  page,
}) => {
  await page.goto("/");
  await page
    .getByLabel("CSV prediction model")
    .selectOption("logistic_regression");
  await page
    .getByLabel("Transaction CSV")
    .setInputFiles({
      name: "choices.csv",
      mimeType: "text/csv",
      buffer: Buffer.from(
        "step,customer,merchant,category,amount,fraud\n1,Cchoice,M1,es_food,10,0\n2,Cchoice,M2,es_travel,200,1\n",
      ),
    });
  const response = page.waitForResponse((result) =>
    result.url().endsWith("/banksim/batch-predictions"),
  );
  await page.getByRole("button", { name: "Score CSV", exact: true }).click();
  const result = await (await response).json();
  expect(result.requested_model).toBe("logistic_regression");
  expect(result.used_models).toEqual({ logistic_regression: 2 });
  await expect(
    page.getByText("Models used: logistic_regression: 2", { exact: true }),
  ).toBeVisible();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download scored results" }).click();
  expect((await download).suggestedFilename()).toContain(
    "banksim-batch-results.json",
  );
});
