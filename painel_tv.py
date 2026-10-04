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

    @app.post('/api/painel-producao/meta-dia')
    def salvar_meta_dia():
        user = get_user()
        if user is None:
            return jsonify(erro='Entre no sistema para definir a meta.'), 401
        if user['perfil'] not in ('gestor', 'admin'):
            return jsonify(erro='Somente gestores e administradores podem definir a meta.'), 403
        d = request.get_json(silent=True) or {}
        try:
            dia = d['data']
            if not isinstance(dia, str) or date.fromisoformat(dia).isoformat() != dia:
                raise ValueError()
            fid = d['fabrica_id']
            qtd = d['quantidade']
            if type(fid) is not int or type(qtd) is not int or not 1 <= qtd <= 10000000:
                raise ValueError()
        except (KeyError, TypeError, ValueError):
            return jsonify(erro='Informe fábrica, data e uma meta inteira entre 1 e 10.000.000 peças.'), 400
        if fid not in fab_ids(user):
            return jsonify(erro='Fábrica não autorizada.'), 403
        c = m.conn()
        try:
            c.execute('''INSERT INTO metas_producao_dia
                         (fabrica_id,data,quantidade,atualizado_por,atualizado_em)
                         VALUES (?,?,?,?,?) ON CONFLICT (fabrica_id,data) DO UPDATE SET
                         quantidade=excluded.quantidade,atualizado_por=excluded.atualizado_por,
                         atualizado_em=excluded.atualizado_em''',
                      (fid, dia, qtd, user['id'], datetime.now(timezone(timedelta(hours=-3))).isoformat()))
            c.commit()
        finally:
            c.close()
        return jsonify(ok=True)

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
            meta_row = c.execute('SELECT quantidade FROM metas_producao_dia WHERE fabrica_id=? AND data=?',
                                 (fid, dia)).fetchone() if fid is not None else None
            meta_dia = meta_row['quantidade'] if meta_row else None
            totais = resumo(rows)
            result = dict(data=dia, atualizado_em=agora.isoformat(), fabrica_id=fid,
                          fabricas=fabricas, resumo=totais, ops=ordens,
                          pode_editar_meta=user['perfil'] in ('gestor', 'admin'),
                          meta_dia=dict(quantidade=meta_dia,
                                        atingimento=round(totais['produzido'] / meta_dia * 100, 1) if meta_dia else None,
                                        faltam=max(0, meta_dia - totais['produzido']) if meta_dia else None),
                          horas=[dict(hora=h, **resumo(items)) for h, items in sorted(horas.items())],
                          recentes=[dict(id=r['id'], numero=r['numero'], referencia=r['referencia'] or '',
                                         hora=r['hora'], operadores=r['operadores'], **resumo([r]))
                                    for r in reversed(rows[-6:])])
        finally:
            c.close()
        response = jsonify(result)
        response.headers['Cache-Control'] = 'no-store'
        return response
