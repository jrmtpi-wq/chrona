const {chromium}=require('./test-results/browser-tools/node_modules/playwright');
const assert=require('node:assert/strict');
(async()=>{
  const browser=await chromium.launch({channel:'msedge',headless:true});
  try {
    const context=await browser.newContext({timezoneId:'America/Sao_Paulo'});
    const page=await context.newPage();
    await page.goto('http://127.0.0.1:5052/test-login');
    await page.goto('http://127.0.0.1:5052/lancamento');
    await page.locator('#sel-op').selectOption('1');
    await page.locator('#sel-turno').selectOption('1');
    await page.locator('#sel-data').fill('2026-10-06');
    await page.evaluate(()=>confirmarSelecao());
    let requests=0;
    await page.route('**/api/lancamento/salvar',async route=>{
      requests++;
      await new Promise(resolve=>setTimeout(resolve,150));
      await route.continue();
    });
    async function save(date,hour){
      await page.evaluate(()=>abrirModalLancar());
      await page.locator('#lan-data').fill(date);
      await page.locator('#lan-hora').fill(hour);
      await page.locator('#lan-qtd').fill('120');
      const response=page.waitForResponse(r=>r.url().endsWith('/api/lancamento/salvar'));
      await page.evaluate(()=>{salvarLancamento();salvarLancamento();});
      assert.equal((await response).status(),200);
      await page.waitForFunction(()=>!salvandoLancamento);
    }
    for(const hour of ['15:30','16:30','17:30'])await save('2026-10-06',hour);
    for(const hour of ['08:00','09:00','10:00','11:00','12:00'])await save('2026-10-07',hour);
    assert.equal(requests,8,'Double invocation sent duplicate saves');
    const records=async date=>(await page.request.get('http://127.0.0.1:5052/api/lancamentos?op_id=1&data='+date)).json();
    assert.deepEqual((await records('2026-10-06')).map(r=>r.hora),['15:30','16:30','17:30']);
    let today=await records('2026-10-07');
    assert.deepEqual(today.map(r=>r.hora),['08:00','09:00','10:00','11:00','12:00']);
    await page.evaluate(id=>editarLancamento(id),today.find(r=>r.hora==='11:00').id);
    await page.locator('#lan-data').fill('2026-10-06');
    await page.locator('#lan-salvar').click();
    await page.waitForFunction(()=>!salvandoLancamento);
    assert.equal((await records('2026-10-07')).length,4);
    assert.equal((await records('2026-10-06')).length,4);
    console.log('Datas 06/07 isoladas, horários preservados, clique repetido salva uma vez e edição corrige data.');
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
