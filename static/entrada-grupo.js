(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  let registros = [], versao = 0;
  const limpar = () => {
    $('entrada-id').value = '';
    $('entrada-qtd').value = '';
    $('entrada-cancelar').hidden = true;
    $('entrada-salvar').textContent = 'Salvar entrada';
  };
  async function atualizar() {
    const atual = ++versao, dia = $('entrada-data').value;
    $('entrada-registros').replaceChildren();
    try {
      const r = await fetch(`/api/entrada-grupo?${new URLSearchParams({data:dia})}`, {cache:'no-store'});
      const dados = await r.json();
      if (atual !== versao) return;
      if (!r.ok) throw Error(dados.erro || 'Não foi possível consultar as entradas.');
      registros = dados;
      for (const item of registros) {
        const tr = document.createElement('tr');
        for (const valor of [item.hora, `OP ${item.numero}`, item.qtd_produzida.toLocaleString('pt-BR')]) {
          const td = document.createElement('td'); td.textContent = valor; tr.append(td);
        }
        const acoes = document.createElement('td');
        for (const [nome, acao] of [['Editar', () => editar(item)], ['Excluir', () => excluir(item)]]) {
          const b = document.createElement('button'); b.type = 'button'; b.className = 'btn btn-light btn-sm'; b.textContent = nome; b.addEventListener('click', acao); acoes.append(b);
        }
        tr.append(acoes); $('entrada-registros').append(tr);
      }
      if (!registros.length) {
        const tr = document.createElement('tr'), td = document.createElement('td');
        td.colSpan = 4; td.textContent = 'Nenhuma entrada apontada nesta data.'; tr.append(td); $('entrada-registros').append(tr);
      }
    } catch (e) { if (atual === versao) $('entrada-mensagem').textContent = e.message; }
  }
  function editar(item) {
    $('entrada-id').value = item.id;
    $('entrada-data').value = item.data;
    $('entrada-op').value = item.op_id;
    $('entrada-hora').value = item.hora;
    $('entrada-qtd').value = item.qtd_produzida;
    $('entrada-meta-manual').value = item.qtd_projetada;
    $('entrada-cancelar').hidden = false;
    $('entrada-salvar').textContent = 'Salvar alteração';
    $('form-entrada').scrollIntoView({behavior:'smooth', block:'center'});
    $('entrada-qtd').focus({preventScroll:true});
  }
  async function excluir(item) {
    if (!confirm(`Excluir a entrada da OP ${item.numero} às ${item.hora}?`)) return;
    try {
      const r = await fetch(`/api/entrada-grupo/${item.id}`, {method:'DELETE'}), d = await r.json();
      if (!r.ok) throw Error(d.erro);
      limpar(); await atualizar(); $('entrada-mensagem').textContent = 'Entrada excluída.';
    } catch (e) { $('entrada-mensagem').textContent = e.message; }
  }
  $('form-entrada').addEventListener('submit', async e => {
    e.preventDefault();
    if ($('entrada-salvar').disabled) return;
    const d = {op_id:Number($('entrada-op').value), data:$('entrada-data').value, hora:$('entrada-hora').value,
      quantidade:Number($('entrada-qtd').value), meta:Number($('entrada-meta-manual').value)};
    if ($('entrada-id').value) d.id = Number($('entrada-id').value);
    $('entrada-salvar').disabled = true;
    try {
      const r = await fetch('/api/entrada-grupo', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(d)});
      const result = await r.json(); if (!r.ok) throw Error(result.erro);
      limpar(); await atualizar(); $('entrada-mensagem').textContent = 'Entrada salva. A TV atualiza automaticamente.';
    } catch (err) { $('entrada-mensagem').textContent = err.message; }
    finally { $('entrada-salvar').disabled = false; }
  });
  $('entrada-cancelar').addEventListener('click', limpar);
  $('entrada-data').addEventListener('change', () => { limpar(); atualizar(); });
  atualizar();
})();
