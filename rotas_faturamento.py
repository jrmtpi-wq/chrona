# ── FATURAMENTO ────────────────────────────────────────────────
@app.route('/faturamento')
@login_required
def faturamento():
    user = get_user()
    fids_list = fab_ids(user)
    ph = ','.join('?'*len(fids_list))
    c = m.conn()
    ops = c.execute(f"""
        SELECT op.*,r.codigo ref_codigo
        FROM ordens_producao op
        LEFT JOIN referencias r ON op.referencia_id=r.id
        WHERE op.fabrica_id IN ({ph})
        ORDER BY op.id DESC
    """, fids_list).fetchall()
    fabricas = c.execute(f"SELECT * FROM fabricas WHERE id IN ({ph})", fids_list).fetchall()
    c.close()
    from datetime import date
    hoje = date.today().strftime('%Y-%m-%d')
    mes_atual = date.today().strftime('%Y-%m')
    # Gerar lista de meses (últimos 12)
    from datetime import datetime
    meses = []
    for i in range(12):
        d = date.today().replace(day=1)
        mes = (d.month - i - 1) % 12 + 1
        ano = d.year - ((d.month - i - 1) // 12)
        meses.append({
            'valor': f'{ano}-{str(mes).zfill(2)}',
            'label': datetime(ano, mes, 1).strftime('%b/%Y').upper(),
            'atual': f'{ano}-{str(mes).zfill(2)}' == mes_atual
        })
    return render_template('faturamento.html', user=user,
        ops=[dict(r) for r in ops],
        fabricas=[dict(r) for r in fabricas],
        meses=meses, hoje=hoje)


@app.route('/api/faturamentos')
@login_required
def api_faturamentos_lista():
    user = get_user(); fids_list = fab_ids(user)
    ph = ','.join('?'*len(fids_list))
    mes = request.args.get('mes','')
    fab_id = request.args.get('fabrica_id','')
    c = m.conn()
    sql = f"""
        SELECT f.*,op.numero op_numero,op.descricao,r.codigo ref_codigo,
               fab.nome fab_nome
        FROM faturamento f
        LEFT JOIN ordens_producao op ON f.op_id=op.id
        LEFT JOIN referencias r ON op.referencia_id=r.id
        LEFT JOIN fabricas fab ON f.fabrica_id=fab.id
        WHERE f.fabrica_id IN ({ph})
    """
    params = list(fids_list)
    if mes: sql += " AND f.data LIKE ?"; params.append(f'{mes}%')
    if fab_id: sql += " AND f.fabrica_id=?"; params.append(fab_id)
    sql += " ORDER BY f.data DESC"
    rows = [dict(r) for r in c.execute(sql, params).fetchall()]
    c.close()
    return jsonify(rows)


@app.route('/api/faturamento/salvar', methods=['POST'])
@login_required
def api_faturamento_salvar():
    user = get_user(); d = request.json; c = m.conn()
    fab_id = int(d.get('fabrica_id') or resolve_fab_id(d, user))
    try:
        if d.get('id'):
            c.execute("""UPDATE faturamento SET op_id=?,fabrica_id=?,data=?,
                         quantidade=?,valor_unitario=?,valor_total=?,
                         numero_nf=?,tipo=?,obs=? WHERE id=?""",
                      (d['op_id'], fab_id, d['data'], d['quantidade'],
                       d['valor_unitario'], d['valor_total'],
                       d.get('numero_nf',''), d.get('tipo','CONCLUIDA'),
                       d.get('obs',''), d['id']))
        else:
            c.execute("""INSERT INTO faturamento (op_id,fabrica_id,data,quantidade,
                         valor_unitario,valor_total,numero_nf,tipo,obs)
                         VALUES (?,?,?,?,?,?,?,?,?)""",
                      (d['op_id'], fab_id, d['data'], d['quantidade'],
                       d['valor_unitario'], d['valor_total'],
                       d.get('numero_nf',''), d.get('tipo','CONCLUIDA'),
                       d.get('obs','')))
        c.commit(); c.close()
        return jsonify({'ok': True})
    except Exception as e:
        c.close(); return jsonify({'ok': False, 'erro': str(e)})


@app.route('/api/faturamento/<int:fid>')
@login_required
def api_faturamento_get(fid):
    c = m.conn()
    r = c.execute("SELECT * FROM faturamento WHERE id=?", (fid,)).fetchone()
    c.close(); return jsonify(dict(r) if r else {})


@app.route('/api/faturamento/excluir/<int:fid>', methods=['DELETE'])
@login_required
def api_faturamento_excluir(fid):
    c = m.conn()
    c.execute("DELETE FROM faturamento WHERE id=?", (fid,))
    c.commit(); c.close(); return jsonify({'ok': True})


# ── NOTAS FISCAIS ──────────────────────────────────────────────
@app.route('/api/notas-fiscais')
@login_required
def api_nfs_lista():
    user = get_user(); fids_list = fab_ids(user)
    ph = ','.join('?'*len(fids_list))
    mes = request.args.get('mes','')
    fab_id = request.args.get('fabrica_id','')
    c = m.conn()
    sql = f"""
        SELECT nf.*,fab.nome fab_nome FROM notas_fiscais nf
        LEFT JOIN fabricas fab ON nf.fabrica_id=fab.id
        WHERE nf.fabrica_id IN ({ph})
    """
    params = list(fids_list)
    if mes: sql += " AND nf.data LIKE ?"; params.append(f'{mes}%')
    if fab_id: sql += " AND nf.fabrica_id=?"; params.append(fab_id)
    sql += " ORDER BY nf.data DESC"
    rows = [dict(r) for r in c.execute(sql, params).fetchall()]
    c.close(); return jsonify(rows)


@app.route('/api/nota-fiscal/salvar', methods=['POST'])
@login_required
def api_nf_salvar():
    user = get_user(); d = request.json; c = m.conn()
    fab_id = int(d.get('fabrica_id') or resolve_fab_id(d, user))
    try:
        if d.get('id'):
            c.execute("""UPDATE notas_fiscais SET numero=?,data=?,cliente=?,
                         fabrica_id=?,valor=?,ops_vinculadas=?,obs=? WHERE id=?""",
                      (d['numero'],d['data'],d['cliente'],fab_id,
                       d['valor'],d.get('ops_vinculadas',''),d.get('obs',''),d['id']))
        else:
            c.execute("""INSERT INTO notas_fiscais (numero,data,cliente,fabrica_id,
                         valor,ops_vinculadas,obs) VALUES (?,?,?,?,?,?,?)""",
                      (d['numero'],d['data'],d['cliente'],fab_id,
                       d['valor'],d.get('ops_vinculadas',''),d.get('obs','')))
        c.commit(); c.close(); return jsonify({'ok': True})
    except Exception as e:
        c.close(); return jsonify({'ok': False, 'erro': str(e)})


@app.route('/api/nota-fiscal/<int:nid>')
@login_required
def api_nf_get(nid):
    c = m.conn()
    r = c.execute("SELECT * FROM notas_fiscais WHERE id=?", (nid,)).fetchone()
    c.close(); return jsonify(dict(r) if r else {})


@app.route('/api/nota-fiscal/excluir/<int:nid>', methods=['DELETE'])
@login_required
def api_nf_excluir(nid):
    c = m.conn()
    c.execute("DELETE FROM notas_fiscais WHERE id=?", (nid,))
    c.commit(); c.close(); return jsonify({'ok': True})
