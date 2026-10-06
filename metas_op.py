"""Metas independentes do balanceamento, com ciclos por OP."""
import math
from datetime import datetime, timedelta
from flask import jsonify, request, render_template


def importar_planejamentos(c):
    """Preserva planos antigos; datas originais definem a ordem inicial legada."""
    c.execute('''INSERT INTO sequencia_metas_op(op_id,data)
        SELECT p.op_id,p.data FROM planejamento_metas_op p
        WHERE NOT EXISTS (SELECT 1 FROM sequencia_metas_op s WHERE s.op_id=p.op_id AND s.data=p.data)
        ORDER BY p.inicio,p.op_id,p.data ON CONFLICT(op_id,data) DO NOTHING''')


def planos_fila(c, fabrica_id):
    return [dict(r) for r in c.execute('''SELECT p.*,s.id sequencia_id,
        o.numero,o.descricao,o.quantidade_total,o.fabrica_id
        FROM sequencia_metas_op s JOIN planejamento_metas_op p ON p.op_id=s.op_id AND p.data=s.data
        JOIN ordens_producao o ON o.id=p.op_id WHERE o.fabrica_id=? ORDER BY s.id''', (fabrica_id,)).fetchall()]


def calcular_fila(c, planos):
    fila, anterior = [], None
    for ordem, plano in enumerate(planos, 1):
        turno = c.execute('SELECT * FROM turnos WHERE id=?', (plano['turno_id'],)).fetchone()
        if not turno or turno['fabrica_id'] != plano['fabrica_id']:
            raise ValueError('Turno da programação não encontrado.')
        dados = dict(plano)
        if anterior:
            entrada = avancar(c, dict(turno), datetime.fromisoformat(anterior), 0)
            dados.update(inicio=entrada.isoformat(), data=entrada.date().isoformat())
        else:
            dados['data'] = datetime.fromisoformat(dados['inicio']).date().isoformat()
        resultado = calcular(c, plano, dict(turno), dados)
        fila.append(dict(plano=plano, ordem=ordem, resultado=resultado))
        anterior = resultado['saida']
    return fila


def metas_programadas(c, fila):
    """Distribui peças prontas, incluindo atravessamento, pausas e saldo final."""
    dias = {}
    def adicionar(dia, hora, qtd, oid):
        item = dias.setdefault(dia, dict(meta=0.0, periodos={}, ops={}))
        item['meta'] += qtd
        item['periodos'][hora] = item['periodos'].get(hora, 0.0) + qtd
        item['ops'][oid] = item['ops'].get(oid, 0.0) + qtd
    for item in fila:
        p, r = item['plano'], item['resultado']
        turno = dict(c.execute('SELECT * FROM turnos WHERE id=?', (p['turno_id'],)).fetchone())
        inicio, primeira, fim = (datetime.fromisoformat(r[k]) for k in ('entrada','primeira_peca','saida'))
        taxa = float(p['operadores']) / float(p['tempo_padrao']) * float(p['eficiencia']) / 100
        emitidas = 1.0
        dia = inicio.date()
        while dia <= fim.date():
            # Presença no planejamento, mesmo durante o atravessamento sem peças prontas.
            dias.setdefault(dia.isoformat(), dict(meta=0.0, periodos={}, ops={}))
            for a,b in intervalos(c, turno, dia):
                # Exibe a jornada inteira, incluindo períodos antes da primeira peça
                # e depois da conclusão da OP, sem acrescentar peças à meta.
                horario = a
                while horario < b:
                    fronteira = horario.replace(minute=0,second=0,microsecond=0)+timedelta(hours=1)
                    adicionar(horario.date().isoformat(),fronteira.strftime('%H:%M'),0.0,p['op_id'])
                    horario = min(b, fronteira)
                atual, limite = max(a, primeira), min(b, fim)
                while atual < limite:
                    fronteira = atual.replace(minute=0,second=0,microsecond=0)+timedelta(hours=1)
                    final = min(limite, fronteira)
                    quantidade = (final-atual).total_seconds()/60*taxa
                    emitidas += quantidade
                    adicionar(atual.date().isoformat(), fronteira.strftime('%H:%M'),quantidade, p['op_id'])
                    atual = final
            dia += timedelta(days=1)
        hora = primeira.replace(minute=0,second=0,microsecond=0)
        if primeira != hora:
            hora += timedelta(hours=1)
        adicionar(primeira.date().isoformat(),hora.strftime('%H:%M'),1.0,p['op_id'])
        # Remove apenas o resíduo numérico do arredondamento de microssegundos.
        ajuste = p['quantidade_total'] - emitidas
        if ajuste:
            ultimo = fim.replace(minute=0,second=0,microsecond=0)
            if ultimo != fim:
                ultimo += timedelta(hours=1)
            adicionar(fim.date().isoformat(),ultimo.strftime('%H:%M'),ajuste,p['op_id'])
    return dias


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
                atravessamento=times*ciclo, entrada=entrada.isoformat(),
                primeira_peca=primeira.isoformat(), saida=saida.isoformat())


