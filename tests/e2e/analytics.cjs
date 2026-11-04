const assert = require("node:assert/strict");
const { chromium } = require("@playwright/test");

(async () => {
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage({
      viewport: { width: 1440, height: 1050 },
    });
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.goto("http://localhost:3010");
    await page
      .getByRole("heading", { name: /Good questions deserve/ })
      .waitFor();
    await page.getByRole("switch", { name: "Pipeline", exact: true }).click();
    await page.getByRole("switch", { name: "Metrics", exact: true }).click();
    async function ask(question) {
      await page.getByRole("textbox", { name: /Message NTI/ }).fill(question);
      await page
        .getByRole("button", { name: "Send message", exact: true })
        .click();
      await page
        .getByText("KEEP EXPLORING", { exact: true })
        .waitFor({ timeout: 45000 });
      await page.locator(".visual-card").waitFor();
      await page.getByRole("tab", { name: "Data", exact: true }).click();
    }
    await ask("Compare October with September failure rates");
    let cells = await page
      .locator(".visual-card tbody tr")
      .first()
      .locator("td")
      .allTextContents();
    assert.deepEqual(cells.slice(0, 4), ["2026-10", "11.1%", "3.8", "7.3"]);
    await page.getByRole("tab", { name: "Chart", exact: true }).click();
    await page.getByLabel("Chart type", { exact: true }).selectOption("bar");
    await page
      .locator(".recharts-legend-wrapper")
      .getByText("Previous period", { exact: true })
      .waitFor();
    await page.screenshot({ path: "runtime/qa/period-comparison.png" });
    await page
      .locator(".inline-citation")
      .filter({ hasText: "D1" })
      .first()
      .click();
    await page
      .getByRole("heading", { name: /Analysis source records.*10,060 match/ })
      .waitFor();
    assert.equal(await page.locator(".dataset-preview tbody tr").count(), 100);
    assert.match(
      await page.locator(".dataset-preview tbody tr").first().innerText(),
      /2026-10/,
    );
    await page.screenshot({ path: "runtime/qa/analysis-source-records.png" });
    await page
      .getByRole("button", { name: "Close dialog", exact: true })
      .click();
    await page
      .getByRole("button", { name: "Start a new conversation", exact: true })
      .click();
    await ask(
      "Which channel contributed most to the October increase in failed transactions?",
    );
    cells = await page
      .locator(".visual-card tbody tr")
      .first()
      .locator("td")
      .allTextContents();
    assert.equal(cells[0], "E-wallet");
    assert.equal(cells[1], "75.07%");
    assert.equal(
      await page
        .getByLabel("Chart type", { exact: true })
        .locator('option[value="pie"]')
        .count(),
      0,
    );
    await page
      .getByRole("button", { name: "Start a new conversation", exact: true })
      .click();
    await ask("Show the success rate trend for the last three months");
    const rates = await page
      .locator(".visual-card tbody tr td:nth-child(2)")
      .allTextContents();
    assert.deepEqual(rates, ["97%", "96.2%", "88.9%"]);
    assert.deepEqual(errors, []);
    console.log(
      "Analytics browser check passed: period comparison, grouped chart, filtered source records, contribution and success rates with both inspectors hidden.",
    );
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
