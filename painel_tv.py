"""Gestão à vista: realizado do Lançamento e metas da programação das OPs."""
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from flask import jsonify, render_template, request
from metas_op import planos_fila, calcular_fila, metas_programadas, atualizar_previsoes
from entrada_grupo import registrar_entrada, metas_entrada, painel_entrada


def resumo(rows):
    produzido = sum(r['qtd_produzida'] or 0 for r in rows)
    meta = sum(r['qtd_projetada'] or 0 for r in rows)
    return dict(produzido=produzido, meta=meta, lancamentos=len(rows),
                eficiencia=round(produzido / meta * 100, 1) if meta > 0 else None,
                saldo=produzido - meta)


def registrar_painel(app, m, get_user, fab_ids, login_required):
    registrar_entrada(app, m, get_user, fab_ids)
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
            periodos = defaultdict(list)
            ops = defaultdict(list)
            for row in rows:
                horas[row['hora'][:2] + ':00'].append(row)
                periodos[row['hora'][:5]].append(row)
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
            inicio_mes = dia[:7] + '-01'
            mensal = c.execute('''
                SELECT COALESCE(SUM(p.qtd_produzida),0) produzido,
                       COUNT(DISTINCT CASE WHEN md.data IS NULL THEN p.data END) dias_sem_meta
                FROM producao p
                JOIN ordens_producao op ON op.id=p.op_id AND op.fabrica_id=p.fabrica_id
                LEFT JOIN metas_producao_dia md ON md.fabrica_id=p.fabrica_id AND md.data=p.data
                WHERE p.fabrica_id=? AND p.data>=? AND p.data<=?
            ''', (fid, inicio_mes, dia)).fetchone()
            metas_mes = c.execute('''SELECT SUM(quantidade) quantidade FROM metas_producao_dia
                                    WHERE fabrica_id=? AND data>=? AND data<=?''',
                                 (fid, inicio_mes, dia)).fetchone()['quantidade']
            fila = calcular_fila(c, planos_fila(c, fid)) if fid is not None else []
            planejados = metas_programadas(c, fila)
            entrada_planejada = metas_entrada(c, fila)
            previsoes = atualizar_previsoes(c, fila, agora)
            dias_previstos = metas_programadas(c, previsoes)
            previsao_por_op = {(i['plano']['op_id'], i['plano']['data']): i for i in previsoes}
            plano_dia = planejados.get(dia)
            programacao = []
            if plano_dia is not None:
                meta_dia = plano_dia['meta']
                totais.update(meta=meta_dia, saldo=totais['produzido']-meta_dia,
                              eficiencia=round(totais['produzido']/meta_dia*100,1) if meta_dia else None)
                # Apontamentos pertencem ao período horário que termina no próximo relógio cheio.
                periodos = defaultdict(list)
                for row in rows:
                    h, minuto = map(int,row['hora'][:5].split(':'))
                    horario = f'{(h + (1 if minuto else 0)) % 24:02d}:00'
                    periodos[horario].append(row)
                for horario in plano_dia['periodos']:
                    periodos[horario]  # Inclui metas ainda sem apontamento.
                periodos_planejados = []
                for horario, items in sorted(periodos.items()):
                    r = resumo(items)
                    meta = plano_dia['periodos'].get(horario,0)
                    r.update(meta=meta,saldo=r['produzido']-meta,
                             eficiencia=round(r['produzido']/meta*100,1) if meta else None)
                    pendente = dia > agora.date().isoformat() or (
                        dia == agora.date().isoformat() and horario > agora.strftime('%H:%M'))
                    r['pendente'] = pendente
                    if pendente:
                        r.update(saldo=None, eficiencia=None)
                    periodos_planejados.append(dict(hora=horario,**r,
                        apontamentos=[dict(id=i['id'],op_id=i['op_id'],numero=i['numero'],hora=i['hora'],quantidade=i['qtd_produzida']) for i in items]))
                por_op = {o['op_id']:o for o in ordens}
                for item in fila:
                    p,r = item['plano'],item['resultado']
                    if r['entrada'][:10] <= dia <= r['saida'][:10]:
                        programacao.append(dict(op_id=p['op_id'],numero=p['numero'],descricao=p['descricao'],
                                                quantidade=p['quantidade_total'],meta=plano_dia['ops'].get(p['op_id'],0),**r))
                        revisao = previsao_por_op[(p['op_id'], p['data'])]
                        programacao[-1]['previsao'] = revisao['resultado']
                        programacao[-1]['restante_atual'] = revisao['restante']
                        programacao[-1]['ultimo_apontamento'] = revisao['ultimo_apontamento']
                        if p['op_id'] not in por_op:
                            total = c.execute('SELECT COALESCE(SUM(qtd_produzida),0) total FROM producao WHERE fabrica_id=? AND op_id=? AND data<=?',(fid,p['op_id'],dia)).fetchone()['total']
                            por_op[p['op_id']] = dict(op_id=p['op_id'],numero=p['numero'],descricao=p['descricao'] or '',referencia='',
                                                      quantidade=p['quantidade_total'],acumulado=total,restante=max(0,p['quantidade_total']-total),
                                                      ultimo_periodo='',**resumo([]))
                for oid,o in por_op.items():
                    meta=plano_dia['ops'].get(oid,0)
                    o.update(meta=meta,saldo=o['produzido']-meta,eficiencia=round(o['produzido']/meta*100,1) if meta else None)
                ordens=list(por_op.values())
            if planejados:
                metas_por_dia = {r['data']:r['quantidade'] for r in c.execute(
                    'SELECT data,quantidade FROM metas_producao_dia WHERE fabrica_id=? AND data>=? AND data<=?',
                    (fid,inicio_mes,dia)).fetchall()}
                metas_por_dia.update({d:p['meta'] for d,p in planejados.items() if inicio_mes<=d<=dia})
                metas_mes=sum(metas_por_dia.values()) if metas_por_dia else None
                datas_apontadas = [r['data'] for r in c.execute('''SELECT DISTINCT p.data FROM producao p
                    JOIN ordens_producao op ON op.id=p.op_id AND op.fabrica_id=p.fabrica_id
                    WHERE p.fabrica_id=? AND p.data>=? AND p.data<=?''',(fid,inicio_mes,dia)).fetchall()]
                mensal=dict(mensal)
                mensal['dias_sem_meta']=sum(d not in metas_por_dia for d in datas_apontadas)
            mes_completo = metas_mes is not None and metas_mes > 0 and mensal['dias_sem_meta'] == 0
            acompanhamento = None
            if plano_dia is not None:
                encerrados = [p for p in periodos_planejados if not p['pendente']]
                acompanhamento = resumo([dict(qtd_produzida=p['produzido'], qtd_projetada=p['meta'])
                                         for p in encerrados])
            realizado_dia = acompanhamento['produzido'] if acompanhamento is not None else totais['produzido']
            result = dict(data=dia, atualizado_em=agora.isoformat(), fabrica_id=fid,
                          entrada=painel_entrada(c, fid, dia, agora, entrada_planejada.get(dia)),
                          acompanhamento=acompanhamento,
                          previsao_dia=(dict(quantidade=dias_previstos.get(dia, {}).get('meta', 0) + realizado_dia)
                                        if fila and dia == agora.date().isoformat() else None),
                          fabricas=fabricas, resumo=totais, ops=ordens,
                          pode_editar_meta=user['perfil'] in ('gestor', 'admin') and plano_dia is None,
                          fonte_meta='programacao' if plano_dia is not None else 'lancamentos',
                          programacao=programacao,
                          meta_dia=dict(quantidade=meta_dia,
                                        atingimento=round(realizado_dia / meta_dia * 100, 1) if meta_dia else None,
                                        faltam=max(0, meta_dia - realizado_dia) if meta_dia else None),
                          mes=dict(inicio=inicio_mes, fim=dia, meta=metas_mes,
                                   produzido=mensal['produzido'], dias_sem_meta=mensal['dias_sem_meta'],
                                   eficiencia=round(mensal['produzido'] / metas_mes * 100, 1) if mes_completo else None),
                          periodos=periodos_planejados if plano_dia is not None else [dict(hora=h, **resumo(items),
                              apontamentos=[dict(id=i['id'],op_id=i['op_id'],numero=i['numero'],hora=i['hora'],quantidade=i['qtd_produzida']) for i in items]) for h, items in sorted(periodos.items())],
                          horas=periodos_planejados if plano_dia is not None else [dict(hora=h, **resumo(items)) for h, items in sorted(horas.items())],
                          recentes=[dict(id=r['id'], numero=r['numero'], referencia=r['referencia'] or '',
                                         hora=r['hora'], operadores=r['operadores'], **resumo([r]))
                                    for r in reversed(rows[-6:])])
        finally:
            c.close()
        response = jsonify(result)
        response.headers['Cache-Control'] = 'no-store'
        return response
