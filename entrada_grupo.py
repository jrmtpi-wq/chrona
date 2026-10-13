"""Apontamentos e metas do primeiro time, independentes da saída pronta."""
import math
from collections import defaultdict
from datetime import date, datetime, timedelta
from flask import jsonify, request
from metas_op import avancar, metas_programadas, intervalos, hora_periodo_painel


def meta_por_op_apontada(c, dia, grupos, planejado, fila):
    """A OP registrada no primeiro time define a meta de entrada a partir daquele período."""
    planos = {}
    for item in fila:
        p = item['plano']
        anterior = planos.get(p['op_id'])
        if anterior is None or (p['data'] <= dia and
                               (anterior['plano']['data'] > dia or p['data'] >= anterior['plano']['data'])):
            planos[p['op_id']] = item
    if planejado is None or not planos:
        return planejado
    metas = dict(planejado['periodos'])
    identificadas = {}
    ativa = None
    for hora in sorted(set(metas) | set(grupos)):
        ops = {r['op_id'] for r in grupos.get(hora, [])}
        if ops:
            # Uma troca dentro do mesmo período não informa a duração de cada OP.
            # Nesse caso preserva a distribuição planejada, sem duplicar uma hora.
            ativa = planos.get(next(iter(ops))) if len(ops) == 1 else None
        if ativa is None:
            continue
        p = ativa['plano']
        turno = dict(c.execute('SELECT * FROM turnos WHERE id=?', (p['turno_id'],)).fetchone())
        fim = datetime.fromisoformat(dia + 'T' + hora)
        inicio = fim.replace(minute=0) if fim.minute else fim - timedelta(hours=1)
        minutos = sum(max(0, (min(b, fim) - max(a, inicio)).total_seconds() / 60)
                      for a, b in intervalos(c, turno, date.fromisoformat(dia)))
        metas[hora] = minutos * float(p['operadores']) / float(p['tempo_padrao']) * float(p['eficiencia']) / 100
        identificadas[hora] = dict(op_id=p['op_id'], numero=p['numero'])
    return dict(planejado, periodos=metas, meta=sum(metas.values()), ops_por_periodo=identificadas)


def metas_entrada(c, fila):
    entrada = []
    for item in fila:
        p, r = item['plano'], dict(item['resultado'])
        turno = dict(c.execute('SELECT * FROM turnos WHERE id=?', (p['turno_id'],)).fetchone())
        r['primeira_peca'] = avancar(c, turno, datetime.fromisoformat(r['entrada']), float(p['ciclo'])).isoformat()
        r['saida'] = r['fim_entrada']
        entrada.append(dict(item, resultado=r))
    return metas_programadas(c, entrada)


def painel_entrada(c, fid, dia, agora, planejado, fila=()):
    from painel_tv import resumo
    rows = [dict(r) for r in c.execute('''SELECT e.* FROM entradas_producao e
        JOIN ordens_producao op ON op.id=e.op_id AND op.fabrica_id=e.fabrica_id
        WHERE e.fabrica_id=? AND e.data=? ORDER BY e.hora,e.id''', (fid, dia)).fetchall()]
    grupos = defaultdict(list)
    for row in rows:
        grupos[hora_periodo_painel(row['hora'], (planejado or {}).get('periodos', {}))].append(row)
    planejado = meta_por_op_apontada(c, dia, grupos, planejado, fila)
    if planejado is not None:
        for hora in planejado['periodos']:
            grupos[hora]
    periodos = []
    for hora, items in sorted(grupos.items()):
        r = resumo(items)
        meta = planejado['periodos'].get(hora, 0) if planejado is not None else r['meta']
        pendente = dia > agora.date().isoformat() or (dia == agora.date().isoformat() and hora > agora.strftime('%H:%M'))
        r.update(meta=meta, pendente=pendente,
                 saldo=None if pendente else r['produzido'] - meta,
                 eficiencia=None if pendente or not meta else round(r['produzido'] / meta * 100, 1))
        periodos.append(dict(hora=hora, **r,
                             op_meta=(planejado or {}).get('ops_por_periodo', {}).get(hora)))
    total = resumo(rows)
    meta_dia = planejado['meta'] if planejado is not None else total['meta']
    total.update(meta=meta_dia, saldo=total['produzido']-meta_dia,
                 eficiencia=round(total['produzido']/meta_dia*100, 1) if meta_dia else None)
    encerrados = [p for p in periodos if not p['pendente']]
    acompanhamento = resumo([dict(qtd_produzida=p['produzido'], qtd_projetada=p['meta']) for p in encerrados])
    return dict(periodos=periodos, resumo=total, acompanhamento=acompanhamento,
                fonte_meta='programacao' if planejado is not None else 'lancamentos')


