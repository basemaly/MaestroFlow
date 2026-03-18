import { chromium } from "playwright";
import { pathToFileURL } from "node:url";

const [, , inputPath, outputPath] = process.argv;

if (!inputPath || !outputPath) {
  console.error("Usage: node render-autoresearch-ui.mjs <input-html> <output-png>");
  process.exit(1);
}

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({
  viewport: { width: 1440, height: 1080 },
  deviceScaleFactor: 2,
});

await page.goto(pathToFileURL(inputPath).href, { waitUntil: "networkidle" });
await page.screenshot({ path: outputPath, fullPage: true, type: "png" });
await browser.close();
