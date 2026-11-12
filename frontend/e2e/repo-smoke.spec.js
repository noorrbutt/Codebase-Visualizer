import { expect, test } from "@playwright/test";

const repo = {
  id: 42,
  owner: "example",
  repo_name: "demo",
  default_branch: "main",
  status: "ready",
  summary: "A small demo repository.",
  nodes: [
    { id: 1, path: "src/App.jsx", language: "javascript", line_count: 40, import_count: 2 },
    { id: 2, path: "src/main.jsx", language: "javascript", line_count: 12, import_count: 1 },
    { id: 3, path: "src/api.js", language: "javascript", line_count: 22, import_count: 1 },
    { id: 4, path: "src/styles.css", language: "css", line_count: 35, import_count: 0 },
    { id: 5, path: "README.md", language: "markdown", line_count: 15, import_count: 0 },
  ],
  edges: [
    { source: "src/main.jsx", target: "src/App.jsx" },
    { source: "src/App.jsx", target: "src/api.js" },
    { source: "src/App.jsx", target: "src/styles.css" },
    { source: "src/main.jsx", target: "src/api.js" },
  ],
  metrics: {
    cycle_count: 0,
    orphan_count: 1,
    cycles: [],
    orphans: ["README.md"],
    top_fan_in: [],
    top_fan_out: [],
  },
};

test("analyzes a repository and opens a selected node's details", async ({ page }) => {
  let analyzeRequests = 0;
  let statusRequests = 0;
  await page.route("**/repos/analyze", async (route) => {
    analyzeRequests += 1;
    await route.fulfill({ json: { id: repo.id, status: "parsing" } });
  });
  await page.route(`**/repos/${repo.id}/status`, async (route) => {
    statusRequests += 1;
    await route.fulfill({ json: { status: "ready", stage: "complete" } });
  });
  await page.route(`**/repos/${repo.id}`, async (route) => {
    await route.fulfill({ json: repo });
  });

  await page.goto("/");
  await expect(page.getByRole("heading", { name: "See how your code connects." })).toBeVisible();
  await page.getByRole("textbox", { name: "GitHub repository URL" })
    .fill("https://github.com/example/demo");
  await page.getByRole("button", { name: "Visualize" }).click();

  await expect(page.getByRole("status").filter({ hasText: "Analyzing example/demo" }))
    .toBeVisible();
  await expect(page.getByText("Fetching repository tree and source files")).toBeVisible();
  await expect(page.getByRole("tab", { name: "Overview" })).toBeVisible({ timeout: 10_000 });
  expect(analyzeRequests).toBe(1);
  expect(statusRequests).toBe(1);

  await page.getByRole("tab", { name: "Files" }).click();
  await page.getByRole("button", { name: "Select src/App.jsx" }).click();
  await expect(page.getByText("App.jsx", { exact: true }).last()).toBeVisible();
  await expect(page.getByRole("button", { name: "Close details for src/App.jsx" })).toBeVisible();
});
