# Gestão à vista da produção

## Entrada e saída do grupo

A TV apresenta **Entrada do grupo** à esquerda e **Saída do grupo** à direita. Cada lado tem tabela por horário, meta do dia, realizado, saldo e eficiência dos períodos encerrados. No celular, a entrada aparece acima da saída. Horários futuros mostram a meta e aguardam o fim do período para calcular perda e eficiência.

Na tela **Lançamento**, abra **Entrada do grupo · apontar produção do primeiro time**. Informe OP, data, fim do período e quantidade em peças; entradas podem ser editadas ou excluídas. O lançamento de produção existente continua registrando peças prontas na saída. Os dois lados atualizam automaticamente a cada 15 segundos.

A meta de entrada usa a programação do primeiro time: primeira produção após um ciclo, término da entrada antes do término da saída pelos ciclos dos demais times. A meta de saída usa o atravessamento completo. Cada lado soma suas OPs previstas para a jornada. Sem programação, o apontamento de entrada permite informar sua própria meta do período.

Entradas são guardadas na tabela aditiva `entradas_producao`, criada em SQLite e PostgreSQL. Não se somam à saída, ao faturamento, ao acumulado mensal de peças prontas ou à produção concluída da OP. Os lançamentos antigos continuam como saída; nenhum realizado de entrada é inferido desses registros. A previsão de conclusão continua baseada nos lançamentos de saída.

Verificação: `python -m unittest test_entrada_grupo test_metas_op test_painel_tv test_fabrica_unica -q`. O teste `node test_browser_entrada.cjs` usa o servidor temporário de `test_metas_op.py --serve`, após `test_browser_metas.cjs`, para verificar o apontamento e a atualização da TV.

## Painel de bordo

A visão padrão segue o modelo de referência: tabela **Hora / Meta / Realizado / Saldo / Efic. %**, resumo diário à direita e acumulado mensal abaixo. **Ver OPs** abre a visão de acompanhamento anterior.

- Horários iniciais: 08:00, 09:00, 10:00, 11:00, 13:30, 14:30, 15:30, 16:30 e 17:30. Horários adicionais registrados são incluídos automaticamente, preservando os minutos (09:00 e 09:30 são distintos). Mais de dez horários têm rodízio automático.
- Metas e realizados por horário vêm dos lançamentos. Horários sem apontamento aparecem em cinza com “—”, sem distribuir artificialmente a meta diária entre horas.
- Saldo horário e diário = realizado menos meta, com valores negativos quando a produção ainda não alcançou a meta.
- Eficiência do dia = realizado dividido pela meta diária cadastrada. Eficiência dos horários e do total apontado = realizado dividido pelas metas dos lançamentos.
- Acumulado mensal: do primeiro dia do mês até a data selecionada; realizado vem dos apontamentos, meta é a soma das metas diárias cadastradas nesse período. Metas ou produções futuras ficam fora.
- Se houver dias com produção e sem meta diária, a eficiência mensal aparece “—” com a quantidade de dias pendentes. Sem meta, nenhuma eficiência gera divisão por zero.
- Números da referência enviada não foram importados como produção real nem como metas.

Validação desta atualização: quatorze testes de dados/integração, incluindo horários com meia hora, corte mensal, isolamento de fábrica e metas mensais incompletas; teste no navegador inclui tabela, resumo diário/mensal, configuração de meta, troca de visão e layout de TV/celular.

Abra **Lançamento → Gestão à vista · TV**, ou `/painel-producao`, após entrar no sistema. Selecione a fábrica e clique em **Tela cheia**. Os apontamentos continuam sendo feitos pela tela Lançamento em outro computador ou celular.

O painel consulta `/api/painel-producao` a cada 15 segundos. Inclusões, alterações e exclusões de lançamentos são refletidas na consulta seguinte. Em caso de falha, os valores anteriores permanecem identificados como desatualizados; a consulta é tentada novamente automaticamente. Uma sessão encerrada exige novo login.

- Produzido: soma das peças registradas na data selecionada, exclusivamente na tabela `producao`. Não soma `lancamentos_fila`.
- Meta do dia: total de peças definido por gestor ou administrador em **Definir meta do dia**, para a fábrica e data selecionadas. É compartilhada entre os usuários dessa fábrica e permanece salva ao reabrir o painel. Sem cadastro, aparece “—”.
- Atingimento diário: produzido / meta do dia × 100. Peças restantes: máximo entre zero e meta do dia menos produzido. Quando a produção ultrapassa a meta, o atingimento pode passar de 100% e a quantidade restante fica em zero.
- Meta apontada: soma de `qtd_projetada` dos registros da mesma data. Não representa a meta de todo o turno, nem estima períodos sem lançamento.
- Eficiência: soma do produzido / soma da meta apontada × 100. Sem meta, aparece “—”; zero produzido com meta positiva aparece 0%.
- Farol: abaixo de 85% vermelho; 85% até menos de 92% amarelo; 92% a 100% verde; acima de 100% azul. Cor acompanhada de percentual e legenda.
- Horas: soma dos lançamentos dentro de cada hora; não presume que um lançamento indique que a máquina está rodando ou parada.
- Progresso da OP: produzido acumulado até a data selecionada / quantidade cadastrada. Não altera situação nem libera faturamento.
- Até quatro OPs por página (duas em TVs com altura menor), com rodízio automático a cada 12 segundos; horas também rodam em páginas de oito. Últimos períodos ordenados pela hora informada, não pelo instante de salvamento.
- A data padrão acompanha o dia em Brasília. Selecionar uma data fixa consulta esse dia até clicar em **Hoje**. Fábrica e data fixa ficam na URL para reutilizar na TV.

O acesso é autenticado e restrito às fábricas autorizadas. Administradores selecionam uma fábrica por vez. A API de consulta permanece somente leitura; `/api/painel-producao/meta-dia` salva a meta apenas para gestores e administradores autorizados. Metas ficam na nova tabela `metas_producao_dia`, criada com `CREATE TABLE IF NOT EXISTS` em SQLite e PostgreSQL. Não altera registros de produção existentes. O painel não exibe valores financeiros.

O registro atual não guarda o turno nem o setor/time no lançamento. A meta diária é informada pelo gestor; a meta integral não é inferida a partir dos lançamentos ou da troca de OP. Situação de equipamentos e desempenho por time dependem de evolução desses registros.

Validação: `python -m unittest test_painel_tv -v`. Testes usam banco temporário, schema SQLite real e app real, substituindo a conexão antes da importação para evitar inicialização e seed do banco do sistema. Para conferir visualmente com dados fictícios: `python test_painel_tv.py --serve`, depois `http://127.0.0.1:5051/test-login`.

Publicação autorizada em 04/10/2026. A aplicação Render usa `gunicorn app:app` e o repositório `jrmtpi-wq/chrona`, branch `main`. A atualização inclui a configuração da meta diária e a criação aditiva da tabela de metas.

Validação: onze testes de dados e integração, incluindo metas por data/fábrica, alteração sem duplicação, validação de quantidades, permissões e meta antes do primeiro apontamento. Navegador Edge verifica configuração de meta, atingimento após apontamento, recuperação de conexão, troca de data, paginação de OPs, escape de textos e layout em 1920×1080, 1366×768 e celular. Capturas de conferência em `test-results/`, com dados fictícios. Teste do navegador: `node test_browser_painel.cjs` com Playwright disponível (ou `PLAYWRIGHT_MODULE` apontando para a instalação local).
