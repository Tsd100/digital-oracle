import { chromium } from 'playwright';

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1360, height: 900 } });
try {
  await page.goto('http://127.0.0.1:5000/timeline?subject=黄金');
  await page.locator('.report-node').first().waitFor();
  const goldNodes = await page.locator('.report-node').count();
  const goldSegments = await page.locator('.prob-segment').count();
  if (goldNodes < 2 || goldSegments !== 0) throw new Error(`gold nodes=${goldNodes} segments=${goldSegments}`);
  await page.goto('http://127.0.0.1:5000/timeline?subject=有色');
  await page.locator('.prob-segment').first().waitFor({ state: 'attached' });
  const segments = await page.locator('.prob-segment').count();
  if (segments !== 1) throw new Error(`nonferrous segments=${segments}`);
  await page.locator('.report-node').first().click();
  await page.locator('#report-dialog[open]').waitFor();
  console.log(`visual checks passed: gold nodes=${goldNodes}, gold lines=0, nonferrous lines=${segments}`);
} finally {
  await browser.close();
}
