// Regras da montagem: a tolerância é global, incluindo todos os apoios.
// Os tempos cadastrados já incluem a margem de 18%.
function ajustarMetaCiclo(valor) {
  const meta = Number(valor);
  if (!Number.isInteger(meta) || meta < 1) { toast('Informe uma quantidade inteira de peças', 'error'); renderAll(); return; }
  estado.metaCiclo = meta;
  estado.metaDia = meta * Math.floor(estado.minutos / estado.ciclo);
  renderAll();
  toast('Meta atualizada. Gere novamente ou ajuste as atribuições antes de salvar.');
}

function podeAtribuir(ti, oi, idx, qtd, carga, anterior=null) {
  const fid = estado.times[ti].operadoras[oi].id;
  if (!Number.isInteger(qtd) || qtd < 1 || !Number.isFinite(carga) || carga <= 0) {
    toast('Quantidade e tempo devem ser positivos', 'error'); return false;
  }
  if (cargaGlobalOperadora(fid) - (anterior ? anterior.carga : 0) + carga > estado.ciclo + 1 + 0.000001) {
    toast('Carga global acima do limite, incluindo os apoios', 'error'); return false;
  }
  const ja = restanteGlobalOperacao(idx).atribuido - (anterior && anterior.op_idx === idx ? anterior.qtd : 0);
  if (ja + qtd > estado.metaCiclo) { toast('Quantidade acima da meta desta operação no ciclo', 'error'); return false; }
  return true;
}
