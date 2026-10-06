"""Metas independentes do balanceamento, com ciclos por OP."""
import math
from datetime import datetime, timedelta
from flask import jsonify, request, render_template


SCHEMA = '''CREATE TABLE IF NOT EXISTS planejamento_metas_op (
    op_id INTEGER NOT NULL, data TEXT NOT NULL, turno_id INTEGER NOT NULL,
    tempo_padrao REAL NOT NULL, operadores INTEGER NOT NULL,
    times INTEGER NOT NULL, ciclo REAL NOT NULL, eficiencia REAL NOT NULL,
    inicio TEXT NOT NULL, atualizado_por INTEGER NOT NULL,
    PRIMARY KEY(op_id, data), FOREIGN KEY(op_id) REFERENCES ordens_producao(id),
    FOREIGN KEY(turno_id) REFERENCES turnos(id)
)'''


def intervalos(c, turno, dia):
    registro = c.execute('SELECT * FROM jornada_calendario WHERE fabrica_id=? AND turno_id=? AND data=?',
                         (turno['fabrica_id'], turno['id'], dia.isoformat())).fetchone()
    if registro:
        fonte = dict(registro)
        if fonte['tipo'] in ('FERIADO', 'FOLGA', 'FERIAS') or fonte['minutos_disponiveis'] <= 0:
            return []
    else:
        if dia.weekday() >= 5:
            return []
        fonte = dict(turno)
        if dia.weekday() == 4 and fonte.get('hora_saida_sexta'):
            fonte['hora_saida'] = fonte['hora_saida_sexta']
    def hora(chave):
        return datetime.combine(dia, datetime.strptime(fonte[chave], '%H:%M').time())
    entrada, saida = hora('hora_entrada'), hora('hora_saida')
    if saida <= entrada:
        saida += timedelta(days=1)
    if fonte.get('hora_saida_almoco') and fonte.get('hora_entrada_almoco') and turno['tem_almoco']:
        almoco, retorno = hora('hora_saida_almoco'), hora('hora_entrada_almoco')
        if almoco < entrada:
            almoco += timedelta(days=1)
        if retorno <= almoco:
            retorno += timedelta(days=1)
        if not entrada < almoco < retorno < saida:
            raise ValueError('Horários de almoço inválidos no turno/calendário.')
        return [(entrada, almoco), (retorno, saida)]
    return [(entrada, saida)]


def avancar(c, turno, inicio, minutos):
    dia = inicio.date()
    for _ in range(3660):
        for entrada, saida in intervalos(c, turno, dia):
            atual = max(inicio, entrada)
            disponivel = (saida - atual).total_seconds() / 60
            if disponivel <= 0:
                continue
            if minutos <= disponivel:
                return atual + timedelta(minutes=minutos)
            minutos -= disponivel
        dia += timedelta(days=1)
    raise ValueError('Não há jornada suficiente para projetar esta OP.')


def calcular(c, op, turno, dados):
    inicio = datetime.fromisoformat(dados['inicio'])
    if inicio.tzinfo is not None or inicio.date().isoformat() != dados['data']:
        raise ValueError('O início deve pertencer à data selecionada e usar horário local.')
    tempo, ciclo, eficiencia = (float(dados[k]) for k in ('tempo_padrao', 'ciclo', 'eficiencia'))
    operadores, times = (int(dados[k]) for k in ('operadores', 'times'))
    if any(not math.isfinite(v) or v <= 0 for v in (tempo, ciclo, eficiencia)) or eficiencia > 100:
        raise ValueError('Informe tempos positivos e eficiência entre 0 e 100%.')
    if any(str(dados[k]) != str(v) or not 1 <= v <= 10000 for k, v in [('operadores', operadores), ('times', times)]):
        raise ValueError('Operadores e times devem ser números inteiros positivos.')
    if op['quantidade_total'] <= 0:
        raise ValueError('A OP precisa ter quantidade cadastrada maior que zero.')
    minutos = sum((b-a).total_seconds()/60 for a,b in intervalos(c, turno, inicio.date()))
    if minutos <= 0:
        raise ValueError('A data selecionada não tem jornada de trabalho.')
    taxa = operadores / tempo * eficiencia / 100
    entrada = avancar(c, turno, inicio, 0)
    primeira = avancar(c, turno, entrada, times*ciclo)
    # A primeira peça já está pronta após o atravessamento.
    saida = avancar(c, turno, primeira, (op['quantidade_total']-1)/taxa)
    return dict(minutos_dia=minutos, meta_dia=taxa*minutos, meta_hora=taxa*60,
                atravessamento=times*ciclo, entrada=entrada.isoformat(timespec='seconds'),
                primeira_peca=primeira.isoformat(timespec='seconds'), saida=saida.isoformat(timespec='seconds'))


