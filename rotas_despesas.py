# ── DESPESAS ───────────────────────────────────────────────────
@app.route('/despesas')
@login_required
def despesas():
    user = get_user()
    fids_list = fab_ids(user)
    ph = ','.join('?'*len(fids_list))
    c = m.conn()
    fabricas = c.execute(f"SELECT * FROM fabricas WHERE id IN ({ph})", fids_list).fetchall()
    categorias = c.execute("SELECT * FROM categorias_despesa ORDER BY ordem,nome").fetchall()
    c.close()
    from datetime import date, datetime
    hoje = date.today().strftime('%Y-%m-%d')
    mes_atual = date.today().strftime('%Y-%m')
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
    return render_template('despesas.html', user=user,
        fabricas=[dict(r) for r in fabricas],
        categorias=[dict(r) for r in categorias],
        meses=meses, hoje=hoje)


@app.route('/api/despesas')
@login_required
def api_despesas_lista():
    user = get_user(); fids_list = fab_ids(user)
    ph = ','.join('?'*len(fids_list))
    mes = request.args.get('mes','')
    fab_id = request.args.get('fabrica_id','')
    cat_id = request.args.get('categoria_id','')
    c = m.conn()
    sql = f"""
        SELECT d.*,cat.nome cat_nome,fab.nome fab_nome
        FROM despesas d
        LEFT JOIN categorias_despesa cat ON d.categoria_id=cat.id
        LEFT JOIN fabricas fab ON d.fabrica_id=fab.id
        WHERE d.fabrica_id IN ({ph})
    """
    params = list(fids_list)
    if mes: sql += " AND d.mes LIKE ?"; params.append(f'{mes}%')
    if fab_id: sql += " AND d.fabrica_id=?"; params.append(fab_id)
    if cat_id: sql += " AND d.categoria_id=?"; params.append(cat_id)
    sql += " ORDER BY d.data DESC, cat.nome"
    rows = [dict(r) for r in c.execute(sql, params).fetchall()]
    c.close(); return jsonify(rows)


@app.route('/api/despesa/salvar', methods=['POST'])
@login_required
def api_despesa_salvar():
    user = get_user(); d = request.json; c = m.conn()
    fab_id = int(d.get('fabrica_id') or resolve_fab_id(d, user))
    mes = d['data'][:7] if d.get('data') else ''
    try:
        if d.get('id'):
            c.execute("""UPDATE despesas SET categoria_id=?,fabrica_id=?,mes=?,
                         data=?,valor=?,tipo=?,numero_doc=?,fornecedor=?,obs=? WHERE id=?""",
                      (d['categoria_id'], fab_id, mes, d['data'],
                       d['valor'], d.get('tipo','FIXA'),
                       d.get('numero_doc',''), d.get('fornecedor',''),
                       d.get('obs',''), d['id']))
        else:
            c.execute("""INSERT INTO despesas (categoria_id,fabrica_id,mes,data,valor,
                         tipo,numero_doc,fornecedor,obs)
                         VALUES (?,?,?,?,?,?,?,?,?)""",
                      (d['categoria_id'], fab_id, mes, d['data'],
                       d['valor'], d.get('tipo','FIXA'),
                       d.get('numero_doc',''), d.get('fornecedor',''),
                       d.get('obs','')))
        c.commit(); c.close(); return jsonify({'ok': True})
    except Exception as e:
        c.close(); return jsonify({'ok': False, 'erro': str(e)})


@app.route('/api/despesa/<int:did>')
@login_required
def api_despesa_get(did):
    c = m.conn()
    r = c.execute("SELECT * FROM despesas WHERE id=?", (did,)).fetchone()
    c.close(); return jsonify(dict(r) if r else {})


@app.route('/api/despesa/excluir/<int:did>', methods=['DELETE'])
@login_required
def api_despesa_excluir(did):
    c = m.conn()
    c.execute("DELETE FROM despesas WHERE id=?", (did,))
    c.commit(); c.close(); return jsonify({'ok': True})


# ── DOCUMENTOS DE DESPESA ──────────────────────────────────────
@app.route('/api/despesas/docs')
@login_required
def api_despesas_docs_lista():
    user = get_user(); fids_list = fab_ids(user)
    ph = ','.join('?'*len(fids_list))
    mes = request.args.get('mes','')
    fab_id = request.args.get('fabrica_id','')
    c = m.conn()
    sql = f"""
        SELECT dd.*,cat.nome cat_nome,fab.nome fab_nome
        FROM despesas_docs dd
        LEFT JOIN categorias_despesa cat ON dd.categoria_id=cat.id
        LEFT JOIN fabricas fab ON dd.fabrica_id=fab.id
        WHERE dd.fabrica_id IN ({ph})
    """
    params = list(fids_list)
    if mes: sql += " AND dd.data LIKE ?"; params.append(f'{mes}%')
    if fab_id: sql += " AND dd.fabrica_id=?"; params.append(fab_id)
    sql += " ORDER BY dd.data DESC"
    rows = [dict(r) for r in c.execute(sql, params).fetchall()]
    c.close(); return jsonify(rows)


@app.route('/api/despesa/doc/salvar', methods=['POST'])
@login_required
def api_despesa_doc_salvar():
    user = get_user(); d = request.json; c = m.conn()
    fab_id = int(d.get('fabrica_id') or resolve_fab_id(d, user))
    try:
        if d.get('id'):
            c.execute("""UPDATE despesas_docs SET numero=?,data=?,fornecedor=?,
                         categoria_id=?,fabrica_id=?,valor=?,obs=? WHERE id=?""",
                      (d['numero'],d['data'],d['fornecedor'],
                       d.get('categoria_id'),fab_id,d['valor'],
                       d.get('obs',''),d['id']))
        else:
            c.execute("""INSERT INTO despesas_docs (numero,data,fornecedor,
                         categoria_id,fabrica_id,valor,obs)
                         VALUES (?,?,?,?,?,?,?)""",
                      (d['numero'],d['data'],d['fornecedor'],
                       d.get('categoria_id'),fab_id,d['valor'],d.get('obs','')))
        c.commit(); c.close(); return jsonify({'ok': True})
    except Exception as e:
        c.close(); return jsonify({'ok': False, 'erro': str(e)})


@app.route('/api/despesa/doc/<int:did>')
@login_required
def api_despesa_doc_get(did):
    c = m.conn()
    r = c.execute("SELECT * FROM despesas_docs WHERE id=?", (did,)).fetchone()
    c.close(); return jsonify(dict(r) if r else {})


@app.route('/api/despesa/doc/excluir/<int:did>', methods=['DELETE'])
@login_required
def api_despesa_doc_excluir(did):
    c = m.conn()
    c.execute("DELETE FROM despesas_docs WHERE id=?", (did,))
    c.commit(); c.close(); return jsonify({'ok': True})
