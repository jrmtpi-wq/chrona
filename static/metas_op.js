(() => {
'use strict';
const form=document.getElementById('plano'), opSelect=document.getElementById('op'), dia=document.getElementById('data'), turno=document.getElementById('turno'), inicio=document.getElementById('inicio'), mensagem=document.getElementById('mensagem'), resultado=document.getElementById('resultado');
const fmt=n=>Number(n).toLocaleString('pt-BR',{maximumFractionDigits:2});
const data=s=>new Date(s).toLocaleString('pt-BR');
function preencherInicio(s){inicio.value=s.slice(0,23);dia.value=s.slice(0,10);}
let fila=[], original=null, carregando=false, versao=0;
const referenciaInicio=document.getElementById('referencia-inicio');
function atualizarReferencia(){document.getElementById('inicio-label').textContent=referenciaInicio.value==='primeira_peca'?'Primeira peça pronta na saída':'Entrada no primeiro time';}
referenciaInicio.addEventListener('change',()=>{versao++;resultado.hidden=true;atualizarReferencia();});
const hoje=new Date();
dia.value=[hoje.getFullYear(),String(hoje.getMonth()+1).padStart(2,'0'),String(hoje.getDate()).padStart(2,'0')].join('-');
function filaDaOp(){const op=ops.find(o=>String(o.id)===opSelect.value);return fila.filter(i=>i.plano.fabrica_id===op?.fabrica_id);}
function ajustarInicio(){
 const lista=filaDaOp();const indice=original?lista.findIndex(i=>i.plano.op_id===Number(opSelect.value)&&i.plano.data===original):lista.length;
 const automatico=indice>0;dia.readOnly=automatico;inicio.readOnly=automatico;
 referenciaInicio.disabled=automatico;if(automatico)referenciaInicio.value='entrada';atualizarReferencia();
 document.getElementById('sequencia-nota').textContent=automatico?'Entrada automática quando a OP anterior termina no primeiro time. A próxima já atravessa os times antes da última peça da anterior sair.':'Esta é a primeira OP: informe o início da programação.';
 if(automatico){const item=lista[indice];const anterior=lista[indice-1];if(item)preencherInicio(item.resultado.entrada);else if(anterior)preencherInicio(anterior.resultado.fim_entrada);}
 else if(!original){const t=turnos.find(t=>String(t.id)===turno.value);if(t&&dia.value)inicio.value=dia.value+'T'+t.hora_entrada;}
}
function mostrarResultado(v){const itens=[['Minutos úteis do dia',fmt(v.minutos_dia)],['Capacidade diária (peças)',fmt(v.meta_dia)],['Meta por hora (peças)',fmt(v.meta_hora)],['Atravessamento (minutos úteis)',fmt(v.atravessamento)],['Entrada prevista',data(v.entrada)],['Primeira peça prevista',data(v.primeira_peca)],['Saída prevista',data(v.saida)]];
 const alvo=document.getElementById('valores');alvo.replaceChildren();for(const [titulo,valor]of itens){const box=document.createElement('div'),label=document.createElement('div'),strong=document.createElement('strong');label.textContent=titulo;strong.textContent=valor;box.append(label,strong);alvo.append(box);}resultado.hidden=false;
}
function mostrarFila(){const alvo=document.getElementById('fila-programada');alvo.replaceChildren();for(const item of fila){const tr=document.createElement('tr');for(const valor of [item.ordem,item.plano.numero+' — '+(item.plano.descricao||''),fmt(item.plano.quantidade_total),data(item.resultado.entrada),data(item.resultado.primeira_peca),data(item.resultado.saida)]){const td=document.createElement('td');td.textContent=valor;tr.append(td);}const td=document.createElement('td'),button=document.createElement('button');button.type='button';button.className='btn btn-sm btn-primary';button.textContent='Editar';button.addEventListener('click',()=>{opSelect.value=String(item.plano.op_id);carregar(item);form.scrollIntoView({behavior:'smooth'});});td.append(button);tr.append(td);alvo.append(tr);}if(!fila.length){const tr=document.createElement('tr'),td=document.createElement('td');td.colSpan=7;td.textContent='Nenhuma OP programada. Salve a primeira OP para iniciar a fila.';tr.append(td);alvo.append(tr);}}
function carregar(item=null){
 referenciaInicio.value='entrada';atualizarReferencia();
 versao++;resultado.hidden=true;mensagem.textContent='';const op=ops.find(o=>String(o.id)===opSelect.value);
 document.getElementById('descricao').value=op?.descricao||'';document.getElementById('quantidade').value=op?.quantidade_total??'';
 for(const option of turno.options)option.hidden=!!option.value&&(!op||option.dataset.fabrica!==String(op.fabrica_id));
 if(turno.selectedOptions[0]?.hidden)turno.value='';
 for(const k of ['tempo_padrao','operadores','times','ciclo'])form.elements[k].value='';form.elements.eficiencia.value='100';
 item=item||fila.find(i=>i.plano.op_id===op?.id);original=item?.plano.data||null;
 if(item){for(const k of ['tempo_padrao','operadores','times','ciclo','eficiencia','turno_id'])form.elements[k].value=item.plano[k];preencherInicio(item.resultado.entrada);}
 ajustarInicio();
}
async function atualizarFila(){carregando=true;try{const r=await fetch('/api/metas-op/fila',{cache:'no-store'}),d=await r.json();if(!r.ok)throw Error(d.erro);fila=d.fila;mostrarFila();document.getElementById('fila-erro').textContent='';carregar();}catch(e){document.getElementById('fila-erro').textContent=e.message;}finally{carregando=false;}}
opSelect.addEventListener('change',()=>carregar());dia.addEventListener('change',ajustarInicio);turno.addEventListener('change',ajustarInicio);
form.addEventListener('input',()=>{versao++;resultado.hidden=true;});
form.addEventListener('submit',async e=>{e.preventDefault();if(carregando)return;const atual=versao;resultado.hidden=true;mensagem.textContent='Calculando…';const dados=Object.fromEntries(new FormData(form));dados.salvar=e.submitter?.value==='salvar';if(original)dados.data_original=original;
 const buttons=[...form.querySelectorAll('button')];buttons.forEach(b=>b.disabled=true);
 try{const r=await fetch('/api/metas-op',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(dados)}),d=await r.json();if(!r.ok)throw Error(d.erro);if(atual!==versao){if(dados.salvar)await atualizarFila();return;}if(dados.salvar){await atualizarFila();original=d.data_original;carregar(fila.find(i=>i.plano.op_id===Number(dados.op_id)&&i.plano.data===original));}referenciaInicio.value='entrada';atualizarReferencia();preencherInicio(d.resultado.entrada);mostrarResultado(d.resultado);mensagem.textContent=dados.salvar?'Programação salva. Datas da fila e metas da Gestão à vista atualizadas.':'Prévia calculada. Salve para aplicar à programação e à Gestão à vista.';}
 catch(e){mensagem.textContent=e.message;}finally{buttons.forEach(b=>b.disabled=false);}
});
atualizarFila();

})();
