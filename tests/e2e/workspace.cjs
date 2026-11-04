const assert = require("node:assert/strict");
const { chromium } = require("@playwright/test");
(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1050 },
  });
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("http://127.0.0.1:3010");
  await page
    .getByRole("heading", { name: /Good questions deserve/ })
    .waitFor({ timeout: 60000 });
  await page
    .getByRole("button", { name: "12 knowledge sources", exact: true })
    .waitFor();
  assert.equal(
    await page.locator(".attachment-chip").count(),
    0,
    "Chatbot knowledge must not appear as removable chat attachments before the first message",
  );
  const rail = page.getByRole("complementary", {
    name: "Workspace navigation",
  });
  assert.equal(Math.round((await rail.boundingBox()).width), 60);
  await rail.hover();
  await page.waitForTimeout(250);
  assert.equal(Math.round((await rail.boundingBox()).width), 224);
  await page.screenshot({ path: "runtime/qa/sidebar-hover.png" });
  await page.mouse.move(600, 100);
  await page.waitForTimeout(250);
  assert.equal(Math.round((await rail.boundingBox()).width), 60);
  await page.keyboard.press("Tab");
  await page.keyboard.press("Tab");
  await page.waitForTimeout(250);
  assert.equal(
    Math.round((await rail.boundingBox()).width),
    224,
    "Keyboard focus expands the rail",
  );
  await page.getByRole("textbox", { name: /Message NTI/ }).click();
  await page.getByRole("button", { name: "Chatbots", exact: true }).click();
  await page
    .getByRole("button", { name: "Create chatbot", exact: true })
    .click();
  let dialog = page.getByRole("dialog");
  await dialog.getByLabel("Chatbot name").fill("QA visible workspace");
  await dialog
    .getByLabel("What is it for?")
    .fill("Browser verification of isolated document retrieval.");
  await dialog
    .getByRole("button", { name: "Create chatbot", exact: true })
    .click();
  await page.getByRole("heading", { name: /Good questions deserve/ }).waitFor();
  await page.getByRole("button", { name: "Knowledge", exact: true }).click();
  await page
    .getByRole("button", { name: "Add knowledge", exact: true })
    .click();
  dialog = page.getByRole("dialog");
  await dialog.locator("input[type=file]").setInputFiles({
    name: "gateway-policy.txt",
    mimeType: "text/plain",
    buffer: Buffer.from(
      "Gateway policy\n\nThe payment gateway retry limit is three attempts. Use an idempotency key for every retry. This is a synthetic test document.",
    ),
  });
  await dialog
    .getByRole("button", { name: "Upload & extract", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Approve & index", exact: true })
    .waitFor({ timeout: 45000 });
  await page
    .getByRole("button", { name: "Approve & index", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Enable vector indexing", exact: true })
    .waitFor({ timeout: 30000 });
  await page.screenshot({ path: "runtime/qa/extraction-review.png" });
  await page.getByRole("button", { name: "Close dialog", exact: true }).click();
  await page.getByRole("button", { name: "Conversation", exact: true }).click();
  await page
    .getByRole("button", { name: "1 knowledge source", exact: true })
    .waitFor();
  assert.equal(
    await page.locator(".attachment-chip").count(),
    0,
    "Permanent private-bot knowledge must not be removable from a new chat",
  );
  await page
    .getByRole("textbox", { name: /Message QA/ })
    .fill("What is the payment gateway retry limit?");
  await page.getByRole("button", { name: "Send message", exact: true }).click();
  await page
    .getByText("KEEP EXPLORING", { exact: true })
    .waitFor({ timeout: 45000 });
  assert.match(await page.locator(".markdown").innerText(), /three attempts/);
  const pane = page.locator(".chat-pane");
  const inspector = page.getByRole("complementary", {
    name: "Live run inspector",
  });
  let chatBounds = await pane.boundingBox();
  let inspectorBounds = await inspector.boundingBox();
  assert.ok(
    inspectorBounds.x >= chatBounds.x + chatBounds.width - 1,
    "Desktop inspector docks to the right",
  );
  assert.ok(Math.abs(inspectorBounds.y - chatBounds.y) < 2);
  await page
    .locator(".pipeline-graph.compact .react-flow__node")
    .first()
    .waitFor();
  assert.ok(
    (await page.locator(".react-flow__node").first().boundingBox()).width > 90,
    "Side-panel stage labels stay readable",
  );
  await page.getByRole("switch", { name: "Pipeline", exact: true }).click();
  assert.equal(await page.locator(".pipeline-graph").count(), 0);
  await page.getByRole("switch", { name: "Metrics", exact: true }).click();
  assert.equal(await inspector.count(), 0);
  await page.getByRole("switch", { name: "Pipeline", exact: true }).click();
  await page.getByRole("switch", { name: "Metrics", exact: true }).click();
  await page
    .getByRole("button", { name: "Attach a document or image", exact: true })
    .click();
  dialog = page.getByRole("dialog");
  await dialog.locator("input[type=file]").setInputFiles({
    name: "chat-note.txt",
    mimeType: "text/plain",
    buffer: Buffer.from(
      "This is a private, removable conversation attachment. Marker: orange tulip.",
    ),
  });
  await dialog
    .getByRole("button", { name: "Upload & extract", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Approve & index", exact: true })
    .waitFor({ timeout: 45000 });
  await page
    .getByRole("button", { name: "Approve & index", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Enable vector indexing", exact: true })
    .waitFor({ timeout: 30000 });
  await page.getByRole("button", { name: "Close dialog", exact: true }).click();
  const attachmentRegion = page.getByRole("region", {
    name: "Conversation attachments",
    exact: true,
  });
  await attachmentRegion.waitFor();
  assert.equal(await attachmentRegion.locator(".attachment-chip").count(), 1);
  const removal = page.waitForResponse(
    (response) =>
      response.request().method() === "DELETE" &&
      /\/conversations\/[^/]+\/attachments\//.test(response.url()),
  );
  await attachmentRegion
    .getByRole("button", {
      name: "Remove chat-note.txt from this conversation",
      exact: true,
    })
    .click();
  assert.equal((await removal).status(), 200);
  await attachmentRegion.waitFor({ state: "detached" });
  await page
    .getByRole("button", { name: "1 knowledge source", exact: true })
    .waitFor();
  await page
    .getByRole("textbox", { name: /Message QA/ })
    .fill("What is the payment gateway retry limit?");
  await page.getByRole("button", { name: "Send message", exact: true }).click();
  await page.waitForFunction(
    () => document.querySelectorAll(".suggested-actions").length === 2,
    { timeout: 45000 },
  );
  assert.match(
    await page.locator(".markdown").last().innerText(),
    /three attempts/,
  );
  await page
    .getByRole("button", { name: "Choose chatbot", exact: true })
    .click();
  await page.getByRole("menuitem", { name: /NTI Operations/ }).click();
  await page.getByRole("button", { name: /Spot the trend/ }).click();
  await page
    .getByText("KEEP EXPLORING", { exact: true })
    .waitFor({ timeout: 45000 });
  await page
    .getByRole("img", { name: /Failure rate by month/ })
    .waitFor({ timeout: 30000 });
  await page.locator(".visual-card").first().scrollIntoViewIfNeeded();
  await page.screenshot({ path: "runtime/qa/analytics-chart.png" });
  await page.getByRole("tab", { name: "Data", exact: true }).click();
  assert.ok((await page.locator(".visual-card table tbody tr").count()) === 3);
  await page.getByRole("tab", { name: "Chart", exact: true }).click();
  await page
    .getByRole("button", { name: "Break down by channel", exact: true })
    .click();
  await page.waitForFunction(
    () => document.querySelectorAll(".suggested-actions").length === 2,
    { timeout: 45000 },
  );
  assert.match(
    await page.locator(".markdown").last().innerText(),
    /2026-08-01 to 2026-11-01/,
  );
  const savedUrl = page.url();
  await page.reload();
  await page
    .getByText("KEEP EXPLORING", { exact: true })
    .last()
    .waitFor({ timeout: 30000 });
  assert.equal(page.url(), savedUrl);
  assert.equal(await page.locator(".user-message").count(), 2);
  await page
    .getByRole("button", { name: "Start a new conversation", exact: true })
    .click();
  await page.getByRole("button", { name: /Ask the documents/ }).click();
  await page
    .getByText("KEEP EXPLORING", { exact: true })
    .waitFor({ timeout: 45000 });
  await page.locator(".diagram-panel svg").waitFor({ timeout: 45000 });
  await page.locator(".diagram-panel").scrollIntoViewIfNeeded();
  await page.screenshot({ path: "runtime/qa/diagram.png" });
  const documentCitation = page
    .locator('.source-chips button[title$=".pdf"]')
    .first();
  const citedPage = Number(
    (await documentCitation.locator("small").innerText()).replace(/\D/g, ""),
  );
  await documentCitation.click();
  await page.getByRole("spinbutton", { name: "Source page number" }).waitFor();
  assert.equal(
    await page
      .getByRole("spinbutton", { name: "Source page number" })
      .inputValue(),
    String(citedPage),
  );
  assert.ok((await page.locator(".source-highlight").count()) > 0);
  await page.locator(".document-page img").waitFor();
  await page.waitForFunction(() => {
    const img = document.querySelector(".document-page img");
    return img && img.complete && img.naturalWidth > 0;
  });
  await page.screenshot({ path: "runtime/qa/source-citation.png" });
  await page
    .getByRole("button", { name: "Rotate page clockwise", exact: true })
    .click();
  await page.getByRole("button", { name: "Zoom in", exact: true }).click();
  await page.waitForTimeout(100);
  const geometry = await page.evaluate(() => {
    const image = document
      .querySelector(".document-page img")
      .getBoundingClientRect();
    return [...document.querySelectorAll(".source-highlight")].every(
      (element) => {
        const r = element.getBoundingClientRect();
        return (
          r.left >= image.left - 2 &&
          r.top >= image.top - 2 &&
          r.right <= image.right + 2 &&
          r.bottom <= image.bottom + 2
        );
      },
    );
  });
  assert.ok(
    geometry,
    "Highlights remain on the source after zoom and rotation",
  );
  await page.screenshot({ path: "runtime/qa/source-rotated.png" });

  await page.getByRole("button", { name: "Close dialog", exact: true }).click();
  const originalSources = await page
    .locator(".source-chips")
    .last()
    .locator("button")
    .allTextContents();
  await page
    .getByRole("button", { name: "Explain the evidence", exact: true })
    .click();
  await page.waitForFunction(
    () => document.querySelectorAll(".suggested-actions").length === 2,
    { timeout: 45000 },
  );
  assert.ok((await page.locator(".markdown").last().innerText()).trim());
  assert.deepEqual(
    await page
      .locator(".source-chips")
      .last()
      .locator("button")
      .allTextContents(),
    originalSources,
    "Explain the evidence keeps the exact sources from the originating answer",
  );
  await page.getByText("Previous answer evidence", { exact: true }).waitFor();
  await page.screenshot({ path: "runtime/qa/evidence-followup.png" });
  for (const width of [1056, 768, 390, 352]) {
    await page.setViewportSize({ width, height: 900 });
    await page.waitForTimeout(150);
    assert.equal(
      await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      ),
      false,
      "overflow at " + width,
    );
    chatBounds = await pane.boundingBox();
    inspectorBounds = await inspector.boundingBox();
    assert.ok(
      inspectorBounds.y >= chatBounds.y + chatBounds.height - 1,
      "Narrow inspector docks below at " + width,
    );
    if (width === 390) {
      await page.screenshot({ path: "runtime/qa/mobile-chat.png" });
      await page
        .getByRole("button", { name: "Open navigation", exact: true })
        .click();
      await page.waitForTimeout(250);
      assert.equal(Math.round((await rail.boundingBox()).x), 0);
      await page.getByRole("button", { name: "Chatbots", exact: true }).click();
      await page
        .getByRole("button", { name: "Open navigation", exact: true })
        .click();
      await page
        .getByRole("button", { name: "Conversation", exact: true })
        .click();
    }
  }
  await page.setViewportSize({ width: 1440, height: 1050 });
  await page
    .getByRole("button", { name: "Switch to dark theme", exact: true })
    .click();
  await page.screenshot({ path: "runtime/qa/dark-chat.png" });
  console.log(
    JSON.stringify({
      checks:
        "hover sidebar, chatbot creation, source upload/review/index, permanent knowledge excluded from the attachment tray, conversation-only attachment removal preserves knowledge, isolated retrieval, right-side desktop inspector and readable graph, bottom inspector on narrow screens, independent toggles, chart/data, exact page highlight, contextual analytics and exact-evidence follow-ups, reload, diagram, responsive and dark mode",
      errors,
    }),
  );
  assert.deepEqual(errors, []);
  await browser.close();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