def registrar_entrada(app, m, get_user, fab_ids):
    @app.route('/api/entrada-grupo', methods=['GET', 'POST'])
    def entrada_grupo():
        user = get_user()
        if user is None:
            return jsonify(erro='Entre no sistema.'), 401
        ids = [i for i in fab_ids(user) if i is not None]
        c = m.conn()
        try:
            if request.method == 'GET':
                dia = request.args.get('data', '')
                if date.fromisoformat(dia).isoformat() != dia:
                    raise ValueError()
                if not ids:
                    return jsonify([])
                ph = ','.join('?' * len(ids))
                rows = c.execute(f'''SELECT e.*,op.numero FROM entradas_producao e
                    JOIN ordens_producao op ON op.id=e.op_id AND op.fabrica_id=e.fabrica_id
                    WHERE e.fabrica_id IN ({ph}) AND e.data=? ORDER BY e.hora,e.id''', [*ids, dia]).fetchall()
                response = jsonify([dict(r) for r in rows])
                response.headers['Cache-Control'] = 'no-store'
                return response
            d = request.get_json(silent=True) or {}
            dia, hora, qtd, meta, oid = d['data'], d['hora'], d['quantidade'], d.get('meta', 0), d['op_id']
            if (date.fromisoformat(dia).isoformat() != dia or
                    datetime.strptime(hora, '%H:%M').strftime('%H:%M') != hora or
                    type(qtd) is not int or not 0 <= qtd <= 10000000 or
                    type(meta) not in (int, float) or not math.isfinite(meta) or not 0 <= meta <= 10000000 or
                    type(oid) is not int):
                raise ValueError()
            op = c.execute('SELECT fabrica_id FROM ordens_producao WHERE id=?', (oid,)).fetchone()
            if op is None or op['fabrica_id'] not in ids:
                return jsonify(erro='OP não autorizada.'), 403
            if d.get('id') is not None:
                if type(d['id']) is not int:
                    raise ValueError()
                existente = c.execute('SELECT fabrica_id FROM entradas_producao WHERE id=?', (d['id'],)).fetchone()
                if existente is None or existente['fabrica_id'] not in ids:
                    return jsonify(erro='Lançamento não autorizado.'), 403
                c.execute('''UPDATE entradas_producao SET fabrica_id=?,op_id=?,data=?,hora=?,qtd_produzida=?,qtd_projetada=? WHERE id=?''',
                          (op['fabrica_id'], oid, dia, hora, qtd, meta, d['id']))
            else:
                c.execute('''INSERT INTO entradas_producao(fabrica_id,op_id,data,hora,qtd_produzida,qtd_projetada)
                             VALUES(?,?,?,?,?,?)''', (op['fabrica_id'], oid, dia, hora, qtd, meta))
            c.commit()
            return jsonify(ok=True)
        except (KeyError, ValueError, TypeError, OverflowError):
            return jsonify(erro='Informe OP, data, horário e quantidades válidas.'), 400
        finally:
            c.close()

    @app.delete('/api/entrada-grupo/<int:lid>')
    def excluir_entrada_grupo(lid):
        user = get_user()
        if user is None:
            return jsonify(erro='Entre no sistema.'), 401
        c = m.conn()
        try:
            row = c.execute('SELECT fabrica_id FROM entradas_producao WHERE id=?', (lid,)).fetchone()
            if row is None or row['fabrica_id'] not in fab_ids(user):
                return jsonify(erro='Lançamento não autorizado.'), 403
            c.execute('DELETE FROM entradas_producao WHERE id=?', (lid,))
            c.commit()
            return jsonify(ok=True)
        finally:
            c.close()
