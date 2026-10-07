const {chromium} = require('./test-results/browser-tools/node_modules/playwright');
const assert = require('node:assert/strict');
(async () => {
  const browser = await chromium.launch({channel:'msedge', headless:true});
  try {
    const context = await browser.newContext({viewport:{width:1920,height:1080}});
    const page = await context.newPage();
    const errors = []; page.on('pageerror', e => errors.push(e.message));
    await page.goto('http://127.0.0.1:5052/test-login');
    const existentes = await (await page.request.get('http://127.0.0.1:5052/api/entrada-grupo?data=2026-10-07')).json();
    for (const item of existentes) await page.request.delete(`http://127.0.0.1:5052/api/entrada-grupo/${item.id}`);
    await page.goto('http://127.0.0.1:5052/lancamento');
    await page.locator('#entrada-lancamento summary').click();
    await page.locator('#entrada-data').fill('2026-10-07');
    await page.locator('#entrada-op').selectOption('1');
    await page.locator('#entrada-hora').fill('08:00');
    await page.locator('#entrada-qtd').fill('150');
    await page.locator('#entrada-salvar').click();
    await page.getByText('Entrada salva. A TV atualiza automaticamente.').waitFor();
    assert.equal(await page.locator('#entrada-registros tr').count(), 1);
    const tv = await context.newPage();
    tv.on('pageerror', e => errors.push(e.message));
    await tv.goto('http://127.0.0.1:5052/painel-producao?data=2026-10-07');
    await tv.waitForFunction(() => document.getElementById('entrada-produzido').textContent === '150');
    assert.equal(await tv.locator('#produzido').innerText(), '0');
    await page.locator('#entrada-registros').getByRole('button', {name:'Editar'}).click();
    await page.locator('#entrada-qtd').fill('180');
    await page.locator('#entrada-salvar').click();
    await page.getByText('Entrada salva. A TV atualiza automaticamente.').waitFor();
    await tv.waitForFunction(() => document.getElementById('entrada-produzido').textContent === '180', {timeout:25000});
    for (const [width,height] of [[1920,1080],[1366,768],[390,844]]) {
      await tv.setViewportSize({width,height});
      const layout = await tv.evaluate(() => {
        const entrada = document.querySelector('#entrada-painel').getBoundingClientRect();
        const saida = document.querySelector('#saida-painel').getBoundingClientRect();
        const program = document.querySelector('#programacao-painel').getBoundingClientRect();
        return {overflow:document.documentElement.scrollWidth > innerWidth,
          beside:entrada.right <= saida.left, stacked:entrada.bottom <= saida.top,
          separated:document.querySelector('.board-layout').getBoundingClientRect().bottom <= program.top,
          footerAfterContent:document.querySelector('footer').getBoundingClientRect().top >= document.querySelector('main').getBoundingClientRect().bottom};
      });
      assert(!layout.overflow, JSON.stringify(layout));
      assert(width > 1000 ? layout.beside : layout.stacked, JSON.stringify(layout));
      assert(layout.separated, JSON.stringify(layout));
      assert(layout.footerAfterContent, JSON.stringify(layout));
      await tv.screenshot({path:`test-results/entrada-saida-${width}.png`,fullPage:true});
    }
    page.once('dialog', d => d.accept());
    await page.locator('#entrada-registros').getByRole('button', {name:'Excluir'}).click();
    await page.getByText('Entrada excluída.').waitFor();
    assert.deepEqual(errors, []);
    console.log('Entrada e saída aprovadas: inclusão, edição, atualização automática, exclusão e layouts em três telas.');
  } finally { await browser.close(); }
})().catch(e => {console.error(e);process.exit(1);});
