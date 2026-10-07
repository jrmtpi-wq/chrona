const {chromium}=require('./test-results/browser-tools/node_modules/playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const context=await browser.newContext({timezoneId:'America/Sao_Paulo'});
  const page=await context.newPage();
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:5052/test-login');
  for(const op_id of [1,2]){
   const r=await page.request.post('http://127.0.0.1:5052/api/metas-op',{data:{op_id,turno_id:1,data:'2026-10-06',inicio:'2026-10-06T07:00',tempo_padrao:'18.5',operadores:'45',times:'12',ciclo:'15',eficiencia:'100',salvar:true}});
   assert.equal(r.status(),200);
  }
  const payload=await (await page.request.get('http://127.0.0.1:5052/api/painel-producao?data=2026-10-07')).json();
  for(const list of [payload.periodos,payload.entrada.periodos]){
   for(const hora of ['19:00','20:00'])list.push({hora,meta:140,produzido:0,saldo:null,eficiencia:null,lancamentos:0,pendente:true});
  }
  assert(payload.programacao.length>=2);
  await page.route('**/api/painel-producao?*',route=>route.fulfill({contentType:'application/json',body:JSON.stringify(payload)}));
  await page.goto('http://127.0.0.1:5052/painel-producao?data=2026-10-07');
  await page.waitForFunction(()=>document.querySelectorAll('#periodos tr').length===12);
  for(const [width,height] of [[1920,1080],[1366,768],[1280,720],[1280,600],[1024,600]]){
   await page.setViewportSize({width,height});
   const layout=await page.evaluate(()=>{
    const rect=selector=>{const r=document.querySelector(selector).getBoundingClientRect();return {top:r.top,bottom:r.bottom,left:r.left,right:r.right};};
    return {width:innerWidth,height:innerHeight,scrollHeight:document.documentElement.scrollHeight,scrollWidth:document.documentElement.scrollWidth,
     month:rect('.monthly'),monthTotal:rect('#produzido-mes'),program:rect('#programacao-painel'),footer:rect('footer'),
     panes:['#entrada-painel','#saida-painel'].map(s=>({table:rect(s+' .board-table'),last:rect(s+' tbody tr:last-child'),total:rect(s+' tfoot'),cards:rect(s+' .metrics')})),
     notes:[...document.querySelectorAll('.flow-pane .metric small')].map(e=>({bottom:e.getBoundingClientRect().bottom,parentBottom:e.closest('.metric').getBoundingClientRect().bottom}))};
   });
   assert(layout.scrollWidth<=width+1,JSON.stringify(layout));
   assert(layout.scrollHeight<=height+1,JSON.stringify(layout));
   assert(layout.month.bottom<=height,JSON.stringify(layout));
   assert(layout.monthTotal.bottom<=height,JSON.stringify(layout));
   assert(layout.footer.bottom<=height,JSON.stringify(layout));
   assert(layout.program.bottom<=layout.month.top,JSON.stringify(layout));
   for(const pane of layout.panes){assert(pane.last.bottom<=pane.total.top+1,JSON.stringify(layout));assert(pane.table.bottom<=pane.cards.top+1,JSON.stringify(layout));}
   for(const note of layout.notes)assert(note.bottom<=note.parentBottom+1,JSON.stringify(layout));
   await page.screenshot({path:`test-results/tv-completa-${width}x${height}.png`});
  }
  await page.locator('.tv-controls summary').click();
  assert(await page.locator('#data').isVisible());
  assert(await page.getByRole('link',{name:'Programação das OPs'}).isVisible());
  await page.locator('#alternar-visao').click();
  assert(await page.locator('.body-grid').isVisible());
  await page.locator('#alternar-visao').click();
  await page.locator('.tv-controls summary').click();
  await page.setViewportSize({width:390,height:844});
  assert(await page.locator('#produzido-mes').isVisible());
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  assert.deepEqual(errors,[]);
  console.log('TV completa sem rolagem em cinco tamanhos, 12 horários, OPs e acumulado mensal visíveis; controles e modo OP funcionam, celular sem corte horizontal.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
