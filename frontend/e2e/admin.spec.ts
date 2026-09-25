import { test, expect } from "@playwright/test";

test("admin dashboard handles periods, pages, errors and mobile layout", async ({
  page,
}) => {
  let fail = false;
  await page.addInitScript(() =>
    sessionStorage.setItem("convene-session", "browser-admin"),
  );
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    let body: unknown = [];
    if (url.pathname.endsWith("/auth/me"))
      body = { id: "admin", email: "owner@example.com", is_admin: true };
    if (url.pathname.endsWith("/admin/overview")) {
      if (fail)
        return route.fulfill({
          status: 403,
          json: { detail: "Administrator access required" },
        });
      const current = Number(url.searchParams.get("page"));
      body = {
        generated_at: "2026-09-23T12:00:00Z",
        days: Number(url.searchParams.get("days")),
        total_users: 21,
        signups: 2,
        active_users: 1,
        total_conversations: 3,
        submitted_runs: 4,
        run_statuses: { complete: 3, failed: 1 },
        recorded_tokens: 800,
        daily_signups: [{ date: "2026-09-23", count: 2 }],
        users: [
          {
            id: `user-${current}`,
            email: `page${current}@example.com`,
            created: "2026-09-23T12:00:00Z",
            last_active: null,
          },
        ],
        page: current,
        page_size: 20,
      };
    }
    await route.fulfill({ json: body });
  });
  await page.goto("/");
  await page
    .getByRole("button", { name: "Admin dashboard", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Dashboard", exact: true }),
  ).toBeVisible();
  await expect(page.getByText("page1@example.com")).toBeVisible();
  await page.getByRole("button", { name: "Next", exact: true }).click();
  await expect(page.getByText("page2@example.com")).toBeVisible();
  await page.getByLabel("Dashboard period").selectOption("7");
  await expect(page.getByText("page1@example.com")).toBeVisible();
  await expect(page.getByText("Last 7 UTC days")).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: "test-results/admin-mobile.png",
    fullPage: true,
  });
  fail = true;
  await page.getByRole("button", { name: "Refresh", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText(
    "Administrator access required",
  );
  await expect(page.getByText("page1@example.com")).toHaveCount(0);
  fail = false;
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await expect(page.getByText("page1@example.com")).toBeVisible();
  await page.getByRole("button", { name: "Back to workspace" }).click();
  await expect(
    page.getByRole("heading", { name: "What’s on your mind?" }),
  ).toBeVisible();
});

test("ordinary members have no admin navigation", async ({ page }) => {
  await page.addInitScript(() =>
    sessionStorage.setItem("convene-session", "browser-member"),
  );
  await page.route("**/api/**", (route) =>
    route.fulfill({
      json: route.request().url().endsWith("/auth/me")
        ? { id: "member", email: "member@example.com", is_admin: false }
        : [],
    }),
  );
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "What’s on your mind?" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Admin dashboard" }),
  ).toHaveCount(0);
});
