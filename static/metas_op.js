const form=document.getElementById('plano'), opSelect=document.getElementById('op'), dia=document.getElementById('data'), turno=document.getElementById('turno'), inicio=document.getElementById('inicio'), mensagem=document.getElementById('mensagem'), resultado=document.getElementById('resultado');
const hoje=new Date(); dia.value=[hoje.getFullYear(),String(hoje.getMonth()+1).padStart(2,'0'),String(hoje.getDate()).padStart(2,'0')].join('-');
function sugerirInicio(){const t=turnos.find(t=>String(t.id)===turno.value);if(t&&dia.value) inicio.value=dia.value+'T'+t.hora_entrada;}
let versao=0;
async function carregar(){
 const atual=++versao; resultado.hidden=true; mensagem.textContent='';
 const op=ops.find(o=>String(o.id)===opSelect.value);
 document.getElementById('descricao').value=op?.descricao||'';document.getElementById('quantidade').value=op?.quantidade_total??'';
 for(const option of turno.options) option.hidden=!!option.value&&(!op||option.dataset.fabrica!==String(op.fabrica_id));
 if(turno.selectedOptions[0]?.hidden) turno.value='';
 for(const k of ['tempo_padrao','operadores','times','ciclo']) form.elements[k].value='';
 form.elements.eficiencia.value='100'; sugerirInicio();
 if(!op||!dia.value)return;
 try{const r=await fetch('/api/metas-op?'+new URLSearchParams({op_id:op.id,data:dia.value}));const d=await r.json();if(atual!==versao)return;if(!r.ok)throw Error(d.erro);if(d.plano){for(const [k,v] of Object.entries(d.plano))if(form.elements[k])form.elements[k].value=v;mensagem.textContent='Planejamento salvo carregado. Clique em Calcular para conferir as previsões atuais.';}}
 catch(e){if(atual===versao)mensagem.textContent=e.message;}
}
opSelect.addEventListener('change',carregar);dia.addEventListener('change',carregar);turno.addEventListener('change',sugerirInicio);
form.addEventListener('input',()=>{resultado.hidden=true;});
form.addEventListener('submit',async e=>{e.preventDefault();resultado.hidden=true;mensagem.textContent='Calculando…';const dados=Object.fromEntries(new FormData(form));dados.salvar=e.submitter?.value==='salvar';
 try{const r=await fetch('/api/metas-op',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(dados)});const d=await r.json();if(!r.ok)throw Error(d.erro);const v=d.resultado;const fmt=n=>n.toLocaleString('pt-BR',{maximumFractionDigits:2});const data=s=>new Date(s).toLocaleString('pt-BR');const itens=[['Minutos úteis do dia',fmt(v.minutos_dia)],['Meta diária (peças)',fmt(v.meta_dia)],['Meta por hora (peças)',fmt(v.meta_hora)],['Atravessamento (minutos úteis)',fmt(v.atravessamento)],['Entrada prevista',data(v.entrada)],['Primeira peça prevista',data(v.primeira_peca)],['Saída prevista',data(v.saida)]];const alvo=document.getElementById('valores');alvo.replaceChildren();for(const [titulo,valor]of itens){const box=document.createElement('div');const label=document.createElement('div');label.textContent=titulo;const strong=document.createElement('strong');strong.textContent=valor;box.append(label,strong);alvo.append(box);}resultado.hidden=false;mensagem.textContent=dados.salvar?'Planejamento salvo.':'Cálculo concluído.';}
 catch(e){mensagem.textContent=e.message;}
});
