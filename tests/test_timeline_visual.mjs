import { chromium } from 'playwright';

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1360, height: 900 } });
try {
  await page.goto('http://127.0.0.1:5000/timeline?subject=原油');
  await page.locator('#count').getByText(/联合分析 \d+ 份 · 单主题需补字段 \d+ 份/).waitFor();
  await page.goto('http://127.0.0.1:5000/timeline?subject=黄金');
  await page.locator('#count').getByText(/联合分析 \d+ 份 · 单主题需补字段 \d+ 份/).waitFor();
  await page.locator('#report-list').evaluate((el) => { el.open = true; });
  await page.locator('.report-card').first().waitFor();
  const countText = await page.locator('#count').textContent();
  const [, jointText, gapText] = countText.match(/联合分析 (\d+) 份 · 单主题需补字段 (\d+) 份/) || [];
  const jointCards = await page.locator('.report-card .quality.review', { hasText: '联合分析' }).count();
  const gapCards = await page.locator('.report-card .quality.review', { hasText: '需补字段' }).count();
  if (!jointCards || !gapCards || jointCards !== Number(jointText) || gapCards !== Number(gapText)) throw new Error(`gold joint=${jointCards} gaps=${gapCards}`);
  if (!await page.locator('.review-reasons').first().textContent()) throw new Error('missing review reason');
  await page.locator('.report-node').first().waitFor();
  const goldNodes = await page.locator('.report-node').count();
  const goldSegments = await page.locator('.prob-segment').count();
  if (goldNodes < 2 || goldSegments !== 0) throw new Error(`gold nodes=${goldNodes} segments=${goldSegments}`);
  const goldBullish = await page.locator('.report-node[data-direction="bullish"]').count();
  const goldBearish = await page.locator('.report-node[data-direction="bearish"]').count();
  const goldMixed = await page.locator('.report-node[data-direction="mixed"]').count();
  if (goldBullish < 2 || goldBearish < 2 || goldMixed < 2) throw new Error(`gold directions bullish=${goldBullish} bearish=${goldBearish} mixed=${goldMixed}`);
  if (!await page.locator('.report-card .subject-judgment').first().textContent()) throw new Error('missing asset-specific judgment');
  await page.goto('http://127.0.0.1:5000/timeline?subject=白银');
  await page.locator('.report-node').first().waitFor();
  const silverResolved = await page.locator('.report-node:not([data-direction="unknown"])').count();
  if (silverResolved < 6) throw new Error(`silver resolved=${silverResolved}`);
  if (Number(await page.locator('#stat-direction').textContent()) !== silverResolved) throw new Error('direction stat does not match chart');
  await page.goto('http://127.0.0.1:5000/timeline?subject=科创50');
  await page.locator('.report-node').first().waitFor();
  const starResolved = await page.locator('.report-node:not([data-direction="unknown"])').count();
  if (starResolved < 3) throw new Error(`STAR 50 resolved=${starResolved}`);
  await page.goto('http://127.0.0.1:5000/timeline?subject=有色');
  await page.locator('.prob-segment').first().waitFor({ state: 'attached' });
  const segments = await page.locator('.prob-segment').count();
  if (segments !== 1) throw new Error(`nonferrous segments=${segments}`);
  await page.locator('.report-node').first().click();
  await page.locator('#report-dialog[open]').waitFor();
  await page.goto('http://127.0.0.1:5000/timeline?subject=美联储');
  await page.locator('.report-node').first().waitFor();
  if (await page.locator('.report-node:not([data-direction="not_applicable"])').count()) throw new Error('policy report mapped to asset stance');
  if (!((await page.locator('#direction-note').textContent()) || '').includes('议息会议')) throw new Error('missing policy horizon explanation');
  console.log(`visual checks passed: gold nodes=${goldNodes}, gold lines=0, nonferrous lines=${segments}`);
} finally {
  await browser.close();
}
