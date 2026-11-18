import { expect, test } from "@playwright/test";

// One story, in order: an employee asks, an agent decides, a manager looks at the numbers.
test.describe.configure({ mode: "serial" });

test("a routine question is answered right away, with its source", async ({ page }) => {
  await page.goto("/#ask");
  await page.getByLabel("Your request").fill("How many vacation days do I get per year?");
  await page.getByRole("button", { name: "Send request" }).click();

  await expect(page.getByText("Answered", { exact: true })).toBeVisible();
  await expect(page.getByRole("list", { name: "Sources" })).toContainText("Vacation and Leave");
});

test("personal details are masked before anything is stored", async ({ page }) => {
  await page.goto("/#ask");
  await page.getByLabel("Your request").fill("How many vacation days do I get? Call me at 054-123-4567");
  await page.getByRole("button", { name: "Send request" }).click();
  await expect(page.getByText("Masked: phone")).toBeVisible();
});

test("a possible security incident goes to a person, not an auto-reply", async ({ page }) => {
  await page.goto("/#ask");
  await page.getByLabel("Your request").fill("I clicked a link in a phishing email and typed my password.");
  await page.getByRole("button", { name: "Send request" }).click();

  await expect(page.getByText("Waiting for approval")).toBeVisible();
  await expect(page.getByText(/sent to the IT team/)).toBeVisible();
});

test("an agent approves the drafted ticket, with an edit", async ({ page }) => {
  await page.goto("/#queue");
  await expect(page.getByRole("heading", { name: "Approval queue" })).toBeVisible();
  await page.getByRole("button", { name: /i clicked a link/i }).first().click();

  await page.getByLabel("Priority").selectOption("high");
  await page.getByLabel("Your name").fill("Noa (IT)");
  await page.getByRole("button", { name: "Approve and create ticket" }).click();

  await expect(page.getByRole("status")).toContainText(/Ticket HD-\d+ created for the IT team/);
});

test("an agent rejects a request with a reason", async ({ page, request }) => {
  const created = await request.post("/api/requests", { data: { text: "The coffee machine on the 3rd floor is broken." } });
  expect(created.ok()).toBeTruthy();
  const { id } = await created.json();

  await page.goto("/#queue");
  await page.getByRole("button", { name: /coffee machine/i }).first().click();
  await page.getByLabel("Your name").fill("Dana (Office)");
  await page.getByRole("button", { name: "Reject" }).click();
  await page.getByLabel("Reason for rejecting").fill("Facilities handles this, not the helpdesk");
  await page.getByRole("button", { name: "Confirm rejection" }).click();

  await expect(page.getByRole("status")).toContainText(`Request #${id} rejected`);
});

test("the history shows the audit trail of a request", async ({ page }) => {
  await page.goto("/#history");
  await page.getByRole("row", { name: /clicked a link/i }).first().click();

  const drawer = page.getByRole("dialog");
  await expect(drawer.getByText("Audit trail")).toBeVisible();
  await expect(drawer.getByText("approved", { exact: true })).toBeVisible();
  await expect(drawer.getByText(/Approved by Noa \(IT\)/)).toBeVisible();
});

test("the manager dashboard shows the numbers and a table view", async ({ page }) => {
  await page.goto("/#dashboard");
  await expect(page.getByText("Resolved automatically")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Requests by category" })).toBeVisible();

  await page.getByRole("button", { name: "Show table" }).click();
  await expect(page.getByRole("columnheader", { name: "Automatic" })).toBeVisible();
});
