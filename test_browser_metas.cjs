const {chromium}=require(process.env.PLAYWRIGHT_MODULE || './test-results/browser-tools/node_modules/playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
 const page=await browser.newPage({viewport:{width:1920,height:1080}});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 page.on('response',async r=>{if(r.status()>=400&&r.url().includes('/api/'))console.log(r.status(),r.request().postData(),await r.text());});
 await page.goto('http://127.0.0.1:5052/test-login');
 await page.getByText('Nenhuma OP programada. Salve a primeira OP para iniciar a fila.').waitFor();
 await page.locator('#op').selectOption('1');await page.locator('#turno').selectOption('1');
 await page.locator('#data').fill('2026-10-05');await page.locator('#inicio').fill('2026-10-05T07:00');
 for(const [k,v] of Object.entries({tempo_padrao:'18.5',operadores:'45',times:'12',ciclo:'15'}))await page.locator(`[name=${k}]`).fill(v);
 await page.getByRole('button',{name:'Salvar planejamento'}).click();
 await page.getByText('Programação salva. Datas da fila e metas da Gestão à vista atualizadas.').waitFor();
 assert.equal(await page.locator('#fila-programada tr').count(),1);
 await page.locator('#op').selectOption('2');
 assert.equal(await page.locator('#inicio').getAttribute('readonly'),'');
 for(const [k,v] of Object.entries({tempo_padrao:'18.5',operadores:'45',times:'12',ciclo:'20'}))await page.locator(`[name=${k}]`).fill(v);
 await page.getByRole('button',{name:'Salvar planejamento'}).click();
 await page.getByText('Programação salva. Datas da fila e metas da Gestão à vista atualizadas.').waitFor();
 assert.equal(await page.locator('#fila-programada tr').count(),2);
 let fila=await page.evaluate(async()=>await(await fetch('/api/metas-op/fila')).json());
 assert.equal(fila.fila[0].resultado.saida,fila.fila[1].resultado.entrada);
 const old=fila.fila[1].resultado.entrada;
 await page.locator('#fila-programada tr').first().getByRole('button',{name:'Editar'}).click();
 assert.equal(await page.locator('#inicio').getAttribute('readonly'),null);
 await page.locator('#data').fill('2026-10-07');await page.locator('#inicio').fill('2026-10-07T07:00');
 await page.getByRole('button',{name:'Salvar planejamento'}).click();
 await page.getByText('Programação salva. Datas da fila e metas da Gestão à vista atualizadas.').waitFor();
 fila=await page.evaluate(async()=>await(await fetch('/api/metas-op/fila')).json());
 assert.notEqual(fila.fila[1].resultado.entrada,old);
 assert.equal(fila.fila[0].resultado.saida,fila.fila[1].resultado.entrada);
 await page.goto('http://127.0.0.1:5052/painel-producao?data=2026-10-07');
 await page.waitForFunction(()=>document.getElementById('total-legenda').textContent==='Total planejado');
 assert.equal(await page.locator('#meta').innerText(),'876,7');
 assert.equal(await page.locator('#programacao-painel').isVisible(),true);
 assert.equal(await page.locator('#definir-meta').isVisible(),false);
 assert.equal(await page.locator('#periodos tr').count(),10);
 assert.equal(await page.locator('#periodos tr').filter({has:page.getByRole('rowheader',{name:'08:00',exact:true})}).locator('td').first().innerText(),'0');
 assert.equal(await page.locator('#periodos tr').filter({has:page.getByRole('rowheader',{name:'09:00',exact:true})}).locator('td').first().innerText(),'0');
 for(const [w,h]of [[1920,1080],[1366,768],[390,844]]){
  await page.setViewportSize({width:w,height:h});
  await page.screenshot({path:`test-results/metas-tv-${w}.png`,fullPage:true});
  assert(await page.locator('#total-meta').isVisible());
  const metrics=await page.evaluate(()=>({width:document.documentElement.scrollWidth,screen:innerWidth,tableBottom:document.querySelector('.board-table').getBoundingClientRect().bottom,height:innerHeight}));
  assert(metrics.width<=metrics.screen+1,JSON.stringify(metrics));
  if(w>1000)assert(metrics.tableBottom<=metrics.height,JSON.stringify(metrics));
 }
 assert.deepEqual(errors,[]);
 console.log('Navegador aprovado: salvar duas OPs, encadear datas, editar primeira OP, TV planejada e três tamanhos de tela.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
