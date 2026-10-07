# Editar e excluir ordens de produção

Em **Ordens de Produção**, cada linha oferece **Editar**, **Excluir** e **Cancelar**. Editar salva os dados e a situação da OP, preservando as datas de entrada/saída e observações quando não foram alteradas. Cancelar mantém os registros. Excluir remove a OP e os seus registros vinculados.

Gestores e administradores podem excluir OPs. A API verifica acesso à fábrica antes da exclusão. O botão **Excluir todas as OPs** inclui ativas, encerradas e canceladas das fábricas autorizadas ou da fábrica selecionada. Busca e filtro de situação não limitam a limpeza. O diálogo informa esse alcance e solicita confirmação.

A exclusão é transacional: planejamento e sequência das metas, entrada, saída, lançamentos de fila, balanceamentos, atribuições, sequência própria da OP e faturamentos vinculados são removidos juntos. A fila legada perde somente os itens dessas OPs; vínculos textuais de notas fiscais são removidos quando correspondem ao número da OP. As notas fiscais e os demais cadastros permanecem. A exclusão de todas também zera as metas diárias das fábricas escolhidas.

Antes da remoção, uma cópia dos registros é guardada em `exclusoes_ops_backup`, na mesma transação. Falhas revertem os dados e a cópia. Não existe tela de restauração nesta entrega. Referências, sequências das referências, funcionários, turnos, calendários, equipamentos, usuários e outras OPs permanecem.

## Limpeza dos testes autorizada em 07/10/2026

O usuário confirmou que todas as OPs existentes são testes e autorizou removê-las antes de cadastrar uma real. A publicação executa a limpeza uma única vez na instalação **JTMTPI CONFECÇÕES**, durante 07/10/2026 UTC, exigindo o registro da consolidação anterior a essa data. O marcador `ops-teste-jtmtpi-2026-10-07` impede repetição. Instalações novas, outros nomes e datas posteriores não executam essa manutenção. OPs cadastradas após a primeira limpeza permanecem nos próximos reinícios.

`/api/status-publicacao-ops` informa somente o booleano da conclusão dessa manutenção, sem expor OPs ou cópias. Os endpoints de exclusão exigem autenticação e perfil autorizado.

## Validação

`python -m unittest test_exclusao_ops test_entrada_grupo test_metas_op test_painel_tv test_fabrica_unica -q` verifica vínculos e chaves estrangeiras, isolamento de fábrica, rollback, cópia, execução única e edição/cadastro posterior.

`python test_metas_op.py --serve` e `node test_browser_exclusao.cjs` usam banco temporário com dados fictícios para conferir as ações pela tela, incluindo cadastrar uma OP após a limpeza.
