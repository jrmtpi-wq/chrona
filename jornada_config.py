from datetime import date
import calendar

SEM_TRABALHO = ('FERIADO', 'FOLGA', 'FERIAS')


def dias_informados(valor, limite):
    dias = {int(item.strip()) for item in (valor or '').split(',') if item.strip()}
    if any(d < 1 or d > limite for d in dias):
        raise ValueError('Informe dias existentes no mês, separados por vírgulas.')
    return dias


def gerar_calendario(c, turno, mes, dados):
    ano, numero = map(int, mes.split('-'))
    limite = calendar.monthrange(ano, numero)[1]
    feriados = dias_informados(dados.get('feriados'), limite)
    sabados = dias_informados(dados.get('sabados_trabalhados'), limite)
    if any(date(ano, numero, d).weekday() != 5 for d in sabados):
        raise ValueError('A lista de sábados trabalhados deve conter somente sábados.')
    nomes = ['Segunda', 'Terca', 'Quarta', 'Quinta', 'Sexta', 'Sabado', 'Domingo']
    inseridos = 0
    for dia in range(1, limite + 1):
        dt = date(ano, numero, dia)
        wd = dt.weekday()
        feriado = dia in feriados
        if not feriado and wd == 5 and not (dados.get('include_sabado') or dia in sabados):
            continue
        if not feriado and wd == 6 and not dados.get('include_domingo'):
            continue
        tipo = 'FERIADO' if feriado else ('SABADO' if wd == 5 else 'DOMINGO' if wd == 6 else 'NORMAL')
        saida = turno['hora_saida_sexta'] if wd == 4 and turno['hora_saida_sexta'] else turno['hora_saida']
        minutos = 0 if feriado else (turno['minutos_sexta'] if wd == 4 else turno['minutos_normal'])
        valores = (turno['fabrica_id'], turno['id'], dt.isoformat(), nomes[wd], tipo,
                   turno['hora_entrada'], turno['hora_saida_almoco'], turno['hora_entrada_almoco'], saida, minutos)
        existente = c.execute('SELECT id FROM jornada_calendario WHERE fabrica_id=? AND turno_id=? AND data=?',
                             (turno['fabrica_id'], turno['id'], dt.isoformat())).fetchone()
        # Exceções explicitamente informadas também corrigem um mês já gerado.
        if existente and (feriado or dia in sabados):
            c.execute('''UPDATE jornada_calendario SET tipo=?, hora_entrada=?, hora_saida_almoco=?,
                         hora_entrada_almoco=?, hora_saida=?, minutos_disponiveis=?, hora_extra=0 WHERE id=?''',
                      (tipo, *valores[5:], existente['id']))
        elif not existente:
            c.execute('''INSERT INTO jornada_calendario
                         (fabrica_id,turno_id,data,dia_semana,tipo,hora_entrada,hora_saida_almoco,
                          hora_entrada_almoco,hora_saida,minutos_disponiveis) VALUES (?,?,?,?,?,?,?,?,?,?)''', valores)
            inseridos += 1
    return inseridos
