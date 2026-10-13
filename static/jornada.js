// Init mes atual
document.getElementById('filt-mes').value = new Date().toISOString().slice(0,7);
document.getElementById('g-mes').value = new Date().toISOString().slice(0,7);
carregarDias();

function hm(s){ if(!s)return 0; const[h,m]=s.split(':'); return parseInt(h)*60+parseInt(m); }

function calcDia(){
  const he=document.getElementById('d-he').value;
  const hsa=document.getElementById('d-hsa').value;
  const hea=document.getElementById('d-hea').value;
  const hs=document.getElementById('d-hs').value;
  let mins=0;
  const semTrabalho=['FERIADO','FOLGA','FERIAS'].includes(document.getElementById('d-tipo').value);
  const duracao=(inicio,fim)=>(hm(fim)-hm(inicio)+1440)%1440;
  if(he&&hs) mins=duracao(he,hs)-(hsa&&hea?duracao(hsa,hea):0);
  document.getElementById('d-mins').value=semTrabalho?0:Math.max(0,mins);
  if(semTrabalho) document.getElementById('d-hex').value='0';
}

function preencherHorarioTurno(){
  const sel=document.getElementById('d-turno');
  const opt=sel.options[sel.selectedIndex];
  if(!opt.value) return;
  document.getElementById('d-he').value=opt.dataset.he||'';
  document.getElementById('d-hsa').value=opt.dataset.hsa||'';
  document.getElementById('d-hea').value=opt.dataset.hea||'';
  document.getElementById('d-hs').value=opt.dataset.hs||'';
  document.getElementById('d-mins').value=opt.dataset.mins||0;
  calcDia();
}

async function gerarMes(){
  const mes=document.getElementById('g-mes').value;
  const turno=document.getElementById('g-turno').value;
  const fab=document.getElementById('g-fab').value;
  if(!mes||!turno){toast('Selecione mês e turno!','err');return}
  const r=await api('/api/jornada/gerar','POST',{
    mes,turno_id:turno,fabrica_id:fab,
    feriados:document.getElementById('g-feriados').value,
    sabados_trabalhados:document.getElementById('g-sabados').value,
    include_sabado:document.getElementById('g-sab').checked,
    include_domingo:document.getElementById('g-dom').checked
  });
  if(r.ok){
    toast(`✅ Calendário atualizado! ${r.inseridos} novos dias.`);
    fecharModal('modal-gerar');
    document.getElementById('filt-mes').value=mes;
    carregarDias();
  } else toast('Erro: '+r.erro,'err');
}

async function salvarDia(){
  const data=document.getElementById('d-data').value;
  const turno=document.getElementById('d-turno').value;
  if(!data||!turno){toast('Data e turno obrigatórios!','err');return}
  calcDia();
  const r=await api('/api/jornada/salvar','POST',{
    id:document.getElementById('d-id').value||null,
    data,turno_id:turno,
    tipo:document.getElementById('d-tipo').value,
    hora_entrada:document.getElementById('d-he').value,
    hora_saida_almoco:document.getElementById('d-hsa').value||null,
    hora_entrada_almoco:document.getElementById('d-hea').value||null,
    hora_saida:document.getElementById('d-hs').value,
    minutos_disponiveis:document.getElementById('d-mins').value,
    hora_extra:document.getElementById('d-hex').value,
    obs:document.getElementById('d-obs').value
  });
  if(r.ok){toast('Dia salvo!');fecharModal('modal-dia');carregarDias()}
  else toast('Erro: '+r.erro,'err');
}

function editarDia(d){
  document.getElementById('modal-dia-title').textContent='Editar Dia';
  document.getElementById('d-id').value=d.id;
  document.getElementById('d-data').value=d.data;
  document.getElementById('d-turno').value=d.turno_id;
  document.getElementById('d-tipo').value=d.tipo;
  document.getElementById('d-he').value=d.hora_entrada||'';
  document.getElementById('d-hsa').value=d.hora_saida_almoco||'';
  document.getElementById('d-hea').value=d.hora_entrada_almoco||'';
  document.getElementById('d-hs').value=d.hora_saida||'';
  document.getElementById('d-mins').value=d.minutos_disponiveis||0;
  document.getElementById('d-hex').value=d.hora_extra||0;
  document.getElementById('d-obs').value=d.obs||'';
  calcDia();
  abrirModal('modal-dia');
}

