# Programação e metas por OP

Acesse **Metas por OP**. Cadastre a primeira OP com turno, data/hora de início, tempo padrão em minutos por peça, operadores, times, ciclo por time e eficiência. Salve a programação. Para cada OP seguinte, informe seus próprios parâmetros: o sistema calcula a entrada a partir do término da anterior no primeiro time, respeitando o atravessamento, os horários de seu turno e as exceções do calendário.

O ciclo é comum aos times de uma OP, mas pode mudar entre OPs. Os dados são independentes do balanceamento. A fila é compartilhada por fábrica, na ordem em que as OPs são programadas. Use **Editar** na tabela para alterar uma OP. Alterações na primeira ou nas intermediárias recalculam as previsões seguintes, sem mudar a ordem nem duplicar os planejamentos existentes.

**Calcular** mostra uma prévia. **Salvar planejamento** aplica a alteração à fila e à **Gestão à vista**, que consulta automaticamente a programação a cada 15 segundos. Somente gestores e administradores salvam; operadores podem acompanhar a fila e a TV.

## Cálculos

- Taxa por minuto = operadores ÷ tempo padrão × eficiência ÷ 100.
- Capacidade diária = minutos úteis do dia × taxa por minuto.
- Meta horária = 60 × taxa por minuto.
- Primeira peça = entrada + times × ciclo, consumindo apenas minutos úteis.
- Saída = primeira peça + (quantidade da OP − 1) ÷ taxa por minuto, consumindo apenas minutos úteis.

As metas na TV correspondem às **peças prontas previstas em cada dia e horário**. Consideram atravessamento inicial, pausas, troca de OP, jornadas diferentes e quantidade restante no último dia. Por isso, a meta programada de um dia parcial pode ser inferior à capacidade diária. Os valores mantêm precisão interna; a exibição é arredondada. Períodos horários terminam em horas cheias; apontamentos com minutos são agrupados no período que termina na próxima hora cheia.

A TV mostra todos os períodos de trabalho do turno nas datas programadas, inclusive antes da primeira peça e depois da conclusão da OP. Horários sem saída prevista de peças têm meta zero; o realizado continua mostrando os lançamentos daquele horário. Pausas sem trabalho não criam períodos produtivos.

Produção realizada continua vindo exclusivamente da tela **Lançamento**. Não há soma com o contador da fila nem criação de apontamentos. Nas datas abrangidas pela programação, a TV usa as metas planejadas para horários, OPs, resumo diário e acumulado mensal. Metas manuais antigas permanecem armazenadas e continuam valendo fora dessas datas. O mês considera apenas datas até a selecionada. O botão de meta manual fica oculto em dias cobertos pela programação.

Sem registro diário no calendário, usa a jornada normal de segunda a sexta e a saída especial de sexta. Cadastre exceções, feriados, folgas e trabalho no fim de semana no calendário.

## Preservação e limites

A atualização cria a tabela aditiva `sequencia_metas_op`. Planejamentos antigos são incluídos uma única vez, ordenados pelo início originalmente salvo, com desempate por OP/data; a versão anterior não registrava a ordem dos salvamentos. Os cadastros antigos são preservados. A chave OP/data do cadastro permanece estável quando as datas previstas são recalculadas.

O encadeamento permite que a próxima OP atravesse os primeiros times enquanto a anterior termina nos últimos. A entrada seguinte parte do fim da entrada da anterior no primeiro time. A primeira saída seguinte respeita pelo menos um ciclo da próxima OP após a última saída anterior; turnos, pausas e diferenças de atravessamento também são considerados. Com times e ciclos iguais, a última saída às 16:30 é seguida pela primeira da próxima às 16:45 para ciclo de 15 minutos.

Lançamentos recalculam automaticamente a previsão usando a quantidade realizada até o último período encerrado. A taxa padrão e a meta original são preservadas. A TV mostra a previsão atualizada do dia e entrada/saída atualizadas das OPs; períodos futuros não geram perda antecipada. Edição e exclusão de lançamentos também são refletidas na consulta seguinte. Sem apontamentos, permanece a previsão planejada; ausência de lançamento não é tratada como parada confirmada. Não há movimentação manual de posição, remoção de OP da fila nem histórico imutável de revisões nesta entrega.

## Verificação

`python -m unittest test_metas_op test_painel_tv test_fabrica_unica` executa 34 testes isolados, incluindo datas encadeadas, pausas/feriados, edição sem duplicação, migração idempotente, acesso por fábrica, metas da TV, distribuição da quantidade completa e proteção contra divisão por zero.

Para testar o navegador, execute `python test_metas_op.py --serve` e `node test_browser_metas.cjs` (Playwright instalado; caminho alternativo via `PLAYWRIGHT_MODULE`). Usa SQLite temporário e dados fictícios, nas telas 1920×1080, 1366×768 e 390×844.