def registrar_metas(app, m, get_user, fab_ids, login_required):
    @app.get('/metas-op')
    @login_required
    def metas_op():
        user = get_user()
        ids = fab_ids(user)
        c = m.conn()
        try:
            ph = ','.join('?' * len(ids)) or 'NULL'
            ops = [dict(r) for r in c.execute(f'SELECT id,numero,descricao,quantidade_total,fabrica_id FROM ordens_producao WHERE fabrica_id IN ({ph}) ORDER BY id DESC', ids).fetchall()]
            turnos = [dict(r) for r in c.execute(f'SELECT * FROM turnos WHERE ativo=1 AND fabrica_id IN ({ph}) ORDER BY numero', ids).fetchall()]
        finally:
            c.close()
        return render_template('metas_op.html', user=user, ops=ops, turnos=turnos)

    @app.route('/api/metas-op', methods=['GET', 'POST'])
    def api_metas_op():
        user = get_user()
        if not user:
            return jsonify(erro='Entre no sistema.'), 401
        if request.method == 'POST' and user['perfil'] not in ('admin', 'gestor'):
            return jsonify(erro='Somente gestores e administradores podem planejar metas.'), 403
        c = m.conn()
        try:
            dados = (request.get_json(silent=True) or {}) if request.method == 'POST' else request.args
            if not hasattr(dados, 'get'):
                raise ValueError('Dados inválidos.')
            op = c.execute('SELECT * FROM ordens_producao WHERE id=?', (int(dados['op_id']),)).fetchone()
            if not op or op['fabrica_id'] not in fab_ids(user):
                return jsonify(erro='OP não autorizada.'), 403
            if request.method == 'GET':
                row = c.execute('SELECT * FROM planejamento_metas_op WHERE op_id=? AND data=?', (op['id'], dados['data'])).fetchone()
                return jsonify(plano=dict(row) if row else None)
            turno = c.execute('SELECT * FROM turnos WHERE id=? AND ativo=1', (int(dados['turno_id']),)).fetchone()
            if not turno or turno['fabrica_id'] != op['fabrica_id']:
                raise ValueError('Selecione um turno da mesma fábrica da OP.')
            resultado = calcular(c, op, dict(turno), dados)
            if dados.get('salvar'):
                c.execute('''INSERT INTO planejamento_metas_op
                    (op_id,data,turno_id,tempo_padrao,operadores,times,ciclo,eficiencia,inicio,atualizado_por)
                    VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(op_id,data) DO UPDATE SET
                    turno_id=excluded.turno_id,tempo_padrao=excluded.tempo_padrao,
                    operadores=excluded.operadores,times=excluded.times,ciclo=excluded.ciclo,
                    eficiencia=excluded.eficiencia,inicio=excluded.inicio,atualizado_por=excluded.atualizado_por''',
                    (op['id'], dados['data'], turno['id'], float(dados['tempo_padrao']), int(dados['operadores']),
                     int(dados['times']), float(dados['ciclo']), float(dados['eficiencia']), dados['inicio'], user['id']))
                c.commit()
            return jsonify(ok=True, resultado=resultado)
        except (ValueError, TypeError, KeyError, OverflowError):
            return jsonify(erro='Confira os campos, a quantidade da OP e os horários do turno/calendário.'), 400
        finally:
            c.close()
