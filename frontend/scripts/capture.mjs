/** Recreate the README screenshots from the running, seeded demo. */
import { chromium } from "@playwright/test";
import { mkdir } from "node:fs/promises";

await mkdir("../docs/screenshots", { recursive: true });
const browser = await chromium.launch({
  executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE,
});
try {
  for (const [name, width, height] of [
    ["dashboard", 1440, 1040],
    ["mobile", 390, 844],
  ]) {
    const page = await browser.newPage({
      viewport: { width, height },
      deviceScaleFactor: 1,
      reducedMotion: "reduce",
    });
    await page.goto("http://127.0.0.1:5173/");
    await page.locator(".logs-panel tbody tr").first().waitFor();
    if (name === "dashboard")
      await page.locator(".product-card details summary").first().click();
    await page.screenshot({
      path: `../docs/screenshots/${name}.png`,
      fullPage: true,
    });
    await page.close();
  }
} finally {
  await browser.close();
}