def registrar_metas(app, m, get_user, fab_ids, login_required):
    @app.get('/api/metas-op/fila')
    def api_fila_metas():
        user = get_user()
        if not user:
            return jsonify(erro='Entre no sistema.'), 401
        c = m.conn()
        try:
            filas = []
            for fid in fab_ids(user):
                filas.extend(calcular_fila(c, planos_fila(c, fid)))
            return jsonify(fila=filas)
        except (ValueError, TypeError, KeyError, OverflowError):
            return jsonify(erro='Confira os horários e quantidades das OPs já programadas.'), 400
        finally:
            c.close()

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
            if dados.get('salvar'):
                if getattr(m, 'PG_MODE', False):
                    c.execute('SELECT pg_advisory_xact_lock(?)', (74210000 + op['fabrica_id'],))
                else:
                    c.execute('BEGIN IMMEDIATE')
            planos = planos_fila(c, op['fabrica_id'])
            chave = dados.get('data_original') or dados['data']
            indice = next((i for i,p in enumerate(planos) if p['op_id']==op['id'] and p['data']==chave), None)
            existente = indice is not None
            if dados.get('data_original') and not existente:
                raise ValueError('Planejamento original não encontrado.')
            if indice is None:
                indice = len(planos)
            if indice == 0:
                calcular(c, op, dict(turno), dados)
            candidato = dict(dados, op_id=op['id'], turno_id=turno['id'], fabrica_id=op['fabrica_id'],
                             numero=op['numero'], descricao=op['descricao'], quantidade_total=op['quantidade_total'])
            if indice < len(planos):
                candidato['data'] = planos[indice]['data']
                planos[indice] = candidato
            else:
                planos.append(candidato)
            fila = calcular_fila(c, planos)
            resultado = fila[indice]['resultado']
            # A chave do cadastro permanece estável quando o início automático muda.
            data_cadastro = chave if existente else resultado['entrada'][:10]
            if dados.get('salvar'):
                c.execute('''INSERT INTO planejamento_metas_op
                    (op_id,data,turno_id,tempo_padrao,operadores,times,ciclo,eficiencia,inicio,atualizado_por)
                    VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(op_id,data) DO UPDATE SET
                    turno_id=excluded.turno_id,tempo_padrao=excluded.tempo_padrao,
                    operadores=excluded.operadores,times=excluded.times,ciclo=excluded.ciclo,
                    eficiencia=excluded.eficiencia,inicio=excluded.inicio,atualizado_por=excluded.atualizado_por''',
                    (op['id'], data_cadastro, turno['id'], float(dados['tempo_padrao']), int(dados['operadores']),
                     int(dados['times']), float(dados['ciclo']), float(dados['eficiencia']),
                     dados['inicio'] if indice == 0 else resultado['entrada'], user['id']))
                c.execute('INSERT INTO sequencia_metas_op(op_id,data) VALUES (?,?) ON CONFLICT(op_id,data) DO NOTHING', (op['id'],data_cadastro))
                c.commit()
                fila = calcular_fila(c, planos_fila(c, op['fabrica_id']))
            return jsonify(ok=True, resultado=resultado, fila=fila, data_original=data_cadastro)
        except (ValueError, TypeError, KeyError, OverflowError):
            return jsonify(erro='Confira os campos, a quantidade da OP e os horários do turno/calendário.'), 400
        finally:
            c.close()
