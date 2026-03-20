const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  
  const requests = [];
  const cssRequests = [];
  const errorStatuses = [];
  
  page.on('request', (req) => {
    requests.push({ url: req.url() });
  });
  
  page.on('response', (res) => {
    const url = res.url();
    if (url.includes('.css')) cssRequests.push(url);
    if (res.status() >= 400) {
      errorStatuses.push({ url, status: res.status() });
    }
  });
  
  const startTime = Date.now();
  try {
    await page.goto('http://localhost:2027/workspace/executive', {
      waitUntil: 'networkidle',
      timeout: 30000,
    });
  } catch (e) {
    console.error('Navigation failed:', e.message);
  }
  const loadTime = Date.now() - startTime;
  
  await page.waitForTimeout(2000);
  
  const uniqueCss = [...new Set(cssRequests)].length;
  const error404s = errorStatuses.filter(r => r.status === 404).length;
  
  console.log('\n=== EXECUTIVE PAGE PERFORMANCE (Round 1) ===\n');
  console.log(`⏱️  Page Load Time: ${loadTime}ms`);
  console.log(`📡 Total Requests: ${requests.length}`);
  console.log(`🎨 Unique CSS Files: ${uniqueCss}`);
  console.log(`❌ 404 Errors: ${error404s}`);
  
  if (errorStatuses.length > 0) {
    console.log('\n❌ HTTP Errors:');
    errorStatuses.slice(0, 5).forEach(err => {
      const path = err.url.split('?')[0];
      console.log(`  - ${err.status}: ${path.slice(-60)}`);
    });
  }
  
  await page.screenshot({ path: '/tmp/executive-page.png' });
  console.log('\n📸 Screenshot: /tmp/executive-page.png');
  
  await browser.close();
})();
