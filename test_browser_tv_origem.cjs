const {chromium}=require('./test-results/browser-tools/node_modules/playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const context=await browser.newContext({timezoneId:'America/Sao_Paulo'});
  const page=await context.newPage();
  await page.goto('http://127.0.0.1:5052/test-login');
  assert.equal((await page.request.post('http://127.0.0.1:5052/api/metas-op',{data:{op_id:1,turno_id:1,data:'2026-10-07',inicio:'2026-10-07T07:00',tempo_padrao:'18.5',operadores:'45',times:'12',ciclo:'15',eficiencia:'100',salvar:true}})).status(),200);
  for(const [op_id,hora,qtd_produzida] of [[1,'09:00',120],[2,'08:30',140]]){
   const r=await page.request.post('http://127.0.0.1:5052/api/lancamento/salvar',{data:{op_id,data:'2026-10-07',hora,qtd_produzida,operadores:45,qtd_projetada:0,eficiencia:0,faturamento_hora:0,resultado_hora:0}});
   assert((await r.json()).ok);
  }
  await page.goto('http://127.0.0.1:5052/painel-producao?data=2026-10-07');
  const total=page.locator('#periodos button[data-hora="09:00"]');
  await total.waitFor();assert.equal(await total.innerText(),'260');await total.click();
  assert.equal(await page.locator('#realizado-registros tr').count(),2);
  const linhas=await page.locator('#realizado-registros').innerText();
  assert(linhas.includes('OP 101'));assert(linhas.includes('OP 102'));assert(linhas.includes('08:30'));assert(linhas.includes('140'));
  assert((await page.locator('#realizado-soma').innerText()).includes('260'));
  const popupPromise=page.waitForEvent('popup');
  await page.locator('#realizado-registros tr').filter({hasText:'OP 102'}).getByRole('link',{name:'Editar',exact:true}).click();
  const edit=await popupPromise;
  await edit.locator('#modal-lancar.open').waitFor();
  assert.equal(await edit.locator('#lan-qtd').inputValue(),'140');
  assert.equal(await edit.locator('#lan-hora').inputValue(),'08:30');
  assert.equal(await edit.locator('#lan-data').inputValue(),'2026-10-07');
  assert((await edit.locator('#lan-titulo').innerText()).includes('OP 102'));
  console.log('260 explicados por duas OPs: 120 às 09h e 140 às 08h30. Link Editar abre o registro correto.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
