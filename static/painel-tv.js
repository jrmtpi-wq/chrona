'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const n = value => Number(value || 0).toLocaleString('pt-BR', {maximumFractionDigits: 1});
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const percent = value => value === null ? '—' : `${n(value)}%`;
  const color = ef => ef === null ? '' : ef < 85 ? 'red' : ef < 92 ? 'amber' : ef <= 100 ? 'green' : 'blue';
  const time = value => new Date(value).toLocaleTimeString('pt-BR', {timeZone:'America/Sao_Paulo',hour:'2-digit',minute:'2-digit',second:'2-digit'});
  let data = null, page = 0, hourPage = 0, timer, busy = false, again = false;
  let selectedDate = new URLSearchParams(location.search).get('data') || '';
  let selectedFactory = new URLSearchParams(location.search).get('fabrica_id') || '';
  let lastSuccess = null;

  function renderOps() {
    if (!data) return;
    const pageSize = window.matchMedia('(min-width:1001px) and (max-height:850px)').matches ? 2 : 4;
    const pages = Math.max(1, Math.ceil(data.ops.length / pageSize));
    page %= pages;
    $('paginas').textContent = data.ops.length ? `${data.ops.length} OPs · página ${page + 1}/${pages}` : '';
    $('ops').innerHTML = data.ops.length ? data.ops.slice(page * pageSize, page * pageSize + pageSize).map(o => {
      const progress = o.quantidade > 0 ? Math.min(100, Math.max(0, o.acumulado / o.quantidade * 100)) : 0;
      return `<article class="op-card ${color(o.eficiencia)}"><div class="op-head"><strong>OP ${escape(o.numero)}</strong><span class="pill">${percent(o.eficiencia)}</span></div>
        <div class="op-ref" title="${escape(o.descricao)}">${escape(o.referencia || 'Sem referência')} · ${escape(o.descricao)}</div>
        <div class="op-numbers"><div><strong>${n(o.produzido)}</strong><span>produzido hoje</span></div><div><strong>${n(o.meta)}</strong><span>meta apontada</span></div></div>
        <div class="progress"><span style="width:${progress}%"></span></div>
        <div class="op-progress"><span>${n(o.acumulado)} / ${n(o.quantidade)} peças na OP</span><span>${n(o.restante)} restantes</span></div></article>`;
    }).join('') : '<div class="empty">Nenhum lançamento nesta data.<br>Os apontamentos salvos aparecerão aqui automaticamente.</div>';
    const hpages = Math.max(1, Math.ceil(data.horas.length / 8));
    hourPage %= hpages;
    const max = Math.max(1, ...data.horas.flatMap(h => [h.produzido, h.meta]));
    $('horas').innerHTML = data.horas.length ? data.horas.slice(hourPage * 8, hourPage * 8 + 8).map(h =>
      `<div class="hour-row"><strong>${escape(h.hora)}</strong><div class="hour-bars"><div class="bar" style="width:${Math.max(0,h.produzido / max * 100)}%"></div><div class="bar target" style="width:${Math.max(0,h.meta / max * 100)}%"></div></div><div class="hour-values">${n(h.produzido)} / ${n(h.meta)}</div></div>`
    ).join('') : '<div class="empty">Aguardando apontamentos</div>';
  }

  function render() {
    const factories = data.fabricas.map(f => `<option value="${Number(f.id)}">${escape(f.nome)}</option>`).join('');
    $('fabrica').innerHTML = factories || '<option value="">Sem fábrica disponível</option>';
    $('fabrica').value = data.fabrica_id ?? '';
    selectedFactory = String(data.fabrica_id ?? '');
    $('fabrica-nome').textContent = data.fabricas.find(f => f.id === data.fabrica_id)?.nome || 'Produção da fábrica';
    $('data').value = data.data;
    const day = new Date(`${data.data}T12:00:00-03:00`).toLocaleDateString('pt-BR', {timeZone:'America/Sao_Paulo',weekday:'long',day:'2-digit',month:'long',year:'numeric'});
    $('dia-legenda').textContent = day;
    $('produzido').textContent = n(data.resumo.produzido);
    $('meta').textContent = n(data.resumo.meta);
    $('eficiencia').textContent = percent(data.resumo.eficiencia);
    $('ef-card').className = `metric ${color(data.resumo.eficiencia)}`;
    $('saldo').textContent = `${data.resumo.saldo > 0 ? '+' : ''}${n(data.resumo.saldo)}`;
    $('farol').textContent = data.resumo.eficiencia === null ? 'Sem meta apontada' : data.resumo.eficiencia < 85 ? 'Abaixo de 85%' : data.resumo.eficiencia < 92 ? 'Atenção ao ritmo' : data.resumo.eficiencia <= 100 ? 'Faixa verde · 92% a 100%' : 'Acima da meta apontada';
    $('contagem').textContent = `${n(data.resumo.lancamentos)} lançamentos na data`;
    $('recentes').innerHTML = data.recentes.length ? data.recentes.map(r =>
      `<article class="recent-item"><span class="time">${escape(r.hora)} · OP ${escape(r.numero)}</span><strong>${n(r.produzido)} <small class="muted">peças</small></strong><span>Meta ${n(r.meta)} · <b class="${color(r.eficiencia)}">${percent(r.eficiencia)}</b></span></article>`
    ).join('') : '<div class="empty">Nenhum período apontado</div>';
    renderOps();
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
      $('conexao').textContent = '● Online · consulta automática';
      $('conexao').className = 'green';
      $('atualizacao').textContent = `Última consulta: ${time(data.atualizado_em)}`;
      const url = new URL(location.href);
      if (selectedFactory) url.searchParams.set('fabrica_id', selectedFactory);
      if (selectedDate) url.searchParams.set('data', selectedDate); else url.searchParams.delete('data');
      history.replaceState(null, '', url);
    } catch (error) {
      $('aviso').hidden = false;
      $('aviso').textContent = `${error.name === 'AbortError' ? 'A consulta demorou. Tentando novamente.' : error.message}${data ? ' Os números exibidos são da última consulta bem-sucedida.' : ''}`;
      $('conexao').textContent = '● Sem atualização';
      $('conexao').className = 'red';
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
    for (const id of ['produzido','meta','eficiencia','saldo']) $(id).textContent = '—';
    $('ef-card').className = 'metric';
    $('farol').textContent = 'Consultando apontamentos';
    $('dia-legenda').textContent = 'Consultando data selecionada…';
    $('paginas').textContent = '';
    $('contagem').textContent = '—';
    $('atualizacao').textContent = 'Última consulta: —';
    lastSuccess = null;
    $('ops').innerHTML = '<div class="empty">Consultando produção…</div>';
    $('horas').innerHTML = '';
    $('recentes').innerHTML = '';
    $('conexao').textContent = 'Consultando…';
    $('conexao').className = '';
    refresh();
  }
  $('fabrica').addEventListener('change', () => { selectedFactory = $('fabrica').value; changeFilter(); });
  $('data').addEventListener('change', () => { selectedDate = $('data').value; changeFilter(); });
  $('hoje').addEventListener('click', () => { selectedDate = ''; changeFilter(); });
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
    $('relogio').textContent = time(Date.now());
    if (lastSuccess && Date.now() - lastSuccess > 35000) {
      $('conexao').textContent = '● Dados sem atualização';
      $('conexao').className = 'red';
    }
  }, 1000);
  setInterval(() => { page++; hourPage++; renderOps(); }, 12000);
  $('relogio').textContent = time(Date.now());
  refresh();
})();
