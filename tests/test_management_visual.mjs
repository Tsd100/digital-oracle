import { chromium } from 'playwright';

const baseUrl = process.env.TIMELINE_BASE_URL || 'http://127.0.0.1:5001';
const browser = await chromium.launch({ headless: true });

try {
  for (const viewport of [{ name: 'desktop', width: 1360, height: 900 }, { name: 'mobile', width: 390, height: 844 }]) {
    const page = await browser.newPage({ viewport });
    const errors = [];
    page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
    await page.goto(`${baseUrl}/`);
    await page.locator('.subject-card').first().waitFor();

    if (await page.locator('.subject-card').count() < 8) throw new Error(`${viewport.name}: missing subject cards`);
    if (await page.locator('.change-item').count() < 1) throw new Error(`${viewport.name}: missing change feed`);
    if (await page.locator('#health-content').textContent().then((text) => !text.includes('自动入库'))) throw new Error(`${viewport.name}: missing health`);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    if (overflow !== 0) throw new Error(`${viewport.name}: horizontal overflow ${overflow}px`);
    if (errors.length) throw new Error(`${viewport.name}: console errors ${errors.join('; ')}`);

    await page.locator('[data-filter="changed"]').click();
    if (await page.locator('.subject-card[data-changed="false"]').count()) throw new Error(`${viewport.name}: changed filter leaked stable cards`);
    await page.locator('#theme-toggle').click();
    if (!await page.evaluate(() => Boolean(localStorage.getItem('do-timeline-theme')))) throw new Error(`${viewport.name}: theme was not persisted`);
    await page.close();
  }

  const page = await browser.newPage();
  await page.goto(`${baseUrl}/ask`);
  if (!await page.locator('#question-form').count()) throw new Error('question workspace missing at /ask');
  if (await page.locator('a[href="/"]').count() < 1) throw new Error('question workspace cannot return to management center');
  await page.close();
  console.log('management visual checks passed: desktop, mobile, filters, theme, /ask');
} finally {
  await browser.close();
}
