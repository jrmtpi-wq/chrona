# ── FILA DE PRODUÇÃO ───────────────────────────────────────────
@app.route('/fila-producao')
@login_required
def fila_producao():
    user = get_user()
    fids_list = fab_ids(user)
    ph = ','.join('?'*len(fids_list))
    c = m.conn()
    ops = c.execute(f"""
        SELECT op.*,r.codigo ref_codigo
        FROM ordens_producao op
        LEFT JOIN referencias r ON op.referencia_id=r.id
        WHERE op.fabrica_id IN ({ph}) AND op.situacao IN ('ABERTA','PRODUCAO')
        ORDER BY op.id DESC
    """, fids_list).fetchall()
    turnos = c.execute(f"""
        SELECT * FROM turnos WHERE fabrica_id IN ({ph}) AND ativo=1 ORDER BY numero
    """, fids_list).fetchall()
    c.close()
    return render_template('fila_producao.html', user=user,
        ops=[dict(r) for r in ops],
        turnos=[dict(r) for r in turnos])
