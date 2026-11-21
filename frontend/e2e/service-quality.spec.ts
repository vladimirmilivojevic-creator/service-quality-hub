import { expect, test } from "@playwright/test";
import { loginAs, resetDemo } from "./helpers";

test.beforeEach(async ({ request }) => {
  await resetDemo(request);
});

test("login page shows the demo accounts and the API status", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByTestId("api-status")).toHaveText("API online");
  await expect(page.getByRole("button", { name: /Log in as/ })).toHaveCount(4);
  await expect(page.getByText("fictional company")).toBeVisible();
});

test("dashboard shows KPIs, plants and open tickets", async ({ page }) => {
  await loginAs(page, "Service Quality Manager");
  await expect(page.getByTestId("kpi-sla_resolution")).toBeVisible();
  await expect(page.getByTestId("kpi-change_success")).toBeVisible();
  await expect(page.getByTestId("plant-table").locator("tr")).toHaveCount(5);
  await page.getByTestId("filter-month").selectOption("2026-10");
  await expect(page.getByTestId("kpi-value-change_success")).toHaveText("90.0 %");
  await expect(page.getByTestId("kpi-change_success").locator("[data-rag]").first()).toHaveAttribute(
    "data-rag",
    "amber",
  );
});

test("an IT manager follows the main story: red supplier, problem candidate, monthly review", async ({ page }) => {
  await loginAs(page, "Service Quality Manager");

  await page.getByRole("link", { name: "Suppliers" }).click();
  const alpnet = page.getByTestId("scorecard-table").locator("tr", { hasText: "AlpNet Carrier" });
  await expect(alpnet.locator("[data-rag]")).toHaveAttribute("data-rag", "red");
  await alpnet.getByRole("link", { name: "AlpNet Carrier" }).click();
  await expect(page.getByRole("heading", { name: "AlpNet Carrier" })).toBeVisible();
  await page.getByTestId("add-improvement").click();
  await page.getByTestId("improvement-title").fill("Escalation drill with AlpNet");
  await page.getByTestId("improvement-save").click();
  await expect(page.getByText("Escalation drill with AlpNet")).toBeVisible();

  await page.getByRole("link", { name: "Problems" }).click();
  const candidates = page.getByTestId("candidate");
  await expect(candidates.first()).toBeVisible();
  const before = await candidates.count();
  expect(before).toBeGreaterThan(0);
  await candidates.first().getByTestId("create-problem").click();
  await expect(candidates).toHaveCount(before - 1);
  await expect(page.getByTestId("problem-table")).toContainText("Recurring");

  await page.getByRole("link", { name: "Dashboard" }).click();
  await page.getByTestId("generate-report").click();
  await expect(page.getByRole("heading", { name: "Monthly service review – October 2026" })).toBeVisible();
  await expect(page.getByTestId("next-actions")).toContainText("Service review with AlpNet Carrier");
  const download = page.waitForEvent("download");
  await page.getByTestId("download-excel").click();
  expect((await download).suggestedFilename()).toBe("service-review-2026-10.xlsx");
});

test("simulate next day moves the demo clock", async ({ page }) => {
  await loginAs(page, "IT Management");
  await expect(page.getByTestId("demo-clock")).toContainText("18 Nov 2026");
  await page.getByTestId("simulate").click();
  await expect(page.getByTestId("simulation-result")).toContainText("new tickets");
  await expect(page.getByTestId("demo-clock")).toContainText("19 Nov 2026");
});

test("JSM CSV import: preview, import, skipped rows", async ({ page }) => {
  await loginAs(page, "Service Quality Manager");
  await page.getByRole("link", { name: "Import" }).click();
  await page.getByTestId("use-sample").click();
  await page.getByTestId("preview").click();
  await expect(page.getByTestId("preview-table").locator("tr")).toHaveCount(20);
  await expect(page.getByTestId("skipped-rows")).toContainText("no plant found");
  await page.getByTestId("import").click();
  await expect(page.getByTestId("import-result")).toContainText("24 created");
});

test("roles: read-only management and a supplier that sees only its scorecard", async ({ page }) => {
  await loginAs(page, "IT Management");
  await expect(page.getByRole("link", { name: "Import" })).toHaveCount(0);
  await page.getByRole("button", { name: "Log out" }).click();

  await loginAs(page, "Supplier – AlpNet");
  await expect(page.getByRole("heading", { name: "AlpNet Carrier" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Dashboard" })).toHaveCount(0);
});

test("how it works is public and explains the rules", async ({ page }) => {
  await page.goto("/how-it-works");
  await expect(page.getByTestId("priority-matrix").locator("tr")).toHaveCount(3);
  await expect(page.getByTestId("kpi-formulas")).toContainText("Change success rate");
  await expect(page.getByTestId("itil-map")).toContainText("Change enablement");
});
