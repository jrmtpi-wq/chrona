'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const htmlAtual = new WeakMap();
  function setText(id, value) {
    const element = $(id), text = String(value);
    if (element.textContent !== text) element.textContent = text;
  }
  function setClass(id, value) {
    if ($(id).className !== value) $(id).className = value;
  }
  function atualizarFilhos(element, novos) {
    [...novos.childNodes].forEach((novo, index) => {
      const atual = element.childNodes[index];
      if (!atual) { element.append(novo.cloneNode(true)); return; }
      if (atual.nodeType !== novo.nodeType || atual.nodeName !== novo.nodeName) {
        atual.replaceWith(novo.cloneNode(true)); return;
      }
      if (novo.nodeType === Node.TEXT_NODE) {
        if (atual.nodeValue !== novo.nodeValue) atual.nodeValue = novo.nodeValue;
      } else if (novo.nodeType === Node.ELEMENT_NODE) {
        for (const attr of [...atual.attributes]) if (!novo.hasAttribute(attr.name)) atual.removeAttribute(attr.name);
        for (const attr of [...novo.attributes]) if (atual.getAttribute(attr.name) !== attr.value) atual.setAttribute(attr.name, attr.value);
        atualizarFilhos(atual, novo);
      }
    });
    while (element.childNodes.length > novos.childNodes.length) element.lastChild.remove();
  }
  function setHtml(id, html) {
    const element = $(id);
    if (htmlAtual.get(element) === html && (!html || element.hasChildNodes())) return;
    const range = document.createRange();
    range.selectNodeContents(element);
    atualizarFilhos(element, range.createContextualFragment(html));
    htmlAtual.set(element, html);
  }
  const n = value => Number(value || 0).toLocaleString('pt-BR', {maximumFractionDigits: 1});
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const percent = value => value === null ? '—' : `${n(value)}%`;
  const color = ef => ef === null ? '' : ef < 85 ? 'red' : ef < 92 ? 'amber' : ef <= 100 ? 'green' : 'blue';
  const time = value => new Date(value).toLocaleTimeString('pt-BR', {timeZone:'America/Sao_Paulo',hour:'2-digit',minute:'2-digit',second:'2-digit'});
  let data = null, page = 0, hourPage = 0, timer, busy = false, again = false;
  let selectedDate = new URLSearchParams(location.search).get('data') || '';
  let selectedFactory = new URLSearchParams(location.search).get('fabrica_id') || '';
  let lastSuccess = null;
  let metaContext = null;
  const signed = value => value === null ? '—' : `${value > 0 ? '+' : ''}${n(value)}`;
  function renderEntrada() {
    const entrada = data.entrada;
    if (!entrada) return;
    const periods = new Map(entrada.periodos.map(p => [p.hora, p]));
    const defaults = ['08:00','09:00','10:00','11:00','13:30','14:30','15:30','16:30','17:30'];
    const times = [...new Set([...(entrada.fonte_meta === 'programacao' ? [] : defaults), ...periods.keys()])].sort();
    setText('entrada-contagem', `${n(entrada.resumo.lancamentos)} apontamentos`);
    setHtml('entrada-periodos', times.map(h => {
      const p = periods.get(h), pending = !p || p.pendente;
      return `<tr class="${pending ? 'pending' : ''}"><th scope="row">${escape(h)}</th><td>${p ? n(p.meta) : '—'}</td><td>${p && (!pending || p.lancamentos) ? n(p.produzido) : '—'}</td><td class="${pending ? '' : p.saldo < 0 ? 'red' : 'green'}">${pending ? '—' : signed(p.saldo)}</td><td class="${pending ? '' : color(p.eficiencia)}">${pending ? '—' : percent(p.eficiencia)}</td></tr>`;
    }).join(''));
    const atual = entrada.acompanhamento;
    setText('entrada-meta', n(entrada.resumo.meta));
    setText('entrada-produzido', n(atual.produzido));
    setText('entrada-saldo', signed(atual.saldo));
    setText('entrada-eficiencia', percent(atual.eficiencia));
    setClass('entrada-ef-card', `metric ${color(atual.eficiencia)}`);
    setText('entrada-total-meta', n(atual.meta));
    setText('entrada-total-realizado', n(atual.produzido));
    setText('entrada-total-saldo', signed(atual.saldo));
    setText('entrada-total-eficiencia', percent(atual.eficiencia));
  }
  function renderPeriods() {
    if (!data) return;
    const defaults = ['08:00','09:00','10:00','11:00','13:30','14:30','15:30','16:30','17:30'];
    const periods = new Map(data.periodos.map(p => [p.hora,p]));
    const times = [...new Set([...(data.fonte_meta === 'programacao' ? [] : defaults),...periods.keys()])].sort();
    setText('periodos-pagina', `${n(data.resumo.lancamentos)} apontamentos${data.fonte_meta === 'programacao' ? ' · jornada completa' : ''}`);
    setHtml('periodos', times.map(h => {
      const p = periods.get(h);
      const pending = !p || p.pendente;
      return `<tr class="${pending ? 'pending' : ''}"><th scope="row">${escape(h)}</th><td>${p ? n(p.meta) : '—'}</td><td>${p && (!pending || p.lancamentos) ? n(p.produzido) : '—'}</td><td class="${pending ? '' : p.saldo < 0 ? 'red' : 'green'}">${pending ? '—' : signed(p.saldo)}</td><td class="${pending ? '' : color(p.eficiencia)}">${pending ? '—' : percent(p.eficiencia)}</td></tr>`;
    }).join(''));
    const total = data.acompanhamento || data.resumo;
    setText('total-meta', n(total.meta));
    setText('total-legenda', data.acompanhamento ? 'Total até o horário' : 'Total apontado');
    setText('total-realizado', n(total.produzido));
    setText('total-saldo', signed(total.saldo));
    setText('total-eficiencia', percent(total.eficiencia));
  }

  function renderOps() {
    if (!data) return;
    const pageSize = window.matchMedia('(min-width:1001px) and (max-height:850px)').matches ? 2 : 4;
    const pages = Math.max(1, Math.ceil(data.ops.length / pageSize));
    page %= pages;
    setText('paginas', data.ops.length ? `${data.ops.length} OPs · página ${page + 1}/${pages}` : '');
    setHtml('ops', data.ops.length ? data.ops.slice(page * pageSize, page * pageSize + pageSize).map(o => {
      const progress = o.quantidade > 0 ? Math.min(100, Math.max(0, o.acumulado / o.quantidade * 100)) : 0;
      return `<article class="op-card ${color(o.eficiencia)}"><div class="op-head"><strong>OP ${escape(o.numero)}</strong><span class="pill">${percent(o.eficiencia)}</span></div>
        <div class="op-ref" title="${escape(o.descricao)}">${escape(o.referencia || 'Sem referência')} · ${escape(o.descricao)}</div>
        <div class="op-numbers"><div><strong>${n(o.produzido)}</strong><span>produzido hoje</span></div><div><strong>${n(o.meta)}</strong><span>${data.fonte_meta === 'programacao' ? 'meta planejada' : 'meta apontada'}</span></div></div>
        <div class="progress"><span style="width:${progress}%"></span></div>
        <div class="op-progress"><span>${n(o.acumulado)} / ${n(o.quantidade)} peças na OP</span><span>${n(o.restante)} restantes</span></div></article>`;
    }).join('') : '<div class="empty">Nenhum lançamento nesta data.<br>Os apontamentos salvos aparecerão aqui automaticamente.</div>');
    const hpages = Math.max(1, Math.ceil(data.horas.length / 8));
    hourPage %= hpages;
    const max = Math.max(1, ...data.horas.flatMap(h => [h.produzido, h.meta]));
    setHtml('horas', data.horas.length ? data.horas.slice(hourPage * 8, hourPage * 8 + 8).map(h =>
      `<div class="hour-row"><strong>${escape(h.hora)}</strong><div class="hour-bars"><div class="bar" style="width:${Math.max(0,h.produzido / max * 100)}%"></div><div class="bar target" style="width:${Math.max(0,h.meta / max * 100)}%"></div></div><div class="hour-values">${n(h.produzido)} / ${n(h.meta)}</div></div>`
    ).join('') : '<div class="empty">Aguardando apontamentos</div>');
  }

  function render() {
    document.body.classList.toggle('has-program',data.fonte_meta === 'programacao');
    const factories = data.fabricas.map(f => `<option value="${Number(f.id)}">${escape(f.nome)}</option>`).join('');
    setHtml('fabrica', factories || '<option value="">Sem fábrica disponível</option>');
    $('fabrica').value = data.fabrica_id ?? '';
    $('fabrica').closest('label').hidden = data.fabricas.length === 1;
    selectedFactory = String(data.fabrica_id ?? '');
    setText('fabrica-nome', data.fabricas.find(f => f.id === data.fabrica_id)?.nome || 'Produção da fábrica');
    $('data').value = data.data;
    const day = new Date(`${data.data}T12:00:00-03:00`).toLocaleDateString('pt-BR', {timeZone:'America/Sao_Paulo',weekday:'long',day:'2-digit',month:'long',year:'numeric'});
    setText('dia-legenda', day);
    setText('produzido', n(data.acompanhamento ? data.acompanhamento.produzido : data.resumo.produzido));
    setText('meta', data.meta_dia.quantidade === null ? '—' : n(data.meta_dia.quantidade));
    setText('atingimento', data.meta_dia.quantidade === null ? 'Meta ainda não definida' : `${percent(data.meta_dia.atingimento)} da meta atingida`);
    setText('previsao-dia', data.previsao_dia ? `Previsão atualizada: ${n(data.previsao_dia.quantidade)} peças no dia` : '');
    $('definir-meta').hidden = !data.pode_editar_meta || data.fabrica_id === null;
    setText('definir-meta', data.meta_dia.quantidade === null ? 'Definir meta do dia' : 'Editar meta do dia');
    if (data.acompanhamento) {
      const atual = data.acompanhamento;
      setText('saldo', signed(atual.saldo));
      setText('meta-apontada', `realizado − meta até o horário (${n(atual.meta)} peças)`);
      setText('eficiencia', percent(atual.eficiencia));
      setClass('ef-card', `metric ${color(atual.eficiencia)}`);
      setText('farol', 'realizado ÷ meta até o horário');
    } else {
      setText('eficiencia', percent(data.meta_dia.atingimento));
      setClass('ef-card', `metric ${color(data.meta_dia.atingimento)}`);
      setText('saldo', data.meta_dia.quantidade === null ? '—' : signed(data.resumo.produzido - data.meta_dia.quantidade));
      setText('meta-apontada', data.meta_dia.faltam === null ? 'realizado − meta do dia' : data.meta_dia.faltam === 0 ? 'Meta do dia atingida!' : `Faltam ${n(data.meta_dia.faltam)} peças`);
      setText('farol', data.meta_dia.atingimento === null ? 'Defina a meta do dia' : 'realizado ÷ meta do dia');
    }
    const programacao=data.programacao||[];
    $('programacao-painel').hidden=!programacao.length;
    const previsao=s=>new Date(s).toLocaleString('pt-BR',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'});
    const inicioProgramacao=(page % Math.max(1,Math.ceil(programacao.length/2)))*2;
    setHtml('programacao-itens', programacao.slice(inicioProgramacao,inicioProgramacao+2).map(p=>`<article><strong>OP ${escape(p.numero)} · ${escape(p.descricao||'')} · Meta ${n(p.meta)}</strong><span>Planejado: entrada ${escape(previsao(p.entrada))} · 1ª peça ${escape(previsao(p.primeira_peca))} · saída ${escape(previsao(p.saida))}</span>${p.previsao ? `<span>Previsão atual: entrada ${escape(previsao(p.previsao.entrada))} · saída ${escape(previsao(p.previsao.saida))} · ${n(p.restante_atual)} peças restantes</span>` : ''}</article>`).join(''));
    setText('meta-mes', data.mes.meta === null ? '—' : n(data.mes.meta));
    setText('produzido-mes', n(data.mes.produzido));
    setText('eficiencia-mes', percent(data.mes.eficiencia));
    setClass('eficiencia-mes', color(data.mes.eficiencia));
    setText('mes-legenda', `De 01/${data.data.slice(5,7)} até ${data.data.split('-').reverse().join('/')}`);
    setText('mes-nota', data.mes.dias_sem_meta ? `${n(data.mes.dias_sem_meta)} dia(s) apontado(s) sem meta cadastrada` : 'realizado ÷ meta do mês');
    setText('contagem', `${n(data.resumo.lancamentos)} lançamentos na data`);
    setHtml('recentes', data.recentes.length ? data.recentes.map(r =>
      `<article class="recent-item"><span class="time">${escape(r.hora)} · OP ${escape(r.numero)}</span><strong>${n(r.produzido)} <small class="muted">peças</small></strong><span>Meta ${n(r.meta)} · <b class="${color(r.eficiencia)}">${percent(r.eficiencia)}</b></span></article>`
    ).join('') : '<div class="empty">Nenhum período apontado</div>');
    renderOps();
    renderPeriods();
    renderEntrada();
  }

  async function refresh() {
    if (busy) { again = true; return; }
    clearTimeout(timer);
    busy = true;
    const params = new URLSearchParams();
    if (selectedDate) params.set('data', selectedDate);
    if (selectedFactory) params.set('fabrica_id', selectedFactory);
    const signature = `${selectedDate}|${selectedFactory}`;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    try {
      const response = await fetch(`/api/painel-producao?${params}`, {cache:'no-store',signal:controller.signal});
      if (signature !== `${selectedDate}|${selectedFactory}`) { again = true; return; }
      if (response.status === 401) throw new Error('Sessão encerrada. Volte ao Lançamento e entre novamente.');
      if (!response.ok) throw new Error('Não foi possível consultar os dados. Confira a conexão e a fábrica selecionada.');
      const next = await response.json();
      if (signature !== `${selectedDate}|${selectedFactory}`) { again = true; return; }
      data = next;
      lastSuccess = Date.now();
      render();
      $('aviso').hidden = true;
      setText('conexao', '● Online · consulta automática');
      setClass('conexao', 'green');
      setText('atualizacao', `Última consulta: ${time(data.atualizado_em)}`);
      const url = new URL(location.href);
      if (selectedFactory) url.searchParams.set('fabrica_id', selectedFactory);
      if (selectedDate) url.searchParams.set('data', selectedDate); else url.searchParams.delete('data');
      history.replaceState(null, '', url);
    } catch (error) {
      $('aviso').hidden = false;
      setText('aviso', `${error.name === 'AbortError' ? 'A consulta demorou. Tentando novamente.' : error.message}${data ? ' Os números exibidos são da última consulta bem-sucedida.' : ''}`);
      setText('conexao', '● Sem atualização');
      setClass('conexao', 'red');
    } finally {
      clearTimeout(timeout);
      busy = false;
      if (again) { again = false; timer = setTimeout(refresh, 0); }
      else timer = setTimeout(refresh, 15000);
    }
  }

  function changeFilter() {
    page = 0; hourPage = 0;
    data = null;
    for (const id of ['entrada-meta','entrada-produzido','entrada-saldo','entrada-eficiencia','entrada-total-meta','entrada-total-realizado','entrada-total-saldo','entrada-total-eficiencia']) $(id).textContent = '—';
    $('entrada-periodos').innerHTML = '';
    setText('entrada-contagem', '');
    setClass('entrada-ef-card', 'metric');
    for (const id of ['produzido','meta','eficiencia','saldo']) $(id).textContent = '—';
    for (const id of ['meta-mes','produzido-mes','eficiencia-mes','total-meta','total-realizado','total-saldo','total-eficiencia']) $(id).textContent = '—';
    $('periodos').innerHTML = '';
    setText('periodos-pagina', '');
    setText('mes-legenda', 'Consultando mês…');
    setText('mes-nota', '');
    setClass('ef-card', 'metric');
    setText('farol', 'Consultando apontamentos');
    setText('dia-legenda', 'Consultando data selecionada…');
    setText('paginas', '');
    setText('contagem', '—');
    setText('atualizacao', 'Última consulta: —');
    lastSuccess = null;
    setText('atingimento', 'Consultando meta do dia');
    setText('previsao-dia', '');
    setText('meta-apontada', 'peças para atingir a meta');
    $('definir-meta').hidden = true;
    $('ops').innerHTML = '<div class="empty">Consultando produção…</div>';
    $('horas').innerHTML = '';
    $('recentes').innerHTML = '';
    setText('conexao', 'Consultando…');
    setClass('conexao', '');
    refresh();
  }
  $('fabrica').addEventListener('change', () => { selectedFactory = $('fabrica').value; changeFilter(); });
  $('data').addEventListener('change', () => { selectedDate = $('data').value; changeFilter(); });
  $('hoje').addEventListener('click', () => { selectedDate = ''; changeFilter(); });
  $('alternar-visao').addEventListener('click', () => {
    const detail = document.body.classList.toggle('op-mode');
    document.querySelectorAll('.detail-view').forEach(e => e.hidden = !detail);
    setText('alternar-visao', detail ? 'Ver painel de bordo' : 'Ver OPs');
  });
  $('definir-meta').addEventListener('click', () => {
    if (!data) return;
    metaContext = {fabrica_id:data.fabrica_id, data:data.data};
    setText('meta-contexto', `${$('fabrica-nome').textContent} · ${data.data.split('-').reverse().join('/')}`);
    $('meta-quantidade').value = data.meta_dia.quantidade ?? '';
    setText('meta-erro', '');
    $('modal-meta').showModal();
    $('meta-quantidade').focus();
  });
  $('cancelar-meta').addEventListener('click', () => $('modal-meta').close());
  $('form-meta').addEventListener('submit', async event => {
    event.preventDefault();
    if ($('salvar-meta').disabled) return;
    $('salvar-meta').disabled = true;
    setText('meta-erro', '');
    try {
      const response = await fetch('/api/painel-producao/meta-dia', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...metaContext,quantidade:Number($('meta-quantidade').value)})});
      const result = await response.json();
      if (!response.ok || !result.ok) throw new Error(result.erro || 'Não foi possível salvar a meta.');
      $('modal-meta').close();
      refresh();
    } catch (error) { $('meta-erro').textContent = error.message; }
    finally { $('salvar-meta').disabled = false; }
  });
  $('tela-cheia').addEventListener('click', async () => {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else await document.documentElement.requestFullscreen();
    } catch (_) { $('aviso').hidden = false; $('aviso').textContent = 'Use F11 ou a opção de tela cheia do navegador.'; }
  });
  document.addEventListener('fullscreenchange', () => { $('tela-cheia').textContent = document.fullscreenElement ? 'Sair da tela cheia' : 'Tela cheia'; });
  window.addEventListener('online', refresh);
  window.addEventListener('resize', renderOps);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });
  setInterval(() => {
    setText('relogio', time(Date.now()));
    if (lastSuccess && Date.now() - lastSuccess > 35000) {
      setText('conexao', '● Dados sem atualização');
      setClass('conexao', 'red');
    }
  }, 1000);
  setInterval(() => {
    if (!data) return;
    const detail = document.body.classList.contains('op-mode');
    const pageSize = window.matchMedia('(min-width:1001px) and (max-height:850px)').matches ? 2 : 4;
    if ((data.programacao || []).length > 2 || (detail && (data.ops.length > pageSize || data.horas.length > 8))) {
      page++; hourPage++; render();
    }
  }, 12000);
  setText('relogio', time(Date.now()));
  refresh();
})();
