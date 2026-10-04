# Gestão à vista da produção

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
