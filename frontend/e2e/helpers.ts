import { expect, type APIRequestContext, type Page } from "@playwright/test";

export const API = "http://localhost:8000";

export type DemoRole = "Service Quality Manager" | "Plant IT Lead – Innfeld" | "IT Management" | "Supplier – AlpNet";

export async function loginAs(page: Page, role: DemoRole) {
  await page.goto("/login");
  await page.getByRole("button", { name: new RegExp(`Log in as ${role}`) }).click();
  await expect(page.getByTestId("current-user")).toBeVisible();
}

/** Every spec starts from the same demo data. */
export async function resetDemo(request: APIRequestContext) {
  const login = await request.post(`${API}/auth/login`, {
    form: { username: "sqm@valdora.example", password: "demo1234" },
  });
  const { access_token } = await login.json();
  const reset = await request.post(`${API}/demo/reset`, { headers: { Authorization: `Bearer ${access_token}` } });
  expect(reset.ok()).toBeTruthy();
}
