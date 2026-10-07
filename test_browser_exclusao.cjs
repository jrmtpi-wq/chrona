const {chromium} = require('./test-results/browser-tools/node_modules/playwright');
const assert = require('node:assert/strict');
(async () => {
  const browser = await chromium.launch({channel:'msedge',headless:true});
  try {
    const page = await browser.newPage({viewport:{width:1366,height:768}});
    const errors = []; page.on('pageerror', e => errors.push(e.message));
    await page.goto('http://127.0.0.1:5052/test-login');
    await page.goto('http://127.0.0.1:5052/cadastro-op');
    await page.waitForFunction(() => document.querySelectorAll('#tbody-ops button').length >= 6);
    assert.equal(await page.locator('#tbody-ops tr').count(), 2);
    await page.locator('#tbody-ops tr').filter({hasText:'101'}).getByRole('button',{name:'Editar',exact:true}).click();
    await page.locator('#op-quantidade').fill('1250');
    await page.locator('#op-valor-unit').fill('10');
    await page.locator('#op-data-entrega').fill('2026-10-20');
    await page.locator('#op-situacao').selectOption('PRODUCAO');
    await page.getByRole('button',{name:'💾 Salvar',exact:true}).click();
    await page.waitForFunction(() => !document.querySelector('#modal-op').classList.contains('open'));
    const op = await (await page.request.get('http://127.0.0.1:5052/api/op/1')).json();
    assert.equal(op.quantidade_total,1250); assert.equal(op.situacao,'PRODUCAO');
    // Cancelar o diálogo de exclusão preserva o registro.
    page.once('dialog', d => d.dismiss());
    await page.locator('#tbody-ops tr').filter({hasText:'101'}).getByRole('button',{name:'Excluir',exact:true}).click();
    assert.equal(await page.locator('#tbody-ops tr').count(),2);
    page.once('dialog', d => d.accept());
    await page.locator('#tbody-ops tr').filter({hasText:'101'}).getByRole('button',{name:'Excluir',exact:true}).click();
    await page.waitForFunction(() => document.querySelectorAll('#tbody-ops tr').length === 1);
    page.once('dialog', d => d.accept());
    await page.locator('#excluir-todas-ops').click();
    await page.getByText('Nenhuma OP encontrada').waitFor();
    await page.getByRole('button',{name:'＋ Nova OP',exact:true}).click();
    await page.locator('#op-numero').fill('REAL-100');
    await page.locator('#op-ref-codigo').fill('JEANS-01');
    await page.locator('#op-quantidade').fill('1500');
    await page.locator('#op-valor-unit').fill('10');
    await page.locator('#op-data-entrega').fill('2026-10-20');
    await page.locator('#op-fabrica').selectOption('1');
    await page.locator('#op-situacao').selectOption('PRODUCAO');
    await page.getByRole('button',{name:'💾 Salvar',exact:true}).click();
    await page.locator('#tbody-ops').getByText('REAL-100',{exact:true}).waitFor();
    assert.deepEqual(errors,[]);
    await page.screenshot({path:'test-results/ops-editar-excluir.png',fullPage:true});
    console.log('OPs aprovadas: editar, cancelar exclusão, excluir uma, excluir todas e cadastrar OP real depois.');
  } finally { await browser.close(); }
})().catch(e => {console.error(e);process.exit(1);});
