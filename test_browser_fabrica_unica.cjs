const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
(async () => {
  const browser = await chromium.launch({channel:'msedge',headless:true});
  try {
    const page = await browser.newPage({viewport:{width:1920,height:1080}});
    const errors = [];
    page.on('pageerror',e => errors.push(e.message));
    await page.goto('http://127.0.0.1:5051/test-login');
    await page.waitForFunction(() => document.getElementById('produzido').textContent === '1.299');
    assert.equal(await page.locator('#fabrica-nome').innerText(),'JTMTPI CONFECÇÕES');
    assert.equal(await page.locator('#fabrica').isVisible(),false);
    await page.goto('http://127.0.0.1:5051/usuarios');
    assert.match(await page.locator('.sid-logo').innerText(),/JTMTPI CONFECÇÕES/);
    await page.evaluate(() => resetForm());
    assert.equal(await page.locator('#u-fabrica').inputValue(),'1');
    assert.equal(await page.locator('#grupo-fabrica').isVisible(),false);
    const saved = await page.request.post('http://127.0.0.1:5051/api/usuarios/salvar',{
      data:{nome:'Operador Teste',login:'operador-teste',senha:'senha-de-teste',perfil:'operador'}
    });
    assert.equal((await saved.json()).ok,true);
    assert.deepEqual(errors,[]);
    console.log('Painel consolidado, marca, seleção automática e novo usuário: OK');
  } finally { await browser.close(); }
})().catch(e => {console.error(e);process.exit(1);});
