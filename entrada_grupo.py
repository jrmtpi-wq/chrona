"""Apontamentos e metas do primeiro time, independentes da saída pronta."""
import math
from collections import defaultdict
from datetime import date, datetime
from flask import jsonify, request
from metas_op import avancar, metas_programadas


def metas_entrada(c, fila):
    entrada = []
    for item in fila:
        p, r = item['plano'], dict(item['resultado'])
        turno = dict(c.execute('SELECT * FROM turnos WHERE id=?', (p['turno_id'],)).fetchone())
        r['primeira_peca'] = avancar(c, turno, datetime.fromisoformat(r['entrada']), float(p['ciclo'])).isoformat()
        r['saida'] = r['fim_entrada']
        entrada.append(dict(item, resultado=r))
    return metas_programadas(c, entrada)


def painel_entrada(c, fid, dia, agora, planejado):
    from painel_tv import resumo
    rows = [dict(r) for r in c.execute('''SELECT e.* FROM entradas_producao e
        JOIN ordens_producao op ON op.id=e.op_id AND op.fabrica_id=e.fabrica_id
        WHERE e.fabrica_id=? AND e.data=? ORDER BY e.hora,e.id''', (fid, dia)).fetchall()]
    grupos = defaultdict(list)
    for row in rows:
        h, minuto = map(int, row['hora'].split(':'))
        grupos[f'{(h + bool(minuto)) % 24:02d}:00'].append(row)
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
        periodos.append(dict(hora=hora, **r))
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
