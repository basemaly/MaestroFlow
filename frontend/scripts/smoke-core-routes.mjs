import { chromium } from "@playwright/test";

const BASE_URL = process.env.MAESTROFLOW_BASE_URL || "http://localhost:2027";

async function expectVisible(page, text) {
  await page.getByText(text, { exact: false }).first().waitFor({ state: "visible", timeout: 15000 });
}

async function run() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();

  try {
    await page.goto(`${BASE_URL}/workspace/chats/new`, { waitUntil: "networkidle" });
    await expectVisible(page, "New chat");
    await expectVisible(page, "Executive");

    await page.goto(`${BASE_URL}/workspace/agents`, { waitUntil: "networkidle" });
    await expectVisible(page, "Agents");

    const chatButton = page.getByRole("button", { name: "Chat" }).first();
    if (await chatButton.count()) {
      await chatButton.click();
      await page.waitForURL(/\/workspace\/agents\/.+\/chats\/new/, { timeout: 15000 });
      await page.getByRole("textbox", { name: "How can I assist you today?" }).waitFor({
        state: "visible",
        timeout: 15000,
      });
    }

    await page.goto(`${BASE_URL}/workspace/executive`, { waitUntil: "networkidle" });
    await expectVisible(page, "Executive");
    await page.getByRole("textbox").first().waitFor({ state: "visible", timeout: 15000 });

    console.log("Core route smoke test passed.");
  } finally {
    await browser.close();
  }
}

run().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