async function excluirDia(id){
  if(!confirm('Remover este dia?'))return;
  await api('/api/jornada/excluir/'+id,'DELETE');
  toast('Removido','warn');carregarDias();
}

const TIPO_CORES = {
  'NORMAL':'#E8F0FE','SABADO':'#FEF9E7','DOMINGO':'#FDEDEC',
  'FERIADO':'#FDEDEC','FOLGA':'#FDEDEC','FERIAS':'#FDEDEC','HORA EXTRA':'#EAFAF1'
};
const TIPO_TEXT = {
  'NORMAL':'var(--azul3)','SABADO':'var(--amar)','DOMINGO':'var(--verm)',
  'FERIADO':'var(--verm)','FOLGA':'var(--verm)','FERIAS':'var(--verm)','HORA EXTRA':'var(--verde)'
};

async function carregarDias(){
  const mes=document.getElementById('filt-mes').value;
  const turno=document.getElementById('filt-turno').value;
  let url='/api/jornada/lista?';
  if(mes) url+=`mes=${mes}&`;
  if(turno) url+=`turno_id=${turno}`;
  const rows=await api(url);
  const tb=document.getElementById('tbody-jornada');
  if(!rows.length){
    tb.innerHTML='<tr><td colspan="12" class="empty"><span class="empty-icon">📅</span>Nenhum dia cadastrado para este período</td></tr>';
    document.getElementById('resumo-mes').innerHTML='';
    return;
  }
  let totMins=0, totDias=0, totHE=0;
  tb.innerHTML=rows.map(r=>{
    const trabalhado=!['FERIADO','FOLGA','FERIAS'].includes(r.tipo)&&parseInt(r.minutos_disponiveis||0)>0;
    if(trabalhado){totMins+=parseInt(r.minutos_disponiveis||0);totDias++;}
    if(trabalhado&&r.hora_extra) totHE++;
    const bg=TIPO_CORES[r.tipo]||'#F8F9FA';
    const fg=TIPO_TEXT[r.tipo]||'var(--cinza)';
    const mins=trabalhado?parseInt(r.minutos_disponiveis||0):0;
    return `<tr>
      <td><strong>${r.data}</strong></td>
      <td style="color:var(--cinza)">${r.dia_semana||''}</td>
      <td><span style="font-size:11px;font-weight:600;color:var(--azul3)">${r.turno_nome}</span></td>
      <td><span class="tag" style="background:${bg};color:${fg}">${r.tipo}</span></td>
      <td>${r.hora_entrada||'—'}</td>
      <td>${r.hora_saida_almoco||'—'}</td>
      <td>${r.hora_entrada_almoco||'—'}</td>
      <td>${r.hora_saida||'—'}</td>
      <td><strong style="color:var(--azul)">${mins}min</strong>
          <span style="font-size:11px;color:var(--cinza)">(${Math.floor(mins/60)}h${mins%60}min)</span></td>
      <td>${r.hora_extra?'<span class="tag tag-ativo">SIM</span>':'<span style="color:var(--cinza)">—</span>'}</td>
      <td style="color:var(--cinza);font-size:12px">${r.obs||''}</td>
      <td>
        <div class="btn-group">
          <button class="btn btn-sm btn-primary" onclick='editarDia(${JSON.stringify(r)})'>✏️</button>
          <button class="btn btn-sm btn-danger" onclick="excluirDia(${r.id})">🗑</button>
        </div>
      </td>
    </tr>`;
  }).join('');

  const horas = Math.floor(totMins/60);
  const minRest = totMins%60;
  document.getElementById('resumo-mes').innerHTML=
    `<strong>${totDias}</strong> dias de trabalho por turno | <strong>${totMins}</strong> min total
     (<strong>${horas}h${minRest}min</strong>) | <strong>${totHE}</strong> dias hora extra`;
}
