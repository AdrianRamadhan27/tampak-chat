const assert = require("node:assert/strict");
const { execFileSync } = require("node:child_process");
const path = require("node:path");
const { chromium } = require("@playwright/test");

(async () => {
  const root = path.resolve(__dirname, "../..");
  const fixture = execFileSync(
    path.join(root, "services/backend/.venv/bin/python"),
    [
      path.join(__dirname, "document_fixture.py"),
      path.join(root, "runtime/qa/ocr-browser"),
    ],
    { encoding: "utf8" },
  ).trim();
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
    await page.getByRole("button", { name: "Chatbots", exact: true }).click();
    await page
      .getByRole("button", { name: "Create chatbot", exact: true })
      .click();
    let dialog = page.getByRole("dialog");
    await dialog.getByLabel("Chatbot name").fill("Scanned document QA");
    await dialog
      .getByRole("button", { name: "Create chatbot", exact: true })
      .click();
    await page
      .getByRole("heading", { name: /Good questions deserve/ })
      .waitFor();
    await page.getByRole("button", { name: "Knowledge", exact: true }).click();
    await page
      .getByRole("button", { name: "Add knowledge", exact: true })
      .click();
    dialog = page.getByRole("dialog");
    await dialog.locator("input[type=file]").setInputFiles(fixture);
    await dialog.getByRole("radio", { name: /Force OCR/ }).check();
    await page.screenshot({ path: "runtime/qa/processing-options.png" });
    const uploaded = page.waitForResponse(
      (response) =>
        response.request().method() === "POST" &&
        /\/bots\/[^/]+\/sources$/.test(response.url()),
    );
    await dialog
      .getByRole("button", { name: "Upload & extract", exact: true })
      .click();
    const { revision_id } = await (await uploaded).json();
    await page
      .getByRole("button", { name: "Approve & index", exact: true })
      .waitFor({ timeout: 190000 });
    const revision = await page.evaluate(
      async (id) => (await fetch(`/api/v1/revisions/${id}`)).json(),
      revision_id,
    );
    const tables = revision.extraction.pages
      .flatMap((page) => page.blocks)
      .filter((block) => block.type === "table");
    assert.ok(
      tables.length > 0,
      "Docling recovered a structured table from the scan",
    );
    const rows = tables[0].rows;
    assert.equal(rows.length, 4);
    assert.match(JSON.stringify(rows[1]), /3\.00%/);
    assert.match(JSON.stringify(rows[2]), /3\.80%/);
    assert.match(JSON.stringify(rows[3]), /11\.10%/);
    assert.ok(tables[0].bbox && tables[0].cells.length >= 16);
    await page.screenshot({ path: "runtime/qa/scanned-table-review.png" });
    await page
      .getByRole("button", { name: "Approve & index", exact: true })
      .click();
    await page
      .getByRole("button", { name: "Enable vector indexing", exact: true })
      .waitFor({ timeout: 30000 });
    await page
      .getByText("Chunks & vector representation", { exact: true })
      .click();
    await page.locator(".chunk-list button").first().waitFor();
    await page.locator(".chunk-list button").first().click();
    assert.ok(
      (await page.locator(".source-highlight").count()) > 0,
      "Reviewed chunks retain actual OCR geometry",
    );
    assert.deepEqual(errors, []);
    console.log(
      "Document browser check passed: selectable forced OCR, image-only PDF, exact table cells, review, publication and chunk-to-source highlights.",
    );
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
