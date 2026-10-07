(() => {
  'use strict';
  let excluindo = false;
  async function excluir(url, dados) {
    if (excluindo) return;
    excluindo = true;
    const botao = document.getElementById('excluir-todas-ops');
    if (botao) botao.disabled = true;
    try {
      const r = await fetch(url, {method:'DELETE',headers:{'Content-Type':'application/json'},body:JSON.stringify(dados)});
      const d = await r.json();
      if (!r.ok || !d.ok) throw Error(d.erro || 'Não foi possível excluir as OPs.');
      await carregarLista();
      toast(`${d.excluidas} OP(s) excluída(s).`);
    } catch (e) { toast(e.message, 'err'); }
    finally { excluindo = false; if (botao) botao.disabled = false; }
  }
  window.excluirOPCad = id => {
    const op = opsAtuais.find(o => o.id === id);
    if (!op || excluindo) return;
    if (!confirm(`Excluir definitivamente a OP ${op.numero} e seus lançamentos, planejamento, balanceamento e faturamento vinculado?`)) return;
    return excluir(`/api/op/excluir/${id}`, {confirmacao:'EXCLUIR'});
  };
  window.excluirTodasOPs = () => {
    if (excluindo) return;
    const fabrica = document.getElementById('filt-fab').value;
    const escopo = fabrica ? 'da fábrica selecionada' : 'das suas fábricas autorizadas';
    if (!confirm(`Excluir definitivamente TODAS as OPs ${escopo}, inclusive canceladas, e seus lançamentos, planejamentos, balanceamentos, faturamentos vinculados e metas diárias? A busca e o filtro de situação não limitam esta limpeza.`)) return;
    const dados = {confirmacao:'EXCLUIR TODAS'};
    if (fabrica) dados.fabrica_id = Number(fabrica);
    return excluir('/api/ops/excluir-todas', dados);
  };
})();
