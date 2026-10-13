const {chromium}=require(process.env.PLAYWRIGHT_MODULE || './test-results/browser-tools/node_modules/playwright');
const fs=require('node:fs');
const assert=require('node:assert/strict');
(async()=>{
  const browser=await chromium.launch({channel:'msedge',headless:true});
  try{
    const page=await browser.newPage();
    const errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    const html=fs.readFileSync('templates/jornada.html','utf8');
    const script=fs.readFileSync('static/jornada.js','utf8');
    await page.setContent(html.replace(/<script[^>]*>[\s\S]*?<\/script>/,'').replace(/{%[\s\S]*?%}/g,'').replace(/{{[\s\S]*?}}/g,''));
    await page.evaluate(()=>{
      window.rows=[
        {id:1,data:'2026-10-12',tipo:'FERIADO',minutos_disponiveis:540,hora_extra:1},
        {id:2,data:'2026-10-17',tipo:'SABADO',minutos_disponiveis:540},
        {id:3,data:'2026-10-10',tipo:'FOLGA',minutos_disponiveis:540}
      ];
      window.api=async(url,method,data)=>{
        if(!method)return window.rows;
        window.payload=data;
        return {ok:true,inseridos:0};
      };
      window.toast=()=>{};
      window.abrirModal=()=>{};
      window.fecharModal=()=>{};
      for(const id of ['g-turno','d-turno']) document.getElementById(id).innerHTML='<option value="1">Dia</option>';
      document.getElementById('g-fab').innerHTML='<option value="1">Fábrica</option>';
    });
    await page.addScriptTag({content:script});
    await page.waitForFunction(()=>document.getElementById('resumo-mes').textContent.includes('540'));
    assert.match(await page.locator('#resumo-mes').innerText(),/1 dias de trabalho por turno/);
    assert.equal(await page.locator('#tbody-jornada tr').count(),3);
    await page.evaluate(()=>{
      editarDia({id:2,data:'2026-10-17',turno_id:1,tipo:'SABADO',hora_entrada:'07:00',hora_saida_almoco:'12:00',hora_entrada_almoco:'13:00',hora_saida:'17:00',minutos_disponiveis:540});
    });
    assert.equal(await page.locator('#d-mins').inputValue(),'540');
    await page.locator('#d-tipo').selectOption('FOLGA');
    assert.equal(await page.locator('#d-mins').inputValue(),'0');
    await page.evaluate(()=>salvarDia());
    assert.equal(await page.evaluate(()=>Number(window.payload.minutos_disponiveis)),0);
    await page.locator('#d-tipo').selectOption('SABADO');
    assert.equal(await page.locator('#d-mins').inputValue(),'540');
    await page.locator('#g-mes').fill('2026-10');
    await page.locator('#g-feriados').fill('12');
    await page.locator('#g-sabados').fill('3, 17');
    await page.evaluate(()=>gerarMes());
    assert.equal(await page.evaluate(()=>window.payload.feriados),'12');
    assert.equal(await page.evaluate(()=>window.payload.sabados_trabalhados),'3, 17');
    assert.equal(await page.evaluate(()=>window.payload.include_sabado),false);
    assert.deepEqual(errors,[]);
    console.log('Jornada: resumo, folga, sábado e configuração mensal aprovados no navegador.');
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
