"""Gestão à vista: leitura exclusiva dos registros da tela Lançamento."""
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from flask import jsonify, render_template, request


def resumo(rows):
    produzido = sum(r['qtd_produzida'] or 0 for r in rows)
    meta = sum(r['qtd_projetada'] or 0 for r in rows)
    return dict(produzido=produzido, meta=meta, lancamentos=len(rows),
                eficiencia=round(produzido / meta * 100, 1) if meta > 0 else None,
                saldo=produzido - meta)


def registrar_painel(app, m, get_user, fab_ids, login_required):
    @app.get('/painel-producao')
    @login_required
    def painel_producao():
        return render_template('painel_producao.html')

    @app.get('/api/painel-producao')
    def api_painel_producao():
        user = get_user()
        if user is None:
            return jsonify(erro='Entre no sistema para acompanhar a produção.'), 401
        agora = datetime.now(timezone(timedelta(hours=-3)))
        dia = request.args.get('data') or agora.date().isoformat()
        try:
            if date.fromisoformat(dia).isoformat() != dia:
                raise ValueError()
            fid = int(request.args['fabrica_id']) if request.args.get('fabrica_id') else None
        except ValueError:
            return jsonify(erro='Data ou fábrica inválida.'), 400
        ids = [i for i in fab_ids(user) if i is not None]
        if fid is not None and fid not in ids:
            return jsonify(erro='Fábrica não autorizada.'), 403
        c = m.conn()
        try:
            fabricas = []
            if ids:
                ph = ','.join('?' * len(ids))
                fabricas = [dict(r) for r in c.execute(
                    f'SELECT id,nome FROM fabricas WHERE id IN ({ph}) ORDER BY nome', ids).fetchall()]
            if fid is None and fabricas:
                fid = user['fabrica_id'] if user['fabrica_id'] in ids else fabricas[0]['id']
            rows = [dict(r) for r in c.execute('''
                SELECT p.id,p.op_id,p.hora,p.qtd_produzida,p.qtd_projetada,
                       p.operadores,op.numero,op.descricao,op.quantidade_total,
                       r.codigo referencia
                FROM producao p
                JOIN ordens_producao op ON op.id=p.op_id AND op.fabrica_id=p.fabrica_id
                LEFT JOIN referencias r ON r.id=op.referencia_id
                WHERE p.fabrica_id=? AND p.data=? ORDER BY p.hora,p.id
            ''', (fid, dia)).fetchall()] if fid is not None else []
            horas = defaultdict(list)
            ops = defaultdict(list)
            for row in rows:
                horas[row['hora'][:2] + ':00'].append(row)
                ops[row['op_id']].append(row)
            ordens = []
            if ops:
                ph = ','.join('?' * len(ops))
                acumulados = {r['op_id']: r['produzido'] for r in c.execute(f'''
                    SELECT op_id,SUM(COALESCE(qtd_produzida,0)) produzido FROM producao
                    WHERE fabrica_id=? AND data<=? AND op_id IN ({ph}) GROUP BY op_id
                ''', [fid, dia, *ops]).fetchall()}
                for oid, items in ops.items():
                    op = items[-1]
                    total = acumulados[oid]
                    quantidade = op['quantidade_total'] or 0
                    ordens.append(dict(op_id=oid, numero=op['numero'],
                                       referencia=op['referencia'] or '', descricao=op['descricao'] or '',
                                       quantidade=quantidade, acumulado=total,
                                       restante=max(0, quantidade - total),
                                       ultimo_periodo=op['hora'], **resumo(items)))
            ordens.sort(key=lambda o: (o['ultimo_periodo'], o['op_id']), reverse=True)
            result = dict(data=dia, atualizado_em=agora.isoformat(), fabrica_id=fid,
                          fabricas=fabricas, resumo=resumo(rows), ops=ordens,
                          horas=[dict(hora=h, **resumo(items)) for h, items in sorted(horas.items())],
                          recentes=[dict(id=r['id'], numero=r['numero'], referencia=r['referencia'] or '',
                                         hora=r['hora'], operadores=r['operadores'], **resumo([r]))
                                    for r in reversed(rows[-6:])])
        finally:
            c.close()
        response = jsonify(result)
        response.headers['Cache-Control'] = 'no-store'
        return response
