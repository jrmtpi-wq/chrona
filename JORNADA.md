# Calendário mensal por turno

Em **Jornada → Gerar Mês**, selecione mês, fábrica e turno.

- **Dias de feriado:** números dos dias separados por vírgulas. Para 12/10/2026, selecione outubro/2026 e informe `12`. A lista é manual; não há reconhecimento automático de feriados nacionais ou municipais.
- **Sábados trabalhados:** informe somente os sábados que terão trabalho. Em outubro/2026, `3, 17` inclui esses dois sábados. Deixe **Incluir todos os Sábados** desmarcado para incluir somente os escolhidos.
- **Incluir Domingos:** inclui todos os domingos, se necessário.

Feriados informados e sábados escolhidos também atualizam registros existentes. Feriado prevalece quando a mesma data aparece nas duas listas. Os demais registros existentes são preservados, inclusive horários especiais. Para cancelar um sábado já cadastrado, use **Editar Dia → Tipo → Folga**. Para voltar a trabalhar, altere para **Sábado**, ajuste os horários e salve. Para trabalhar em uma data antes marcada como feriado, altere para **Normal** ou **Hora Extra** e confira os horários.

Repita a configuração para cada turno afetado. Em Editar Dia, Feriado, Folga e Férias zeram minutos e hora extra. Esses tipos não entram nos totais de dias trabalhados/minutos nem na programação das OPs. O total de dias é por turno: uma data com dois turnos representa dois dias de trabalho por turno.

Gerar novamente sem informar uma exceção não remove a exceção já cadastrada. Não exclua um feriado para desativá-lo: sem registro, o planejamento usa a jornada padrão de segunda a sexta.

Validação isolada: `python -m unittest test_jornada test_metas_op test_painel_tv` e `node test_browser_jornada.cjs` (Playwright/Edge).
