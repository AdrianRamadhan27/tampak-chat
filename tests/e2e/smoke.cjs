const { chromium } = require("@playwright/test");
(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({
    viewport: { width: 1440, height: 1050 },
  });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("http://127.0.0.1:3010");
  await page
    .getByRole("heading", { name: /Good questions deserve/ })
    .waitFor({ timeout: 90000 });
  await page.screenshot({ path: "runtime/qa/welcome.png", fullPage: true });
  await page.getByRole("button", { name: /Spot the trend/ }).click();
  await page
    .getByText("KEEP EXPLORING", { exact: true })
    .waitFor({ timeout: 60000 });
  await page.getByText("Failure rate by month", { exact: true }).waitFor();
  await page.screenshot({ path: "runtime/qa/chat.png", fullPage: true });
  console.log(
    JSON.stringify({
      url: page.url(),
      errors,
      answer: (await page.locator(".markdown").innerText()).slice(0, 450),
      horizontalOverflow: await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      ),
    }),
  );
  await browser.close();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
