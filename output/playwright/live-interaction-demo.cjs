const puppeteer = require('puppeteer');
const fs = require('fs');

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  const portsRaw = fs.readFileSync('/tmp/financenews-ports.env', 'utf8');
  const frontendPort = (portsRaw.match(/FRONTEND_PORT=(\d+)/) || [])[1] || '3938';
  const base = `http://127.0.0.1:${frontendPort}`;

  const browser = await puppeteer.launch({ headless: true });
  const page = await browser.newPage();
  await page.setViewport({ width: 1600, height: 900 });

  const shots = [];
  const snap = async (name) => {
    const path = `output/playwright/live-interact-${name}.png`;
    await page.screenshot({ path, fullPage: true });
    shots.push(path);
  };

  const clickByText = async (selector, regex) => {
    return page.evaluate(
      ({ selector, regexSource }) => {
        const r = new RegExp(regexSource, 'i');
        const nodes = Array.from(document.querySelectorAll(selector));
        const target = nodes.find((n) => r.test((n.textContent || '').trim()));
        if (target) {
          target.click();
          return true;
        }
        return false;
      },
      { selector, regexSource: regex.source }
    );
  };

  await page.goto(base, { waitUntil: 'networkidle2' });
  await snap('01-dashboard');

  const search = await page.$('input[placeholder="Buscar"]');
  if (search) {
    await search.click({ clickCount: 3 });
    await search.type('market');
    await sleep(700);
  }
  await snap('02-dashboard-search-typed');

  const didClear = await clickByText('button', /LIMPIAR|QUITAR FILTROS/);
  if (didClear) {
    await sleep(600);
  }
  await snap('03-dashboard-after-clear-click');

  const didArticlesNav = await clickByText('a', /ARTICLES/);
  if (didArticlesNav) {
    await sleep(1000);
  } else {
    await page.goto(`${base}/articles`, { waitUntil: 'networkidle2' });
  }
  await snap('04-articles-via-nav');

  const didAnalyticsNav = await clickByText('a', /ANALYTICS/);
  if (didAnalyticsNav) {
    await sleep(1000);
  } else {
    await page.goto(`${base}/analytics`, { waitUntil: 'networkidle2' });
  }
  await snap('05-analytics-via-nav');

  await page.goto(`${base}/admin/crawler`, { waitUntil: 'networkidle2' });
  await snap('06-admin-before-run-click');

  const didRun = await clickByText('button', /RUN CRAWLERS NOW/);
  if (didRun) {
    await sleep(2000);
  }
  await snap('07-admin-after-run-click');

  fs.writeFileSync('output/playwright/live-interaction-shots.txt', shots.join('\n'));
  console.log(shots.join('\n'));

  await browser.close();
})();
