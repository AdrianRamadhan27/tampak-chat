const assert = require("node:assert/strict");
const { spawn } = require("node:child_process");
const path = require("node:path");
const { chromium } = require("@playwright/test");

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({
    viewport: { width: 1366, height: 960 },
  });
  await page.goto("http://localhost:3010");
  await page.getByRole("heading", { name: /Good questions deserve/ }).waitFor();
  const setup = await page.evaluate(async () => {
    const session = await (await fetch("/api/v1/session")).json();
    const bots = await (await fetch("/api/v1/bots")).json();
    const bot = bots.find((item) => item.is_seed);
    const conversation = await (
      await fetch(`/api/v1/bots/${bot.id}/conversations`, {
        method: "POST",
        headers: { "X-CSRF-Token": session.csrf },
      })
    ).json();
    return { owner: session.id, bot: bot.id, conversation: conversation.id };
  });
  const root = path.resolve(__dirname, "../..");
  const producer = spawn(
    path.join(root, "services/backend/.venv/bin/python"),
    [
      path.join(root, "tests/e2e/stream_fixture.py"),
      setup.owner,
      setup.conversation,
      setup.bot,
    ],
    { cwd: path.join(root, "services/backend") },
  );
  await new Promise((resolve, reject) => {
    producer.stdout.once("data", resolve);
    producer.once("error", reject);
    producer.once("exit", (code) => {
      if (code) reject(new Error(`Transport fixture exited with ${code}`));
    });
    producer.stderr.on("data", (chunk) => process.stderr.write(chunk));
  });
  await page.goto(
    `http://localhost:3010/?bot=${setup.bot}&chat=${setup.conversation}`,
  );
  await page.locator(".markdown").filter({ hasText: "Part 1." }).waitFor();
  await page.getByRole("button", { name: "Chatbots", exact: true }).click();
  await page.waitForTimeout(1200);
  await page.getByRole("button", { name: "Conversation", exact: true }).click();
  await page.waitForFunction(() =>
    document.querySelector(".markdown")?.textContent.includes("Part 3."),
  );
  assert.ok(
    !(await page.locator(".markdown").innerText()).includes("Part 6."),
    "Must restore while the producer is still running",
  );
  await page.waitForFunction(() =>
    document.querySelector(".markdown")?.textContent.includes("Part 6."),
  );
  await page.waitForTimeout(1300);
  const expected = "Part 1. Part 2. Part 3. Part 4. Part 5. Part 6.";
  assert.equal((await page.locator(".markdown").innerText()).trim(), expected);
  await page.reload();
  await page.locator(".markdown").waitFor();
  assert.equal((await page.locator(".markdown").innerText()).trim(), expected);
  await page.screenshot({ path: "runtime/qa/reconnect-complete.png" });
  console.log(
    "SSE browser recovery passed: left the chat, restored an active run, received remaining output, reloaded with no duplicated text.",
  );
  await browser.close();
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
