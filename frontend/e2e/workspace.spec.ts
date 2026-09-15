import { test, expect } from "@playwright/test";
const password = "convene-test-password";
test("sign in, configure models, ask, inspect evidence, reload and export", async ({
  page,
}) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Welcome back." }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Create an account", exact: true })
    .click();
  await page.getByLabel("Email address").fill("preview@example.com");
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "What’s on your mind?" }),
  ).toBeVisible();
  await page.screenshot({
    path: "../docs/convene-desktop.png",
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Council settings", exact: true })
    .click();
  const model = page.getByRole("checkbox", { name: /Nemotron 3.5 Lightning/ });
  await expect(model).toBeChecked();
  await page.getByRole("button", { name: "Done", exact: true }).click();
  await page.getByLabel("Answer approach").selectOption("council");
  await page
    .getByLabel("Your question")
    .fill("Compare two ways to explain triangles.");
  await page.getByRole("button", { name: "Send question" }).click();
  await expect(page.getByText("Saved", { exact: true })).toBeVisible({
    timeout: 20000,
  });
  await page.getByRole("tab", { name: /evidence/i }).click();
  await expect(page.getByText("supported", { exact: true })).toBeVisible();
  await page.getByRole("tab", { name: /perspectives/i }).click();
  await expect(page.getByText(/100% ranking agreement/)).toBeVisible();
  await page.getByRole("tab", { name: "answer", exact: true }).click();
  await page
    .getByRole("button", { name: "Helpful answer", exact: true })
    .click();
  const exported = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export conversation" }).click();
  expect((await exported).suggestedFilename()).toBe("convene-conversation.md");
  await page.screenshot({ path: "../docs/convene-answer.png", fullPage: true });
  await page.reload();
  await page
    .getByRole("navigation", { name: "Conversations" })
    .getByRole("button", {
      name: "Compare two ways to explain triangles.",
      exact: true,
    })
    .click();
  await expect(page.getByText("Saved", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Welcome back." }),
  ).toBeVisible();
});
test("mobile layout keeps navigation and composer accessible", async ({
  page,
  request,
}) => {
  const registration = await request.post(
    "http://127.0.0.1:8001/api/auth/register",
    { data: { email: `mobile-${Date.now()}@example.com`, password } },
  );
  const { token } = await registration.json();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.addInitScript(
    (t) => sessionStorage.setItem("convene-session", t),
    token,
  );
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "What’s on your mind?" }),
  ).toBeVisible();
  await expect(page.getByLabel("Your question")).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({ path: "../docs/convene-mobile.png", fullPage: true });
  await page.getByRole("button", { name: "Open navigation" }).click();
  await expect(
    page.getByRole("button", { name: "Council settings", exact: true }),
  ).toBeVisible();
});
