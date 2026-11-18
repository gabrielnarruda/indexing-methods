const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');
const { pathToFileURL } = require('url');

(async () => {
  const root = path.resolve(__dirname, '..');
  const output = path.join(root, 'reports', 'validation');
  fs.mkdirSync(output, {recursive: true});
  const browser = await chromium.launch({channel: 'msedge', headless: true});
  const page = await browser.newPage({viewport: {width: 1440, height: 1100}});
  const errors = [];
  const externalRequests = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', request => {
    if (/^https?:/.test(request.url())) externalRequests.push(request.url());
  });
  const open = async filename => page.goto(pathToFileURL(path.join(root, filename)).href);
  const check = (value, message) => { if (!value) throw Error(message); };

  await open('docs/arquitetura.html');
  await page.locator('[data-id="graph"]').click();
  check(await page.locator('#detail-title').textContent() === 'Neo4j', 'Node selection');
  const before = await page.locator('#zoom-value').textContent();
  await page.locator('#zoom-in').click();
  check(before !== await page.locator('#zoom-value').textContent(), 'Zoom control');
  await page.locator('#fit').click();
  await page.screenshot({path: path.join(output, 'architecture.png'), fullPage: true});
  await page.locator('#tab-tests').click();
  check(await page.locator('.node').count() === 10, 'Test pipeline view');
  await page.locator('[data-id="trace"]').click();
  await page.screenshot({path: path.join(output, 'test-pipeline.png'), fullPage: true});

  await open('reports/full/grafo.html');
  check(await page.locator('#entity option').count() > 0, 'Graph entities');
  await page.locator('g.node').first().click();
  check((await page.locator('#quote').textContent()).length >= 12, 'Graph source quote');
  check((await page.locator('#source').getAttribute('href')).includes('#page='), 'PDF page link');
  await page.screenshot({path: path.join(output, 'graph.png'), fullPage: true});
  await page.locator('#corpus').selectOption('dom-casmurro');
  check((await page.locator('#count').textContent()).includes('81 afirmações'), 'Book graph scope');
  await page.locator('#query').fill('ZZZ-DOES-NOT-EXIST');
  check(await page.locator('#entity option').count() === 0, 'Empty entity filter');
  await page.locator('#query').fill('Escobar');
  check(await page.locator('#entity option').count() > 0, 'Entity search');
  await page.locator('g.node').first().focus();
  await page.keyboard.press('Enter');
  check((await page.locator('#quote').textContent()).length >= 12, 'Keyboard graph selection');

  await open('reports/full/relatorio.html');
  const entries = await page.locator('details[data-corpus]').count();
  check(entries > 0, 'Measured report entries');
  await page.locator('#corpus').selectOption('adpf54');
  await page.locator('#variant').selectOption('F');
  const shown = await page.locator('details[data-corpus]:visible').count();
  check(shown > 0 && shown < entries, 'Report filters');
  check(await page.locator('details:not([data-corpus])').first().isVisible(), 'Stage table remains available');
  await page.locator('#rate').fill('10');
  check((await page.locator('#cost').textContent()).includes('Projeção:'), 'Cost projection');
  await page.evaluate(() => scrollTo(0, 0));
  await page.screenshot({path: path.join(output, 'report.png'), fullPage: false});
  await page.setViewportSize({width: 390, height: 844});
  await open('docs/arquitetura.html');
  check(await page.evaluate(() => document.body.scrollWidth <= innerWidth), 'Mobile page width');
  await page.screenshot({path: path.join(output, 'architecture-mobile.png'), fullPage: true});
  check(errors.length === 0, errors.join('\n'));
  check(externalRequests.length === 0, 'Unexpected external network requests');
  const summary = {status: 'passed', report_entries: entries, javascript_errors: errors,
    external_requests: externalRequests, checks: ['architecture nodes and zoom', 'test pipeline',
      'graph source and scope', 'entity search', 'keyboard access', 'report filters',
      'cost projection', 'mobile architecture'], checked_at: new Date().toISOString()};
  fs.writeFileSync(path.join(output, 'browser-checks.json'), JSON.stringify(summary, null, 2));
  console.log(JSON.stringify(summary));
  await browser.close();
})().catch(error => { console.error(error); process.exit(1); });
