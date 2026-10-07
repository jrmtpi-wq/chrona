const {chromium}=require('./test-results/browser-tools/node_modules/playwright');
const assert=require('node:assert/strict');
(async()=>{
  const browser=await chromium.launch({channel:'msedge',headless:true});
  try {
    const context=await browser.newContext({viewport:{width:1366,height:768},timezoneId:'America/Sao_Paulo'});
    const cadastro=await context.newPage();
    await cadastro.clock.install({time:new Date('2026-10-07T07:30:00-03:00')});
    await cadastro.goto('http://127.0.0.1:5052/test-login');
    await cadastro.request.post('http://127.0.0.1:5052/api/metas-op',{data:{op_id:1,turno_id:1,data:'2026-10-07',inicio:'2026-10-07T07:00',tempo_padrao:'18.5',operadores:'45',times:'12',ciclo:'15',eficiencia:'100',salvar:true}});
    await cadastro.goto('http://127.0.0.1:5052/lancamento');
    await cadastro.locator('#sel-op').selectOption('1');
    await cadastro.locator('#sel-turno').selectOption('1');
    await cadastro.getByRole('button',{name:'✅ Confirmar Seleção',exact:true}).click();
    await cadastro.getByRole('button',{name:'➕ Novo Lançamento',exact:true}).click();
    assert.equal(await cadastro.locator('#lan-hora').inputValue(),'08:00');
    const resposta=await cadastro.request.get('http://127.0.0.1:5052/api/painel-producao?data=2026-10-07');
    const payload=await resposta.json();
    for(const alvo of [payload.periodos,payload.entrada.periodos]){
      for(const hora of ['19:00','20:00'])alvo.push({hora,meta:0,produzido:0,saldo:null,eficiencia:null,lancamentos:0,pendente:true});
    }
    let falha=false, consultas=0;
    const tv=await context.newPage();
    const errors=[];tv.on('pageerror',e=>errors.push(e.message));
    await tv.clock.install({time:new Date('2026-10-07T11:30:00-03:00')});
    await tv.route('**/api/painel-producao?*',route=>{
      consultas++;
      return route.fulfill({status:falha?500:200,contentType:'application/json',body:JSON.stringify(payload)});
    });
    await tv.goto('http://127.0.0.1:5052/painel-producao?data=2026-10-07');
    await tv.waitForFunction(()=>document.querySelectorAll('#periodos tr').length===12);
    await tv.evaluate(()=>{
      window.mudancas=0;
      window.primeiraLinha=document.querySelector('#entrada-periodos tr');
      window.celula=document.querySelector('#entrada-periodos tr td:nth-child(3)');
      const observer=new MutationObserver(rs=>{window.mudancas+=rs.length;});
      observer.observe(document.querySelector('#entrada-painel'),{subtree:true,childList:true,characterData:true,attributes:true});
      observer.observe(document.querySelector('#saida-painel'),{subtree:true,childList:true,characterData:true,attributes:true});
    });
    for(let i=0;i<3;i++){
      const quantidade=consultas;
      const resposta=tv.waitForResponse(r=>r.url().includes('/api/painel-producao?'));
      await tv.clock.runFor(16000);
      await resposta;
      await tv.evaluate(()=>new Promise(resolve=>setTimeout(resolve,0)));
      await tv.waitForFunction(()=>document.getElementById('conexao').textContent.includes('Online'));
      assert(consultas>quantidade);
      assert.equal(await tv.evaluate(()=>window.mudancas),0,'Consulta sem mudanças redesenhou os indicadores');
      assert.equal(await tv.locator('#periodos tr').count(),12);
      assert.equal(await tv.locator('#entrada-periodos tr').count(),12);
    }
    payload.entrada.resumo.produzido=180;
    payload.entrada.acompanhamento.produzido=180;
    payload.entrada.periodos[0].produzido=180;
    payload.entrada.periodos[0].lancamentos=1;
    const alteracao=tv.waitForResponse(r=>r.url().includes('/api/painel-producao?'));
    await tv.clock.runFor(16000);
    await alteracao;
    await tv.waitForFunction(()=>document.getElementById('entrada-produzido').textContent==='180');
    assert(await tv.evaluate(()=>window.primeiraLinha===document.querySelector('#entrada-periodos tr')));
    assert(await tv.evaluate(()=>window.celula===document.querySelector('#entrada-periodos tr td:nth-child(3)')));
    assert.equal(await tv.locator('#produzido').innerText(),'0');
    falha=true;
    const respostaFalha=tv.waitForResponse(r=>r.url().includes('/api/painel-producao?'));
    await tv.clock.runFor(16000);
    await respostaFalha;
    await tv.locator('#aviso').waitFor();
    assert.equal(await tv.locator('#entrada-produzido').innerText(),'180');
    assert.equal(await tv.locator('#entrada-periodos tr').count(),12);
    assert.deepEqual(errors,[]);
    console.log('TV estável: três consultas e rodízios sem reconstruir números, todos os horários visíveis, alteração mantém células e falha preserva dados. Turno 07h sugere apontamento 08h.');
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
