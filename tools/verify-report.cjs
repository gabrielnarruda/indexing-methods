// Offline presentation checks; does not run inference or change benchmark data.
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const { pathToFileURL } = require('url');

(async () => {
  const root = path.resolve(__dirname, '..');
  const output = path.join(root, 'reports/validation');
  const source = path.join(root, 'reports/full/relatorio.html');
  const checks = [];
  const check = (condition, label) => { if (!condition) throw Error(label); checks.push(label); };
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1100 }, reducedMotion: 'reduce' });
    const errors = [], external = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => { if (/^https?:/.test(request.url())) external.push(request.url()); });
    await page.goto(pathToFileURL(source).href);
    check(await page.locator('h1').count() === 1, 'One primary title');
    check(await page.locator('details[data-corpus]').count() === 720, 'All 720 original field evaluations retained');
    check(await page.locator('#workbench .work').count() === 8, 'Eight developer work packages');
    check((await page.locator('#prompts pre').first().textContent()).startsWith('Você extrai informações'), 'Historical system prompt rendered');
    check((await page.locator('#prompts').textContent()).includes('Extraia até 6 relações'), 'Six-relation constraint explained');
    check(await page.locator('[data-result="adpf54"]').isVisible(), 'Legal results initially visible');
    await page.getByRole('button', {name: 'Livro de literatura', exact: true}).focus();
    await page.keyboard.press('Enter');
    check(await page.locator('[data-result="dom-casmurro"]').isVisible(), 'Keyboard switches result document');
    check(!(await page.locator('[data-result="adpf54"]').isVisible()), 'Other result panel hidden');
    await page.getByRole('button', {name: 'Ver os dois', exact: true}).click();
    check(await page.locator('.result-panel:visible').count() === 2, 'Both result tables available');
    const links = await page.locator('a[href]').evaluateAll(nodes => nodes.map(node => node.getAttribute('href')));
    const ids = new Set(await page.locator('[id]').evaluateAll(nodes => nodes.map(node => node.id)));
    for (const href of links) {
      if (href.startsWith('#')) check(ids.has(decodeURIComponent(href.slice(1))), `Anchor exists: ${href}`);
      else if (!/^(?:https?:|mailto:)/.test(href)) check(fs.existsSync(path.resolve(path.dirname(source), decodeURIComponent(href.split('#')[0]))), `Local link exists: ${href}`);
    }
    await page.evaluate(() => scrollTo(0, 0));
    await page.screenshot({ path: path.join(output, 'report-explained-desktop.png') });
    await page.locator('#resultados').scrollIntoViewIfNeeded();
    await page.screenshot({ path: path.join(output, 'report-explained-results.png') });
    await page.locator('#audit-details > summary').click();
    await page.locator('#corpus').selectOption('adpf54');
    await page.locator('#variant').selectOption('F');
    check(await page.locator('details[data-corpus]:visible').count() === 72, 'Audit filter retains 24 fields times 3 repetitions');
    await page.locator('details[data-corpus]:visible').first().locator('summary').click();
    check(await page.locator('details[data-corpus]:visible').first().locator('pre').isVisible(), 'Original answer details open');
    await page.locator('#rate').fill('10');
    check((await page.locator('#cost').textContent()).includes('Projeção:'), 'Machine cost projection works');
    await page.locator('#audit-details > summary').click();
    const widths = [];
    for (const width of [390, 768, 1440]) {
      await page.setViewportSize({ width, height: 844 });
      const dimensions = await page.evaluate(() => ({viewport: innerWidth, body: document.body.scrollWidth, document: document.documentElement.scrollWidth}));
      widths.push(dimensions);
      check(dimensions.body <= width && dimensions.document <= width, `No horizontal page overflow at ${width}px`);
    }
    await page.setViewportSize({width: 390, height: 844});
    await page.evaluate(() => scrollTo(0, document.querySelector('main').offsetTop));
    await page.screenshot({path: path.join(output, 'report-explained-mobile.png')});
    await page.getByRole('button', {name: 'Documento judicial', exact: true}).click();
    await page.emulateMedia({media: 'print'});
    check(await page.locator('.result-panel:visible').count() === 2, 'Print includes both result tables');
    check(!(await page.locator('.audit').isVisible()), 'Print omits 720-entry audit appendix');
    await page.emulateMedia({media: 'screen'});
    const noJs = await browser.newContext({javaScriptEnabled: false, viewport: {width: 1280, height: 900}});
    const staticPage = await noJs.newPage();
    await staticPage.goto(pathToFileURL(source).href);
    check(await staticPage.locator('.result-panel:visible').count() === 2, 'Both result tables readable without JavaScript');
    await noJs.close();
    check(errors.length === 0, 'No browser JavaScript errors');
    check(external.length === 0, 'No external network requests');
    const summary = {status: 'passed', scope: 'HTML presentation and retained benchmark data; no new model evaluation',
      checked_at: new Date().toISOString(), viewport_checks: widths, checks,
      javascript_errors: errors, external_requests: external};
    fs.writeFileSync(path.join(output, 'report-revision.json'), JSON.stringify(summary, null, 2));
    console.log(JSON.stringify({status: summary.status, checks: checks.length, viewport_checks: widths, javascript_errors: errors, external_requests: external}));
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exit(1);});
