/** Real API E2E tests: run the prepared backend and PostgreSQL before this suite. */
import { test, expect } from "@playwright/test";

test("personalization, evidence, popularity comparison and cold start", async ({
  page,
}) => {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(page.locator(".product-card")).toHaveCount(5);
  await expect(
    page.getByText("Personalized using similar purchase histories"),
  ).toBeVisible();
  await page.getByRole("searchbox").fill("12347");
  await page.getByLabel("Customer", { exact: true }).selectOption("12347");
  await expect(page.locator(".neighbor-list li")).not.toHaveCount(0);
  await page
    .locator(".product-card details")
    .first()
    .locator("summary")
    .click();
  await expect(page.locator(".product-card details[open]")).toContainText(
    "Customer",
  );
  await page.getByLabel("Ranking method").selectOption("popularity");
  await expect(
    page.getByText("Popularity ranking · distinct purchasing customers"),
  ).toBeVisible();
  await expect(page.locator(".product-card")).toHaveCount(5);
  await page.getByLabel("Suggestions").selectOption("10");
  await expect(page.locator(".product-card")).toHaveCount(10);
  await page
    .getByLabel("Customer", { exact: true })
    .selectOption("NEW_CUSTOMER");
  await expect(
    page.getByText("This customer has no recorded purchases.", {
      exact: false,
    }),
  ).toBeVisible();
  await expect(page.locator(".product-card")).toHaveCount(10);
  await expect(
    page.getByRole("heading", { name: "Offline evaluation" }),
  ).toBeVisible();
  await expect(page.locator(".logs-panel tbody tr").first()).toContainText(
    "NEW_CUSTOMER",
  );
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  expect(errors).toEqual([]);
});

test("unavailable API gives an actionable retry state", async ({ page }) => {
  await page.route("**/api/model", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Model temporarily unavailable" }),
    }),
  );
  await page.goto("/");
  await expect(page.getByRole("alert")).toContainText(
    "Model temporarily unavailable",
  );
  await expect(page.getByRole("button", { name: "Try again" })).toBeEnabled();
});

test("a slow previous customer cannot replace current results", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.locator(".product-card")).toHaveCount(5);
  await page.route("**/api/recommend/12347*", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 400));
    await route.continue();
  });
  await page.getByLabel("Suggestions").selectOption("10");
  await page
    .getByLabel("Customer", { exact: true })
    .selectOption("NEW_CUSTOMER");
  await expect(
    page.getByText("Popularity ranking · distinct purchasing customers"),
  ).toBeVisible();
  await expect(page.locator(".product-card")).toHaveCount(10);
  await expect(page.locator(".strategy-line")).toContainText("COLD START");
});
