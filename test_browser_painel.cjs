const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');

(async () => {
  const browser = await chromium.launch({channel:'msedge', headless:true});
  try {
    const page = await browser.newPage({viewport:{width:1920,height:1080}});
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto('http://127.0.0.1:5051/test-login');
    await page.waitForFunction(() => document.getElementById('produzido').textContent === '300');
    assert.equal(await page.locator('#eficiencia').innerText(), '—');
    assert.equal(await page.locator('.op-card').count(), 2);
    assert.equal(await page.locator('#fabrica option').count(), 1);
    assert.equal(await page.locator('#meta').innerText(), '—');
    await page.locator('#definir-meta').click();
    await page.locator('#meta-quantidade').fill('500');
    await page.locator('#salvar-meta').click();
    await page.waitForFunction(() => document.getElementById('meta').textContent === '500');
    assert.equal(await page.locator('#atingimento').innerText(), '60% da meta atingida');
    assert.equal(await page.locator('#saldo').innerText(), '-200');
    assert.equal(await page.locator('#eficiencia').innerText(), '60%');
    assert.equal(await page.locator('#produzido-mes').innerText(), '500');
    assert.equal(await page.locator('#meta-mes').innerText(), '500');
    assert.equal(await page.locator('#eficiencia-mes').innerText(), '—');
    assert.equal(await page.locator('#periodos tr').count(), 10);
    assert.match(await page.locator('#periodos').innerText(), /09:30/);
    assert.match(await page.locator('#periodos').innerText(), /13:30/);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    assert.equal(await page.evaluate(() => document.documentElement.scrollHeight <= innerHeight), true);
    assert.equal(await page.evaluate(() => document.querySelector('.board-table tfoot').getBoundingClientRect().bottom <= document.querySelector('.board-hourly').getBoundingClientRect().bottom), true);
    fs.mkdirSync('test-results', {recursive:true});
    await page.screenshot({path:'test-results/painel-tv-1920.png',fullPage:true});

    // Apontamento na rota real; aguarda a consulta automática refletir o banco.
    const save = await page.request.post('http://127.0.0.1:5051/api/lancamento/salvar', {
      data:{op_id:1,data:'2026-10-04',hora:'10:00',operadores:4,qtd_produzida:50,
            qtd_projetada:100,eficiencia:50,faturamento_hora:0,resultado_hora:0}
    });
    assert.equal((await save.json()).ok, true);
    await page.waitForFunction(() => document.getElementById('produzido').textContent === '350', {timeout:25000});
    assert.equal(await page.locator('#atingimento').innerText(), '70% da meta atingida');
    assert.equal(await page.locator('#saldo').innerText(), '-150');
    assert.equal(await page.locator('#eficiencia').innerText(), '70%');

    // Falha mantém dados anteriores identificados; retorno da conexão recupera.
    await page.route('**/api/painel-producao?*', route => route.abort());
    await page.evaluate(() => window.dispatchEvent(new Event('online')));
    await page.waitForFunction(() => !document.getElementById('aviso').hidden);
    assert.equal(await page.locator('#produzido').innerText(), '350');
    assert.match(await page.locator('#aviso').innerText(), /última consulta/);
    await page.unroute('**/api/painel-producao?*');
    await page.evaluate(() => window.dispatchEvent(new Event('online')));
    await page.waitForFunction(() => document.getElementById('aviso').hidden);

    await page.locator('#data').fill('2026-01-01');
    await page.locator('#data').dispatchEvent('change');
    await page.waitForFunction(() => document.getElementById('produzido').textContent === '0');
    assert.equal(await page.locator('#eficiencia').innerText(), '—');
    assert.equal(await page.locator('#meta').innerText(), '—');
    assert.match(await page.locator('#ops').innerText(), /Nenhum lançamento/);
    await page.locator('#data').fill('2026-10-04');
    await page.locator('#data').dispatchEvent('change');
    await page.waitForFunction(() => document.getElementById('produzido').textContent === '350');

    // Rodízio inclui todas as OPs, e textos cadastrados não executam HTML.
    await page.locator('#alternar-visao').click();
    await page.locator('.op-card').first().waitFor({state:'visible'});
    const response = await page.request.get('http://127.0.0.1:5051/api/painel-producao?data=2026-10-04');
    const fixture = await response.json();
    fixture.ops[0].descricao = '<img src=x onerror="window.injected=true">';
    const first = fixture.ops[0];
    for (let i=0;i<4;i++) fixture.ops.push({...first, op_id:10+i,numero:String(200+i)});
    await page.route('**/api/painel-producao?*', route => route.fulfill({json:fixture}));
    await page.evaluate(() => window.dispatchEvent(new Event('online')));
    await page.waitForFunction(() => document.getElementById('paginas').textContent.includes('6 OPs'));
    assert.equal(await page.evaluate(() => document.documentElement.scrollHeight <= innerHeight), true);
    await page.screenshot({path:'test-results/painel-tv-rodizio.png',fullPage:true});
    assert.equal(await page.locator('#ops img').count(), 0);
    assert.equal(await page.evaluate(() => window.injected), undefined);
    await page.waitForFunction(() => document.getElementById('paginas').textContent.includes('página 2/2'), {timeout:15000});
    assert.equal(await page.locator('.op-card').count(), 2);
    await page.unroute('**/api/painel-producao?*');
    await page.evaluate(() => window.dispatchEvent(new Event('online')));
    await page.waitForFunction(() => document.getElementById('paginas').textContent.includes('2 OPs'));
    await page.locator('#alternar-visao').click();

    await page.setViewportSize({width:1366,height:768});
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    assert.equal(await page.evaluate(() => document.documentElement.scrollHeight <= innerHeight), true);
    assert.equal(await page.evaluate(() => document.querySelector('.board-table tfoot').getBoundingClientRect().bottom <= document.querySelector('.board-hourly').getBoundingClientRect().bottom), true);
    await page.screenshot({path:'test-results/painel-tv-1366.png',fullPage:true});
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await page.screenshot({path:'test-results/painel-tv-mobile.png',fullPage:true});
    assert.deepEqual(errors, []);
    console.log('OK: painel de bordo, metas e eficiencia do dia/mes, horarios, apontamento online, conexao, filtros, OPs e layout.');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode=1; });
