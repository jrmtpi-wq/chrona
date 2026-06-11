from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from functools import wraps
from datetime import datetime, date
import models as m

app = Flask(__name__)
app.secret_key = 'chrona_2025_producao_secret'

@app.context_processor
def inject_globals():
    return dict(get_user=get_user, session=session)

def login_required(f):
    @wraps(f)
    def dec(*a, **kw):
        if 'uid' not in session:
            session['next'] = request.url
            return redirect(url_for('login'))
        return f(*a, **kw)
    return dec

def get_user():
    if 'uid' not in session: return None
    c = m.conn()
    u = c.execute("SELECT u.*,f.nome fab_nome FROM usuarios u LEFT JOIN fabricas f ON u.fabrica_id=f.id WHERE u.id=?",
                  (session['uid'],)).fetchone()
    c.close(); return u

def fab_ids(user):
    if user['perfil'] in ('admin','gestor'):
        c = m.conn()
        ids = [r[0] for r in c.execute("SELECT id FROM fabricas WHERE ativa=1").fetchall()]
        c.close(); return ids
    return [user['fabrica_id']]

# ── AUTH ──────────────────────────────────────────────────────
@app.route('/')
def index():
    return redirect(url_for('dashboard') if 'uid' in session else url_for('login'))

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        c = m.conn()
        u = c.execute("SELECT * FROM usuarios WHERE login=? AND senha_hash=? AND ativo=1",
                      (request.form['login'], m.hash_senha(request.form['senha']))).fetchone()
        c.close()
        if u:
            session.update({'uid':u['id'],'nome':u['nome'],'perfil':u['perfil'],'fab_id':u['fabrica_id']})
            next_url = session.pop('next', None)
            return redirect(next_url or url_for('dashboard'))
        flash('Login ou senha incorretos','error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear(); return redirect(url_for('login'))

# ── DASHBOARD ─────────────────────────────────────────────────
@app.route('/dashboard')
@login_required
def dashboard():
    user = get_user()
    c = m.conn()
    hoje = date.today().strftime('%Y-%m-%d')
    mes  = date.today().strftime('%Y-%m')
    fids = fab_ids(user)
    ph   = ','.join('?'*len(fids))

    stats = {
        'funcionarios': c.execute(f"SELECT COUNT(*) FROM funcionarios WHERE fabrica_id IN ({ph}) AND situacao='ATIVO'", fids).fetchone()[0],
        'equipamentos': c.execute(f"SELECT COUNT(*) FROM equipamentos WHERE fabrica_id IN ({ph}) AND situacao='ATIVO'", fids).fetchone()[0],
        'ops_abertas':  c.execute(f"SELECT COUNT(*) FROM ordens_producao WHERE fabrica_id IN ({ph}) AND situacao='ABERTA'", fids).fetchone()[0],
        'fat_mes':      c.execute(f"SELECT COALESCE(SUM(valor_total),0) FROM faturamento WHERE fabrica_id IN ({ph}) AND data LIKE ?", fids+[f'{mes}%']).fetchone()[0],
    }
    ultimos = c.execute(f"""
        SELECT p.data,p.hora,f.nome fab,op.numero,p.operadores,
               p.qtd_produzida,p.qtd_projetada,p.eficiencia,p.resultado_hora
        FROM producao p JOIN fabricas f ON p.fabrica_id=f.id
        JOIN ordens_producao op ON p.op_id=op.id
        WHERE p.fabrica_id IN ({ph})
        ORDER BY p.criado_em DESC LIMIT 15
    """, fids).fetchall()
    c.close()
    return render_template('dashboard.html', user=user, stats=stats, ultimos=ultimos, hoje=hoje)

# ── FUNCIONARIOS ──────────────────────────────────────────────
@app.route('/funcionarios')
@login_required
def funcionarios():
    user = get_user()
    c = m.conn()
    fids_list = fab_ids(user)
    ph = ','.join('?'*len(fids_list))
    funcs = c.execute(f"""
        SELECT fn.*,f.nome fab_nome,fc.nome funcao_nome
        FROM funcionarios fn
        JOIN fabricas f ON fn.fabrica_id=f.id
        LEFT JOIN funcoes fc ON fn.funcao_id=fc.id
        WHERE fn.fabrica_id IN ({ph})
        ORDER BY fn.nome
    """, fids_list).fetchall()
    fabricas = c.execute(f"SELECT * FROM fabricas WHERE id IN ({ph})", fids_list).fetchall()
    funcoes  = c.execute("SELECT * FROM funcoes WHERE ativa=1 ORDER BY nome").fetchall()
    c.close()
    return render_template('funcionarios.html', user=user, funcs=[dict(r) for r in funcs],
                           fabricas=[dict(r) for r in fabricas], funcoes=[dict(r) for r in funcoes])

@app.route('/api/funcionario/salvar', methods=['POST'])
@login_required
def api_func_salvar():
    d = request.json; c = m.conn()
    user = get_user()
    fab_id = int(d.get('fabrica_id') or user['fabrica_id'] or 1)
    campos = ['fabrica_id','funcao_id','nome','cpf','rg','sexo','data_nascimento',
              'telefone','celular','email','endereco','numero','bairro','cidade',
              'estado','cep','data_admissao','salario','situacao','observacao']
    vals = [fab_id, d.get('funcao_id') or None, d.get('nome','').strip(),
            d.get('cpf',''), d.get('rg',''), d.get('sexo',''),
            d.get('data_nascimento',''), d.get('telefone',''), d.get('celular',''),
            d.get('email',''), d.get('endereco',''), d.get('numero',''),
            d.get('bairro',''), d.get('cidade',''), d.get('estado',''),
            d.get('cep',''), d.get('data_admissao',''),
            float(d.get('salario') or 0), d.get('situacao','ATIVO'), d.get('observacao','')]
    try:
        if d.get('id'):
            sets = ','.join(f"{c2}=?" for c2 in campos)
            c.execute(f"UPDATE funcionarios SET {sets} WHERE id=?", vals+[d['id']])
        else:
            c.execute(f"INSERT INTO funcionarios ({','.join(campos)}) VALUES ({','.join('?'*len(campos))})", vals)
        c.commit(); c.close(); return jsonify({'ok':True})
    except Exception as e:
        c.close(); return jsonify({'ok':False,'erro':str(e)})

@app.route('/api/funcionario/<int:fid>')
@login_required
def api_func_get(fid):
    c = m.conn()
    f = c.execute("SELECT * FROM funcionarios WHERE id=?", (fid,)).fetchone()
    c.close()
    return jsonify(dict(f) if f else {})

@app.route('/api/funcionario/excluir/<int:fid>', methods=['DELETE'])
@login_required
def api_func_excluir(fid):
    c = m.conn()
    c.execute("UPDATE funcionarios SET situacao='INATIVO' WHERE id=?", (fid,))
    c.commit(); c.close(); return jsonify({'ok':True})

@app.route('/api/funcionarios/lista')
@login_required
def api_funcs_lista():
    user = get_user(); fids_list = fab_ids(user)
    ph = ','.join('?'*len(fids_list))
    busca = request.args.get('q','').strip()
    situacao = request.args.get('situacao','ATIVO')
    c = m.conn()
    sql = f"""SELECT fn.*,f.nome fab_nome,fc.nome funcao_nome
              FROM funcionarios fn JOIN fabricas f ON fn.fabrica_id=f.id
              LEFT JOIN funcoes fc ON fn.funcao_id=fc.id
              WHERE fn.fabrica_id IN ({ph})"""
    params = list(fids_list)
    if situacao != 'TODOS': sql += " AND fn.situacao=?"; params.append(situacao)
    if busca: sql += " AND (LOWER(fn.nome) LIKE ? OR fn.cpf LIKE ?)"; params += [f'%{busca.lower()}%',f'%{busca}%']
    rows = [dict(r) for r in c.execute(sql+' ORDER BY fn.nome', params).fetchall()]
    c.close(); return jsonify(rows)

# ── FUNCOES ───────────────────────────────────────────────────
@app.route('/funcoes')
@login_required
def funcoes():
    user = get_user(); c = m.conn()
    fcs = c.execute("SELECT * FROM funcoes ORDER BY nome").fetchall()
    c.close()
    return render_template('funcoes.html', user=user, funcoes=[dict(r) for r in fcs])

@app.route('/api/funcao/salvar', methods=['POST'])
@login_required
def api_funcao_salvar():
    d = request.json; c = m.conn()
    try:
        if d.get('id'):
            c.execute("UPDATE funcoes SET nome=?,descricao=?,salario_base=? WHERE id=?",
                      (d['nome'],d.get('descricao',''),float(d.get('salario_base',0)),d['id']))
        else:
            c.execute("INSERT INTO funcoes (nome,descricao,salario_base) VALUES (?,?,?)",
                      (d['nome'],d.get('descricao',''),float(d.get('salario_base',0))))
        c.commit(); c.close(); return jsonify({'ok':True})
    except Exception as e: return jsonify({'ok':False,'erro':str(e)})

@app.route('/api/funcao/excluir/<int:fid>', methods=['DELETE'])
@login_required
def api_funcao_excluir(fid):
    c = m.conn()
    c.execute("UPDATE funcoes SET ativa=0 WHERE id=?", (fid,))
    c.commit(); c.close(); return jsonify({'ok':True})

# ── EQUIPAMENTOS ──────────────────────────────────────────────
@app.route('/equipamentos')
@login_required
def equipamentos():
    user = get_user(); c = m.conn()
    fids_list = fab_ids(user); ph = ','.join('?'*len(fids_list))
    equips = c.execute(f"""SELECT e.*,f.nome fab_nome FROM equipamentos e
                           JOIN fabricas f ON e.fabrica_id=f.id
                           WHERE e.fabrica_id IN ({ph}) ORDER BY e.nome""", fids_list).fetchall()
    fabricas = c.execute(f"SELECT * FROM fabricas WHERE id IN ({ph})", fids_list).fetchall()
    c.close()
    equips_list = [dict(e) for e in equips]
    fabricas_list = [dict(f) for f in fabricas]
    return render_template('equipamentos.html', user=user, equips=equips_list, fabricas=fabricas_list)

@app.route('/api/equipamento/salvar', methods=['POST'])
@login_required
def api_equip_salvar():
    d = request.json; user = get_user(); c = m.conn()
    fab_id = int(d.get('fabrica_id') or user['fabrica_id'] or 1)
    try:
        if d.get('id'):
            c.execute("UPDATE equipamentos SET fabrica_id=?,nome=?,marca=?,modelo=?,numero_serie=?,"
                      "data_aquisicao=?,valor=?,situacao=?,observacao=? WHERE id=?",
                      (fab_id,d['nome'],d.get('marca',''),d.get('modelo',''),
                       d.get('numero_serie',''),d.get('data_aquisicao',''),
                       float(d.get('valor',0)),d.get('situacao','ATIVO'),d.get('observacao',''),d['id']))
        else:
            c.execute("INSERT INTO equipamentos (fabrica_id,nome,marca,modelo,numero_serie,"
                      "data_aquisicao,valor,situacao,observacao) VALUES (?,?,?,?,?,?,?,?,?)",
                      (fab_id,d['nome'],d.get('marca',''),d.get('modelo',''),
                       d.get('numero_serie',''),d.get('data_aquisicao',''),
                       float(d.get('valor',0)),d.get('situacao','ATIVO'),d.get('observacao','')))
        c.commit(); c.close(); return jsonify({'ok':True})
    except Exception as e: return jsonify({'ok':False,'erro':str(e)})

@app.route('/api/equipamento/excluir/<int:eid>', methods=['DELETE'])
@login_required
def api_equip_excluir(eid):
    c = m.conn()
    c.execute("UPDATE equipamentos SET situacao='INATIVO' WHERE id=?", (eid,))
    c.commit(); c.close(); return jsonify({'ok':True})

# ── PRODUTOS ──────────────────────────────────────────────────
@app.route('/produtos')
@login_required
def produtos():
    user = get_user(); c = m.conn()
    generos = c.execute("SELECT * FROM generos_produto ORDER BY nome").fetchall()
    tipos   = c.execute("SELECT t.*,g.nome gen_nome FROM tipos_produto t LEFT JOIN generos_produto g ON t.genero_id=g.id ORDER BY t.nome").fetchall()
    c.close()
    return render_template('produtos.html', user=user, generos=[dict(r) for r in generos], tipos=[dict(r) for r in tipos])

@app.route('/api/genero/salvar', methods=['POST'])
@login_required
def api_genero_salvar():
    d = request.json; c = m.conn()
    try:
        if d.get('id'): c.execute("UPDATE generos_produto SET nome=? WHERE id=?",(d['nome'],d['id']))
        else: c.execute("INSERT OR IGNORE INTO generos_produto (nome) VALUES (?)",(d['nome'],))
        c.commit(); c.close(); return jsonify({'ok':True})
    except Exception as e: return jsonify({'ok':False,'erro':str(e)})

@app.route('/api/tipo/salvar', methods=['POST'])
@login_required
def api_tipo_salvar():
    d = request.json; c = m.conn()
    try:
        if d.get('id'): c.execute("UPDATE tipos_produto SET nome=?,genero_id=? WHERE id=?",(d['nome'],d.get('genero_id'),d['id']))
        else: c.execute("INSERT OR IGNORE INTO tipos_produto (nome,genero_id) VALUES (?,?)",(d['nome'],d.get('genero_id')))
        c.commit(); c.close(); return jsonify({'ok':True})
    except Exception as e: return jsonify({'ok':False,'erro':str(e)})

# ── APIs AUXILIARES ───────────────────────────────────────────
@app.route('/api/fabricas')
@login_required
def api_fabricas():
    user = get_user(); fids_list = fab_ids(user); ph = ','.join('?'*len(fids_list))
    c = m.conn()
    rows = [dict(r) for r in c.execute(f"SELECT * FROM fabricas WHERE id IN ({ph})", fids_list).fetchall()]
    c.close(); return jsonify(rows)

@app.route('/api/funcoes')
@login_required
def api_funcoes():
    c = m.conn()
    rows = [dict(r) for r in c.execute("SELECT * FROM funcoes WHERE ativa=1 ORDER BY nome").fetchall()]
    c.close(); return jsonify(rows)

# ── TURNOS ────────────────────────────────────────────────────
@app.route('/turnos')
@login_required
def turnos():
    user = get_user()
    fids_list = fab_ids(user)
    ph = ','.join('?'*len(fids_list))
    c = m.conn()
    ts = c.execute("SELECT t.*,f.nome fab_nome FROM turnos t JOIN fabricas f ON t.fabrica_id=f.id WHERE t.fabrica_id IN ({}) AND t.ativo=1 ORDER BY t.numero".format(ph), fids_list).fetchall()
    fabricas = c.execute("SELECT * FROM fabricas WHERE id IN ({})".format(ph), fids_list).fetchall()
    c.close()
    return render_template('turnos.html', user=user,
                           turnos=[dict(r) for r in ts],
                           fabricas=[dict(r) for r in fabricas])


@app.route('/api/turno/salvar', methods=['POST'])
@login_required
def api_turno_salvar():
    user = get_user(); d = request.json; c = m.conn()
    fab_id = int(d.get('fabrica_id') or user['fabrica_id'] or 1)
    # Calcula minutos
    he = d.get('hora_entrada','07:30')
    hsa = d.get('hora_saida_almoco','')
    hea = d.get('hora_entrada_almoco','')
    hs  = d.get('hora_saida','17:30')
    hsf = d.get('hora_saida_sexta','') or hs
    tem_alm = 1 if d.get('tem_almoco') else 0

    def hm(s):
        try: h,mm=s.split(':'); return int(h)*60+int(mm)
        except: return 0

    if tem_alm and hsa and hea:
        mins_normal = (hm(hsa)-hm(he)) + (hm(hs)-hm(hea))
        mins_sexta  = (hm(hsa)-hm(he)) + (hm(hsf)-hm(hea))
    else:
        mins_normal = hm(hs)-hm(he)
        mins_sexta  = hm(hsf)-hm(he)

    try:
        if d.get('id'):
            c.execute("""UPDATE turnos SET fabrica_id=?,nome=?,numero=?,
                         hora_entrada=?,hora_saida_almoco=?,hora_entrada_almoco=?,
                         hora_saida=?,hora_saida_sexta=?,tem_almoco=?,
                         minutos_normal=?,minutos_sexta=?,
                         max_hora_extra_dia=?,obs=? WHERE id=?""",
                      (fab_id, d['nome'], int(d.get('numero',1)),
                       he, hsa or None, hea or None, hs, hsf or None,
                       tem_alm, mins_normal, mins_sexta,
                       float(d.get('max_hora_extra_dia',1)), d.get('obs',''), d['id']))
        else:
            c.execute("""INSERT INTO turnos (fabrica_id,nome,numero,hora_entrada,
                         hora_saida_almoco,hora_entrada_almoco,hora_saida,hora_saida_sexta,
                         tem_almoco,minutos_normal,minutos_sexta,max_hora_extra_dia,obs)
                         VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                      (fab_id, d['nome'], int(d.get('numero',1)),
                       he, hsa or None, hea or None, hs, hsf or None,
                       tem_alm, mins_normal, mins_sexta,
                       float(d.get('max_hora_extra_dia',1)), d.get('obs','')))
        c.commit(); c.close()
        return jsonify({'ok':True,'mins_normal':mins_normal,'mins_sexta':mins_sexta})
    except Exception as e:
        c.close(); return jsonify({'ok':False,'erro':str(e)})

@app.route('/api/turno/excluir/<int:tid>', methods=['DELETE'])
@login_required
def api_turno_excluir(tid):
    c = m.conn()
    c.execute("UPDATE turnos SET ativo=0 WHERE id=?", (tid,))
    c.commit(); c.close(); return jsonify({'ok':True})

@app.route('/api/turno/<int:tid>')
@login_required
def api_turno_get(tid):
    c = m.conn()
    t = c.execute("SELECT * FROM turnos WHERE id=?", (tid,)).fetchone()
    c.close(); return jsonify(dict(t) if t else {})

# ── JORNADA CALENDARIO ────────────────────────────────────────
@app.route('/jornada')
@login_required
def jornada():
    user = get_user()
    fids_list = fab_ids(user)
    ph = ','.join('?'*len(fids_list))
    c = m.conn()
    ts = c.execute(f"""SELECT t.*,f.nome fab_nome FROM turnos t
                       JOIN fabricas f ON t.fabrica_id=f.id
                       WHERE t.fabrica_id IN ({ph}) AND t.ativo=1
                       ORDER BY t.numero""", fids_list).fetchall()
    fabricas = c.execute(f"SELECT * FROM fabricas WHERE id IN ({ph})", fids_list).fetchall()
    # Ultimos 60 dias do calendario
    dias = c.execute(f"""SELECT j.*,t.nome turno_nome,f.nome fab_nome
                         FROM jornada_calendario j
                         JOIN turnos t ON j.turno_id=t.id
                         JOIN fabricas f ON j.fabrica_id=f.id
                         WHERE j.fabrica_id IN ({ph})
                         ORDER BY j.data DESC, t.numero
                         LIMIT 120""", fids_list).fetchall()
    c.close()
    return render_template('jornada.html', user=user,
                           turnos=[dict(r) for r in ts],
                           fabricas=[dict(r) for r in fabricas],
                           dias=[dict(r) for r in dias])

@app.route('/api/jornada/gerar', methods=['POST'])
@login_required
def api_jornada_gerar():
    """Gera dias do calendario para um mes/turno automaticamente"""
    user = get_user(); d = request.json
    fab_id = int(d.get('fabrica_id') or user['fabrica_id'] or 1)
    turno_id = int(d['turno_id'])
    mes = d['mes']  # formato YYYY-MM
    include_sab = d.get('include_sabado', False)
    include_dom = d.get('include_domingo', False)
    c = m.conn()
    turno = c.execute("SELECT * FROM turnos WHERE id=?", (turno_id,)).fetchone()
    if not turno: c.close(); return jsonify({'ok':False,'erro':'Turno não encontrado'})
    from datetime import date, timedelta
    import calendar
    ano, mes_n = map(int, mes.split('-'))
    dias_mes = calendar.monthrange(ano, mes_n)[1]
    DIAS_PT = ['Segunda','Terca','Quarta','Quinta','Sexta','Sabado','Domingo']
    inseridos = 0
    for dia in range(1, dias_mes+1):
        dt = date(ano, mes_n, dia)
        wd = dt.weekday()  # 0=seg, 5=sab, 6=dom
        if wd == 5 and not include_sab: continue
        if wd == 6 and not include_dom: continue
        tipo = 'NORMAL'
        if wd == 5: tipo = 'SABADO'
        if wd == 6: tipo = 'DOMINGO'
        # Sexta usa hora_saida_sexta
        is_sexta = (wd == 4)
        hs = turno['hora_saida_sexta'] if (is_sexta and turno['hora_saida_sexta']) else turno['hora_saida']
        mins = turno['minutos_sexta'] if is_sexta else turno['minutos_normal']
        try:
            c.execute("""INSERT OR IGNORE INTO jornada_calendario
                         (fabrica_id,turno_id,data,dia_semana,tipo,hora_entrada,
                          hora_saida_almoco,hora_entrada_almoco,hora_saida,minutos_disponiveis)
                         VALUES (?,?,?,?,?,?,?,?,?,?)""",
                      (fab_id, turno_id, dt.strftime('%Y-%m-%d'), DIAS_PT[wd],
                       tipo, turno['hora_entrada'], turno['hora_saida_almoco'],
                       turno['hora_entrada_almoco'], hs, mins))
            inseridos += 1
        except: pass
    c.commit(); c.close()
    return jsonify({'ok':True,'inseridos':inseridos})

@app.route('/api/jornada/salvar', methods=['POST'])
@login_required
def api_jornada_salvar():
    user = get_user(); d = request.json
    fab_id = int(d.get('fabrica_id') or user['fabrica_id'] or 1)
    c = m.conn()
    try:
        if d.get('id'):
            c.execute("""UPDATE jornada_calendario SET tipo=?,hora_entrada=?,
                         hora_saida_almoco=?,hora_entrada_almoco=?,hora_saida=?,
                         minutos_disponiveis=?,hora_extra=?,obs=? WHERE id=?""",
                      (d['tipo'], d['hora_entrada'], d.get('hora_saida_almoco'),
                       d.get('hora_entrada_almoco'), d['hora_saida'],
                       int(d.get('minutos_disponiveis',0)),
                       int(d.get('hora_extra',0)), d.get('obs',''), d['id']))
        else:
            from datetime import datetime
            dt = datetime.strptime(d['data'], '%Y-%m-%d')
            DIAS = ['Segunda','Terca','Quarta','Quinta','Sexta','Sabado','Domingo']
            c.execute("""INSERT OR REPLACE INTO jornada_calendario
                         (fabrica_id,turno_id,data,dia_semana,tipo,hora_entrada,
                          hora_saida_almoco,hora_entrada_almoco,hora_saida,
                          minutos_disponiveis,hora_extra,obs)
                         VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                      (fab_id, int(d['turno_id']), d['data'],
                       DIAS[dt.weekday()], d['tipo'], d['hora_entrada'],
                       d.get('hora_saida_almoco'), d.get('hora_entrada_almoco'),
                       d['hora_saida'], int(d.get('minutos_disponiveis',0)),
                       int(d.get('hora_extra',0)), d.get('obs','')))
        c.commit(); c.close(); return jsonify({'ok':True})
    except Exception as e:
        c.close(); return jsonify({'ok':False,'erro':str(e)})

@app.route('/api/jornada/excluir/<int:jid>', methods=['DELETE'])
@login_required
def api_jornada_excluir(jid):
    c = m.conn()
    c.execute("DELETE FROM jornada_calendario WHERE id=?", (jid,))
    c.commit(); c.close(); return jsonify({'ok':True})

@app.route('/api/jornada/lista')
@login_required
def api_jornada_lista():
    user = get_user()
    fids_list = fab_ids(user)
    ph = ','.join('?'*len(fids_list))
    mes = request.args.get('mes','')
    turno_id = request.args.get('turno_id','')
    c = m.conn()
    sql = f"""SELECT j.*,t.nome turno_nome,f.nome fab_nome
              FROM jornada_calendario j
              JOIN turnos t ON j.turno_id=t.id
              JOIN fabricas f ON j.fabrica_id=f.id
              WHERE j.fabrica_id IN ({ph})"""
    params = list(fids_list)
    if mes: sql += " AND j.data LIKE ?"; params.append(f'{mes}%')
    if turno_id: sql += " AND j.turno_id=?"; params.append(turno_id)
    rows = [dict(r) for r in c.execute(sql+' ORDER BY j.data,t.numero', params).fetchall()]
    c.close(); return jsonify(rows)
# ── REF / OP ──────────────────────────────────────────────────
@app.route('/ref-op')
@login_required
def ref_op():
    user = get_user()
    fids_list = fab_ids(user)
    ph = ','.join('?'*len(fids_list))
    c = m.conn()
 
    referencias = c.execute("""
        SELECT r.*,g.nome gen_nome,t.nome tipo_nome,
               (SELECT COUNT(*) FROM ordens_producao op WHERE op.referencia_id=r.id) total_ops,
               (SELECT COUNT(*) FROM sequencia_op sq
                JOIN ordens_producao op ON sq.op_id=op.id
                WHERE op.referencia_id=r.id LIMIT 1) total_operacoes
        FROM referencias r
        LEFT JOIN generos_produto g ON r.genero_id=g.id
        LEFT JOIN tipos_produto t ON r.tipo_produto_id=t.id
        WHERE r.ativo=1 ORDER BY r.codigo
    """).fetchall()
 
    ops = c.execute(f"""
        SELECT op.*,r.codigo ref_codigo,r.descricao ref_desc
        FROM ordens_producao op
        LEFT JOIN referencias r ON op.referencia_id=r.id
        WHERE op.fabrica_id IN ({ph})
        ORDER BY op.id DESC
    """, fids_list).fetchall()
 
    operacoes = c.execute("""
        SELECT o.*,e.nome equip_nome FROM operacoes o
        LEFT JOIN equipamentos e ON o.equipamento_id=e.id
        WHERE o.ativo=1 ORDER BY o.codigo, o.descricao
    """).fetchall()
 
    equipamentos = c.execute(f"""
        SELECT * FROM equipamentos WHERE fabrica_id IN ({ph}) AND situacao='ATIVO' ORDER BY nome
    """, fids_list).fetchall()
 
    generos = c.execute("SELECT * FROM generos_produto ORDER BY nome").fetchall()
    tipos   = c.execute("SELECT * FROM tipos_produto ORDER BY nome").fetchall()
    c.close()
 
    return render_template('ref_op.html', user=user,
        referencias=[dict(r) for r in referencias],
        ops=[dict(r) for r in ops],
        operacoes=[dict(r) for r in operacoes],
        equipamentos=[dict(r) for r in equipamentos],
        generos=[dict(r) for r in generos],
        tipos=[dict(r) for r in tipos])
 
 
# ── APIs REFERÊNCIA ───────────────────────────────────────────
@app.route('/api/referencia/salvar', methods=['POST'])
@login_required
def api_ref_salvar():
    d = request.json; c = m.conn()
    try:
        if d.get('id'):
            c.execute("UPDATE referencias SET codigo=?,descricao=?,genero_id=?,tipo_produto_id=? WHERE id=?",
                      (d['codigo'], d.get('descricao',''), d.get('genero_id'), d.get('tipo_produto_id'), d['id']))
        else:
            c.execute("INSERT INTO referencias (codigo,descricao,genero_id,tipo_produto_id) VALUES (?,?,?,?)",
                      (d['codigo'], d.get('descricao',''), d.get('genero_id'), d.get('tipo_produto_id')))
        c.commit(); c.close(); return jsonify({'ok': True})
    except Exception as e:
        c.close(); return jsonify({'ok': False, 'erro': str(e)})
 
@app.route('/api/referencia/<int:rid>')
@login_required
def api_ref_get(rid):
    c = m.conn()
    r = c.execute("SELECT * FROM referencias WHERE id=?", (rid,)).fetchone()
    c.close(); return jsonify(dict(r) if r else {})
 
@app.route('/api/referencia/sequencia/<int:rid>')
@login_required
def api_ref_sequencia_get(rid):
    c = m.conn()
    # Pega sequência de uma OP da referência (a mais recente com sequência)
    rows = c.execute("""
        SELECT rs.*, o.descricao, e.nome equip_nome, fn.nome func_nome
        FROM ref_sequencia rs
        JOIN operacoes o ON rs.operacao_id=o.id
        LEFT JOIN equipamentos e ON rs.equipamento_id=e.id
        LEFT JOIN funcionarios fn ON rs.funcionario_id=fn.id
        WHERE rs.referencia_id=?
        ORDER BY rs.ordem
    """, (rid,)).fetchall()
    c.close()
    return jsonify([{
        'operacao_id': r['operacao_id'],
        'descricao': r['descricao'],
        'tempo_padrao': r['tempo_padrao'],
        'equipamento_id': r['equipamento_id'],
        'equipamento_nome': r['equip_nome'] or '',
        'funcionario_id': r['funcionario_id'],
        'funcionario_nome': r['func_nome'] or '',
        'ordem': r['ordem'],
    } for r in rows])
 
@app.route('/api/referencia/sequencia/salvar', methods=['POST'])
@login_required
def api_ref_sequencia_salvar():
    
   d = request.json; c = m.conn()
   ref_id = int(d['referencia_id'])    
   try:
        c.execute("DELETE FROM ref_sequencia WHERE referencia_id=?", (ref_id,))
        for i, op in enumerate(d.get('operacoes', [])):
            c.execute("""INSERT INTO ref_sequencia
                         (referencia_id,operacao_id,ordem,equipamento_id,funcionario_id,tempo_padrao)
                         VALUES (?,?,?,?,?,?)""",
                      (ref_id, op['operacao_id'], i+1,
                       op.get('equipamento_id'), op.get('funcionario_id'),
                       float(op.get('tempo_padrao') or 0)))
        c.commit(); c.close()
        return jsonify({'ok': True})
   except Exception as e:
        c.close(); return jsonify({'ok': False, 'erro': str(e)})
 
 
# ── APIs OP ────────────────────────────────────────────────────
@app.route('/api/op/salvar', methods=['POST'])
@login_required
def api_op_salvar():
    user = get_user(); d = request.json; c = m.conn()
    fab_id = user['fabrica_id'] or 1
    try:
        ref_id = d.get('referencia_id')
        qtd = int(d.get('quantidade_total') or 0)
        unit = float(d.get('valor_unitario') or 0)
        total = qtd * unit
 
        if d.get('id'):
            c.execute("""UPDATE ordens_producao SET numero=?,fabrica_id=?,referencia_id=?,
                         descricao=?,quantidade_total=?,valor_unitario=?,valor_total=?,
                         data_entrada=?,data_entrega=?,obs=? WHERE id=?""",
                      (d['numero'], fab_id, ref_id, d.get('descricao',''),
                       qtd, unit, total, d.get('data_entrada'), d.get('data_entrega'),
                       d.get('obs',''), d['id']))
            op_id = d['id']
        else:
            c.execute("""INSERT INTO ordens_producao (numero,fabrica_id,referencia_id,descricao,
                         quantidade_total,valor_unitario,valor_total,data_entrada,data_entrega,obs)
                         VALUES (?,?,?,?,?,?,?,?,?,?)""",
                      (d['numero'], fab_id, ref_id, d.get('descricao',''),
                       qtd, unit, total, d.get('data_entrada'), d.get('data_entrega'), d.get('obs','')))
            op_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
 
            # Copiar sequência da referência se solicitado
            if d.get('copiar_sequencia') and ref_id:
                # Busca a sequência de outra OP da mesma referência
                seq_ref = c.execute("""
                    SELECT * FROM ref_sequencia
                    WHERE referencia_id=?
                    ORDER BY ordem
                """, (ref_id,)).fetchall()
                for s in seq_ref:
                    c.execute("""INSERT INTO sequencia_op
                                 (op_id,operacao_id,ordem,equipamento_id,funcionario_id,tempo_padrao)
                                 VALUES (?,?,?,?,?,?)""",
                              (op_id, s['operacao_id'], s['ordem'],
                               s['equipamento_id'], s['funcionario_id'], s['tempo_padrao']))
 
        c.commit(); c.close(); return jsonify({'ok': True, 'op_id': op_id})
    except Exception as e:
        c.close(); return jsonify({'ok': False, 'erro': str(e)})
 
@app.route('/api/op/<int:oid>')
@login_required
def api_op_get(oid):
    c = m.conn()
    r = c.execute("SELECT * FROM ordens_producao WHERE id=?", (oid,)).fetchone()
    c.close(); return jsonify(dict(r) if r else {})
 
@app.route('/api/op/situacao', methods=['POST'])
@login_required
def api_op_situacao():
    d = request.json; c = m.conn()
    c.execute("UPDATE ordens_producao SET situacao=? WHERE id=?", (d['situacao'], d['id']))
    c.commit(); c.close(); return jsonify({'ok': True})
 
@app.route('/api/op/sequencia/<int:oid>')
@login_required
def api_op_sequencia_get(oid):
    c = m.conn()
    rows = c.execute("""
        SELECT sq.*, o.descricao, o.tempo_padrao as tp, o.equipamento_id as eq_id
        FROM sequencia_op sq
        JOIN operacoes o ON sq.operacao_id=o.id
        WHERE sq.op_id=? ORDER BY sq.ordem
    """, (oid,)).fetchall()
    c.close()
    return jsonify([{
        'id': r['id'],
        'operacao_id': r['operacao_id'],
        'descricao': r['descricao'],
        'tempo_padrao': r['tempo_padrao'],
        'equipamento_id': r['equipamento_id'],
        'ordem': r['ordem'],
    } for r in rows])
 
@app.route('/api/op/sequencia/salvar', methods=['POST'])
@login_required
def api_op_sequencia_salvar():
    d = request.json; c = m.conn()
    op_id = int(d['op_id'])
    try:
        c.execute("DELETE FROM sequencia_op WHERE op_id=?", (op_id,))
        for i, op in enumerate(d.get('operacoes', [])):
            c.execute("""INSERT INTO sequencia_op
                         (op_id,operacao_id,ordem,equipamento_id,tempo_padrao)
                         VALUES (?,?,?,?,?)""",
                      (op_id, op['operacao_id'], i+1,
                       op.get('equipamento_id'), op['tempo_padrao']))
        c.commit(); c.close(); return jsonify({'ok': True})
    except Exception as e:
        c.close(); return jsonify({'ok': False, 'erro': str(e)})
 
 
# ── APIs OPERAÇÕES BANCO ───────────────────────────────────────
@app.route('/api/operacao/salvar', methods=['POST'])
@login_required
def api_operacao_salvar():
    d = request.json; c = m.conn()
    try:
        if d.get('id'):
            c.execute("UPDATE operacoes SET codigo=?,descricao=?,equipamento_id=?,tempo_padrao=?,tipo=? WHERE id=?",
                      (d.get('codigo'), d['descricao'], d.get('equipamento_id'),
                       float(d.get('tempo_padrao') or 0), d.get('tipo','C'), d['id']))
        else:
            c.execute("INSERT INTO operacoes (codigo,descricao,equipamento_id,tempo_padrao,tipo) VALUES (?,?,?,?,?)",
                      (d.get('codigo'), d['descricao'], d.get('equipamento_id'),
                       float(d.get('tempo_padrao') or 0), d.get('tipo','C')))
        c.commit(); c.close(); return jsonify({'ok': True})
    except Exception as e:
        c.close(); return jsonify({'ok': False, 'erro': str(e)})
 
@app.route('/api/operacao/<int:oid>')
@login_required
def api_operacao_get(oid):
    c = m.conn()
    r = c.execute("SELECT * FROM operacoes WHERE id=?", (oid,)).fetchone()
    c.close(); return jsonify(dict(r) if r else {})
 
@app.route('/api/operacao/excluir/<int:oid>', methods=['DELETE'])
@login_required
def api_operacao_excluir(oid):
    c = m.conn()
    c.execute("UPDATE operacoes SET ativo=0 WHERE id=?", (oid,))
    c.commit(); c.close(); return jsonify({'ok': True})
@app.route('/balanceamento')
@login_required
def balanceamento():
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
 
    funcionarios = c.execute(f"""
        SELECT * FROM funcionarios WHERE fabrica_id IN ({ph}) AND situacao='ATIVO' ORDER BY nome
    """, fids_list).fetchall()
 
    c.close()
    return render_template('balanceamento.html', user=user,
        ops=[dict(r) for r in ops],
        turnos=[dict(r) for r in turnos],
        funcionarios=[dict(r) for r in funcionarios])
 
 
@app.route('/api/balanceamento/salvar', methods=['POST'])
@login_required
def api_balanceamento_salvar():
    user = get_user(); d = request.json; c = m.conn()
    fab_id = user['fabrica_id'] or 1
    try:
        # Salva ou atualiza o balanceamento
        bal = c.execute("SELECT id FROM balanceamento WHERE op_id=?", (d['op_id'],)).fetchone()
        if bal:
            c.execute("""UPDATE balanceamento SET ciclo_minutos=?,total_operadores=?,
                         minutos_disponiveis=?,meta_dia=?,meta_ciclo=?,total_times=?
                         WHERE op_id=?""",
                      (d['ciclo_minutos'], d['total_operadores'], d['minutos_disponiveis'],
                       d['meta_dia'], d['meta_ciclo'], d['total_times'], d['op_id']))
            bal_id = bal['id']
        else:
            bal_id = c.insert_id("""INSERT INTO balanceamento (op_id,fabrica_id,ciclo_minutos,total_operadores,
                         minutos_disponiveis,meta_dia,meta_ciclo,total_times)
                         VALUES (?,?,?,?,?,?,?,?)""",
                      (d['op_id'], fab_id, d['ciclo_minutos'], d['total_operadores'],
                       d['minutos_disponiveis'], d['meta_dia'], d['meta_ciclo'], d['total_times']))
 
        # Atualiza time_numero na sequencia_op
        for time in d.get('times', []):
            for op in time.get('ops', []):
                if op.get('operacao_id'):
                    c.execute("""UPDATE sequencia_op SET time_numero=?
                                 WHERE op_id=? AND operacao_id=?""",
                              (time['num'], d['op_id'], op['operacao_id']))
 
        c.commit(); c.close()
        return jsonify({'ok': True, 'bal_id': bal_id})
    except Exception as e:
        c.close(); return jsonify({'ok': False, 'erro': str(e)})
 
 
@app.route('/api/balanceamento/<int:op_id>')
@login_required
def api_balanceamento_get(op_id):
    c = m.conn()
    bal = c.execute("SELECT * FROM balanceamento WHERE op_id=?", (op_id,)).fetchone()
    c.close()
    return jsonify(dict(bal) if bal else {})
# ── SEQUÊNCIA OP ───────────────────────────────────────────────
@app.route('/sequencia-op')
@login_required
def sequencia_op():
    user = get_user()
    fids_list = fab_ids(user)
    ph = ','.join('?'*len(fids_list))
    c = m.conn()
    equipamentos = c.execute(f"""
        SELECT * FROM equipamentos WHERE fabrica_id IN ({ph}) AND situacao='ATIVO' ORDER BY nome
    """, fids_list).fetchall()
    c.close()
    return render_template('sequencia_op.html', user=user,
        equipamentos=[dict(r) for r in equipamentos])


@app.route('/api/operacoes/banco')
@login_required
def api_operacoes_banco():
    c = m.conn()
    TIPOS = {'C':'Costura','A':'Acabamento','P':'Preparação','Q':'Qualidade','O':'Outro'}
    rows = c.execute("""
        SELECT o.*, e.nome equip_nome
        FROM operacoes o
        LEFT JOIN equipamentos e ON o.equipamento_id=e.id
        WHERE o.ativo=1
        ORDER BY o.modelo, o.descricao
    """).fetchall()
    c.close()
    result = []
    for r in rows:
        d = dict(r)
        d['tipo_label'] = TIPOS.get(d.get('tipo','C'), '')
        d['modelo'] = d.get('modelo') or 'UNIVERSAL'
        result.append(d)
    return jsonify(result)


@app.route('/api/sequencia/salvar', methods=['POST'])
@login_required
def api_sequencia_salvar():
    user = get_user(); d = request.json; c = m.conn()
    try:
        # Calcula tempo total
        tempo_total = sum(float(op.get('tempo_padrao',0)) for op in d.get('operacoes',[]))
        total_ops = len(d.get('operacoes',[]))

        if d.get('id'):
            c.execute("""UPDATE sequencias_banco SET nome=?,modelo=?,tempo_total=?,total_ops=?
                         WHERE id=?""",
                      (d['nome'], d['modelo'], tempo_total, total_ops, d['id']))
            seq_id = d['id']
            c.execute("DELETE FROM sequencia_banco_ops WHERE sequencia_id=?", (seq_id,))
        else:
            c.execute("""INSERT INTO sequencias_banco (nome,modelo,tempo_total,total_ops,criado_por)
                         VALUES (?,?,?,?,?)""",
                      (d['nome'], d['modelo'], tempo_total, total_ops, user['id']))
            seq_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]

        for op in d.get('operacoes', []):
            c.execute("""INSERT INTO sequencia_banco_ops
                         (sequencia_id,operacao_id,ordem,tempo_padrao,equipamento_id)
                         VALUES (?,?,?,?,?)""",
                      (seq_id, op['operacao_id'], op['ordem'],
                       float(op.get('tempo_padrao',0)), op.get('equipamento_id')))

        c.commit(); c.close()
        return jsonify({'ok': True, 'seq_id': seq_id})
    except Exception as e:
        c.close(); return jsonify({'ok': False, 'erro': str(e)})


@app.route('/api/sequencias')
@login_required
def api_sequencias_lista():
    modelo = request.args.get('modelo','')
    c = m.conn()
    sql = "SELECT * FROM sequencias_banco WHERE 1=1"
    params = []
    if modelo and modelo != 'TODOS':
        sql += " AND modelo=?"
        params.append(modelo)
    sql += " ORDER BY nome"
    rows = [dict(r) for r in c.execute(sql, params).fetchall()]
    c.close()
    return jsonify(rows)


@app.route('/api/sequencia/<int:sid>')
@login_required
def api_sequencia_get(sid):
    c = m.conn()
    ops = c.execute("""
        SELECT sbo.*, o.descricao, o.modelo, o.tipo, e.nome equip_nome
        FROM sequencia_banco_ops sbo
        JOIN operacoes o ON sbo.operacao_id=o.id
        LEFT JOIN equipamentos e ON sbo.equipamento_id=e.id
        WHERE sbo.sequencia_id=?
        ORDER BY sbo.ordem
    """, (sid,)).fetchall()
    c.close()
    return jsonify([dict(r) for r in ops])


@app.route('/api/sequencia/excluir/<int:sid>', methods=['DELETE'])
@login_required
def api_sequencia_excluir(sid):
    c = m.conn()
    c.execute("DELETE FROM sequencia_banco_ops WHERE sequencia_id=?", (sid,))
    c.execute("DELETE FROM sequencias_banco WHERE id=?", (sid,))
    c.commit(); c.close()
    return jsonify({'ok': True})
@app.route('/api/lancamento/salvar', methods=['POST'])
@login_required
def api_lancamento_salvar():
    user = get_user(); d = request.json; c = m.conn()
    fab_id = user['fabrica_id'] or 1
    try:
        if d.get('id'):
            c.execute("""UPDATE producao SET hora=?,operadores=?,qtd_produzida=?,
                         qtd_projetada=?,eficiencia=?,faturamento_hora=?,
                         resultado_hora=?,obs=? WHERE id=?""",
                      (d['hora'], d['operadores'], d['qtd_produzida'],
                       d['qtd_projetada'], d['eficiencia'], d['faturamento_hora'],
                       d['resultado_hora'], d.get('obs',''), d['id']))
        else:
            c.execute("""INSERT INTO producao (fabrica_id,op_id,data,hora,ciclo_minutos,
                         operadores,qtd_produzida,qtd_projetada,eficiencia,
                         faturamento_hora,custo_hora,resultado_hora,obs)
                         VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                      (fab_id, d['op_id'], d['data'], d['hora'],
                       d.get('ciclo_minutos',60), d['operadores'],
                       d['qtd_produzida'], d['qtd_projetada'], d['eficiencia'],
                       d['faturamento_hora'], d.get('custo_hora',0),
                       d['resultado_hora'], d.get('obs','')))
        c.commit(); c.close()
        return jsonify({'ok': True})
    except Exception as e:
        c.close(); return jsonify({'ok': False, 'erro': str(e)})
 
 
@app.route('/api/lancamento/excluir/<int:lid>', methods=['DELETE'])
@login_required
def api_lancamento_excluir(lid):
    c = m.conn()
    c.execute("DELETE FROM producao WHERE id=?", (lid,))
    c.commit(); c.close()
    return jsonify({'ok': True})
@app.route('/lancamento')
@login_required
def lancamento():
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
    from datetime import date
    hoje = date.today().strftime('%Y-%m-%d')
    return render_template('lancamento.html', user=user,
        ops=[dict(r) for r in ops],
        turnos=[dict(r) for r in turnos],
        hoje=hoje)


@app.route('/api/lancamentos')
@login_required
def api_lancamentos_lista():
    op_id = request.args.get('op_id')
    data = request.args.get('data')
    c = m.conn()
    sql = "SELECT * FROM producao WHERE 1=1"
    params = []
    if op_id: sql += " AND op_id=?"; params.append(op_id)
    if data: sql += " AND data=?"; params.append(data)
    sql += " ORDER BY hora"
    rows = [dict(r) for r in c.execute(sql, params).fetchall()]
    c.close()
    return jsonify(rows)
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
    fab_id = int(d.get('fabrica_id') or user['fabrica_id'] or 1)
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
    fab_id = int(d.get('fabrica_id') or user['fabrica_id'] or 1)
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
    fab_id = int(d.get('fabrica_id') or user['fabrica_id'] or 1)
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
    fab_id = int(d.get('fabrica_id') or user['fabrica_id'] or 1)
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
# ── DRE ────────────────────────────────────────────────────────
@app.route('/dre')
@login_required
def dre():
    user = get_user()
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
    return render_template('dre.html', user=user, meses=meses)
 
 
@app.route('/api/dre')
@login_required
def api_dre():
    user = get_user()
    fids_list = fab_ids(user)
    ph = ','.join('?'*len(fids_list))
    mes = request.args.get('mes', '')
    c = m.conn()
 
    # Categorias folha (salários, FGTS, etc)
    FOLHA_CATS = ['FOLHA LIQUIDA','FGTS + FGTS RESCISAO','GPS / IMPOSTO DE RENDA',
                  'IRRF','PREVISAO FOLHA 13','PREVISAO FERIAS','PREVISAO 1/3',
                  'INDENIZACOES','SINDICATO','PAGAMENTO RESCISAO','RECRUTA']
 
    def get_dre_fab(fab_id=None):
        params_f = [fab_id] if fab_id else list(fids_list)
        ph_f = '?' if fab_id else ph
        cond_f = f"fabrica_id={ph_f}" if fab_id else f"fabrica_id IN ({ph_f})"
 
        # Receita
        receita = c.execute(f"""
            SELECT COALESCE(SUM(valor_total),0) FROM faturamento
            WHERE {cond_f} AND data LIKE ?
        """, params_f + [f'{mes}%']).fetchone()[0] or 0
 
        # Despesas com categoria
        desp = c.execute(f"""
            SELECT cat.nome, d.tipo, COALESCE(SUM(d.valor),0) as total
            FROM despesas d
            JOIN categorias_despesa cat ON d.categoria_id=cat.id
            WHERE {cond_f} AND d.mes LIKE ?
            GROUP BY d.categoria_id, d.tipo
            ORDER BY cat.nome
        """, params_f + [f'{mes}%']).fetchall()
 
        fixo, variavel, folha = 0, 0, 0
        itens_fixo, itens_variavel, itens_folha = [], [], []
 
        for d_row in desp:
            nome, tipo, valor = d_row
            if nome.upper() in FOLHA_CATS:
                folha += valor
                itens_folha.append({'nome': nome, 'valor': valor})
            elif tipo == 'VARIAVEL':
                variavel += valor
                itens_variavel.append({'nome': nome, 'valor': valor})
            else:
                fixo += valor
                itens_fixo.append({'nome': nome, 'valor': valor})
 
        return {
            'receita': receita,
            'custo_fixo': fixo,
            'custo_variavel': variavel,
            'folha': folha,
            'itens_fixo': itens_fixo,
            'itens_variavel': itens_variavel,
            'itens_folha': itens_folha,
        }
 
    # Consolidado
    consolidado = get_dre_fab()
 
    # Por fábrica
    fabricas = c.execute(f"SELECT id,nome FROM fabricas WHERE id IN ({ph})", fids_list).fetchall()
    fab_list = []
    for fab in fabricas:
        d = get_dre_fab(fab['id'])
        d['nome'] = fab['nome']
        fab_list.append(d)
 
    c.close()
    return jsonify({'consolidado': consolidado, 'fabricas': fab_list})
 
 
@app.route('/api/dre/evolucao')
@login_required
def api_dre_evolucao():
    user = get_user()
    fids_list = fab_ids(user)
    ph = ','.join('?'*len(fids_list))
    from datetime import date, datetime
    c = m.conn()
 
    FOLHA_CATS = ['FOLHA LIQUIDA','FGTS + FGTS RESCISAO','GPS / IMPOSTO DE RENDA',
                  'IRRF','PREVISAO FOLHA 13','PREVISAO FERIAS','PREVISAO 1/3',
                  'INDENIZACOES','SINDICATO','PAGAMENTO RESCISAO','RECRUTA']
 
    resultado = []
    for i in range(11, -1, -1):
        d = date.today().replace(day=1)
        mes = (d.month - i - 1) % 12 + 1
        ano = d.year - ((d.month - i - 1) // 12)
        mes_str = f'{ano}-{str(mes).zfill(2)}'
        mes_label = datetime(ano, mes, 1).strftime('%b/%Y').upper()
 
        receita = c.execute(f"""
            SELECT COALESCE(SUM(valor_total),0) FROM faturamento
            WHERE fabrica_id IN ({ph}) AND data LIKE ?
        """, fids_list + [f'{mes_str}%']).fetchone()[0] or 0
 
        despesas_total = c.execute(f"""
            SELECT COALESCE(SUM(d.valor),0) FROM despesas d
            WHERE d.fabrica_id IN ({ph}) AND d.mes LIKE ?
        """, fids_list + [f'{mes_str}%']).fetchone()[0] or 0
 
        resultado.append({
            'mes': mes_label,
            'receita': receita,
            'despesas': despesas_total,
            'resultado': receita - despesas_total,
        })
 
    c.close()
    return jsonify(resultado)
# ── OCORRÊNCIAS ────────────────────────────────────────────────
@app.route('/ocorrencias')
@login_required
def ocorrencias():
    user = get_user()
    fids_list = fab_ids(user)
    ph = ','.join('?'*len(fids_list))
    c = m.conn()
    fabricas = c.execute(f"SELECT * FROM fabricas WHERE id IN ({ph})", fids_list).fetchall()
    funcionarios = c.execute(f"""
        SELECT fn.*,f.nome fab_nome FROM funcionarios fn
        JOIN fabricas f ON fn.fabrica_id=f.id
        WHERE fn.fabrica_id IN ({ph}) AND fn.situacao='ATIVO'
        ORDER BY fn.nome
    """, fids_list).fetchall()
    tipos = c.execute("SELECT * FROM tipos_ocorrencia ORDER BY nome").fetchall()
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
    return render_template('ocorrencias.html', user=user,
        fabricas=[dict(r) for r in fabricas],
        funcionarios=[dict(r) for r in funcionarios],
        tipos=[dict(r) for r in tipos],
        meses=meses, hoje=hoje)


@app.route('/api/ocorrencias')
@login_required
def api_ocorrencias_lista():
    user = get_user(); fids_list = fab_ids(user)
    ph = ','.join('?'*len(fids_list))
    mes = request.args.get('mes','')
    fab_id = request.args.get('fabrica_id','')
    tipo_id = request.args.get('tipo_id','')
    c = m.conn()
    sql = f"""
        SELECT oc.*,fn.nome func_nome,f.nome fab_nome,t.nome tipo_nome
        FROM ocorrencias oc
        LEFT JOIN funcionarios fn ON oc.funcionario_id=fn.id
        LEFT JOIN fabricas f ON oc.fabrica_id=f.id
        LEFT JOIN tipos_ocorrencia t ON oc.tipo_id=t.id
        WHERE oc.fabrica_id IN ({ph})
    """
    params = list(fids_list)
    if mes: sql += " AND oc.data LIKE ?"; params.append(f'{mes}%')
    if fab_id: sql += " AND oc.fabrica_id=?"; params.append(fab_id)
    if tipo_id: sql += " AND oc.tipo_id=?"; params.append(tipo_id)
    sql += " ORDER BY oc.data DESC,fn.nome"
    rows = [dict(r) for r in c.execute(sql, params).fetchall()]
    c.close(); return jsonify(rows)


@app.route('/api/ocorrencias/fabricas')
@login_required
def api_ocorrencias_fabricas():
    user = get_user(); fids_list = fab_ids(user)
    ph = ','.join('?'*len(fids_list))
    mes = request.args.get('mes','')
    c = m.conn()
    fabricas = c.execute(f"SELECT id,nome FROM fabricas WHERE id IN ({ph})", fids_list).fetchall()
    result = []
    for fab in fabricas:
        params = [fab['id']]
        sql_base = "WHERE oc.fabrica_id=?"
        if mes: sql_base += " AND oc.data LIKE ?"; params.append(f'{mes}%')
        total_oc = c.execute(f"SELECT COUNT(*) FROM ocorrencias oc {sql_base}", params).fetchone()[0]
        horas = c.execute(f"SELECT COALESCE(SUM(oc.horas),0) FROM ocorrencias oc {sql_base}", params).fetchone()[0]
        ferias = c.execute(f"""
            SELECT COUNT(*) FROM ocorrencias oc
            JOIN tipos_ocorrencia t ON oc.tipo_id=t.id
            {sql_base} AND UPPER(t.nome) LIKE '%FERIA%'
        """, params).fetchone()[0]
        total_func = c.execute("SELECT COUNT(*) FROM funcionarios WHERE fabrica_id=? AND situacao='ATIVO'", (fab['id'],)).fetchone()[0]
        horas_disp = total_func * 9 * 22
        abs_pct = (horas / horas_disp * 100) if horas_disp > 0 else 0
        result.append({'nome': fab['nome'], 'total_func': total_func, 'total_oc': total_oc,
                       'horas': horas, 'ferias': ferias, 'abs_pct': abs_pct})
    c.close(); return jsonify(result)


@app.route('/api/ocorrencias/evolucao')
@login_required
def api_ocorrencias_evolucao():
    user = get_user(); fids_list = fab_ids(user)
    ph = ','.join('?'*len(fids_list))
    from datetime import date, datetime
    c = m.conn()
    result = []
    for i in range(5, -1, -1):
        d = date.today().replace(day=1)
        mes = (d.month - i - 1) % 12 + 1
        ano = d.year - ((d.month - i - 1) // 12)
        mes_str = f'{ano}-{str(mes).zfill(2)}'
        mes_label = datetime(ano, mes, 1).strftime('%b/%Y').upper()
        params = fids_list + [f'{mes_str}%']
        total_h = c.execute(f"SELECT COALESCE(SUM(horas),0) FROM ocorrencias WHERE fabrica_id IN ({ph}) AND data LIKE ?", params).fetchone()[0]
        h_falta = c.execute(f"""SELECT COALESCE(SUM(oc.horas),0) FROM ocorrencias oc
            JOIN tipos_ocorrencia t ON oc.tipo_id=t.id
            WHERE oc.fabrica_id IN ({ph}) AND oc.data LIKE ? AND UPPER(t.nome) LIKE '%FALTA%'""", params).fetchone()[0]
        h_atestado = c.execute(f"""SELECT COALESCE(SUM(oc.horas),0) FROM ocorrencias oc
            JOIN tipos_ocorrencia t ON oc.tipo_id=t.id
            WHERE oc.fabrica_id IN ({ph}) AND oc.data LIKE ? AND UPPER(t.nome) LIKE '%ATESTADO%'""", params).fetchone()[0]
        total_func = c.execute(f"SELECT COUNT(*) FROM funcionarios WHERE fabrica_id IN ({ph}) AND situacao='ATIVO'", fids_list).fetchone()[0]
        horas_disp = total_func * 9 * 22
        abs_pct = (total_h / horas_disp * 100) if horas_disp > 0 else 0
        result.append({'mes': mes_label, 'abs_pct': round(abs_pct, 2),
                       'h_falta': h_falta, 'h_atestado': h_atestado,
                       'h_outros': max(0, total_h - h_falta - h_atestado)})
    c.close(); return jsonify(result)


@app.route('/api/ocorrencia/salvar', methods=['POST'])
@login_required
def api_ocorrencia_salvar():
    user = get_user(); d = request.json; c = m.conn()
    fab_id = int(d.get('fabrica_id') or user['fabrica_id'] or 1)
    try:
        if d.get('id'):
            c.execute("""UPDATE ocorrencias SET funcionario_id=?,fabrica_id=?,data=?,
                         tipo_id=?,horas=?,direto=?,obs=? WHERE id=?""",
                      (d['funcionario_id'],fab_id,d['data'],d['tipo_id'],
                       d.get('horas',0),d.get('direto','DIRETO'),d.get('obs',''),d['id']))
        else:
            c.execute("""INSERT INTO ocorrencias (funcionario_id,fabrica_id,data,tipo_id,horas,direto,obs)
                         VALUES (?,?,?,?,?,?,?)""",
                      (d['funcionario_id'],fab_id,d['data'],d['tipo_id'],
                       d.get('horas',0),d.get('direto','DIRETO'),d.get('obs','')))
        c.commit(); c.close(); return jsonify({'ok': True})
    except Exception as e:
        c.close(); return jsonify({'ok': False, 'erro': str(e)})


@app.route('/api/ocorrencia/<int:oid>')
@login_required
def api_ocorrencia_get(oid):
    c = m.conn()
    r = c.execute("SELECT * FROM ocorrencias WHERE id=?", (oid,)).fetchone()
    c.close(); return jsonify(dict(r) if r else {})


@app.route('/api/ocorrencia/excluir/<int:oid>', methods=['DELETE'])
@login_required
def api_ocorrencia_excluir(oid):
    c = m.conn()
    c.execute("DELETE FROM ocorrencias WHERE id=?", (oid,))
    c.commit(); c.close(); return jsonify({'ok': True})
# ── USUÁRIOS ───────────────────────────────────────────────────
def admin_required(f):
    from functools import wraps
    @wraps(f)
    def dec(*a, **kw):
        if session.get('perfil') != 'admin':
            flash('Acesso restrito ao administrador.', 'error')
            return redirect(url_for('dashboard'))
        return f(*a, **kw)
    return dec

@app.route('/usuarios')
@login_required
@admin_required
def usuarios():
    c = m.conn()
    users = c.execute("""
        SELECT u.*, f.nome fab_nome
        FROM usuarios u
        LEFT JOIN fabricas f ON u.fabrica_id = f.id
        ORDER BY u.perfil, u.nome
    """).fetchall()
    fabricas = c.execute("SELECT * FROM fabricas WHERE ativa=1 ORDER BY nome").fetchall()
    c.close()
    return render_template('usuarios.html',
        users=[dict(r) for r in users],
        fabricas=[dict(r) for r in fabricas])

@app.route('/api/usuarios/salvar', methods=['POST'])
@login_required
@admin_required
def api_usuarios_salvar():
    d = request.json; c = m.conn()
    try:
        fab_id = int(d['fabrica_id']) if d.get('fabrica_id') else None
        if d.get('id'):
            sql = "UPDATE usuarios SET nome=?,login=?,perfil=?,fabrica_id=?,ativo=?"
            params = [d['nome'], d['login'], d['perfil'], fab_id, int(d.get('ativo', 1))]
            if d.get('senha'):
                sql += ",senha_hash=?"
                params.append(m.hash_senha(d['senha']))
            sql += " WHERE id=?"
            params.append(d['id'])
            c.execute(sql, params)
        else:
            if not d.get('senha'):
                return jsonify({'ok': False, 'erro': 'Senha obrigatória para novo usuário'})
            c.execute("""INSERT INTO usuarios (nome,login,senha_hash,perfil,fabrica_id,ativo)
                         VALUES (?,?,?,?,?,1)""",
                      (d['nome'], d['login'], m.hash_senha(d['senha']), d['perfil'], fab_id))
        c.commit(); c.close()
        return jsonify({'ok': True})
    except Exception as e:
        c.close()
        if 'UNIQUE' in str(e):
            return jsonify({'ok': False, 'erro': 'Login já existe'})
        return jsonify({'ok': False, 'erro': str(e)})

@app.route('/api/usuarios/toggle/<int:uid>', methods=['POST'])
@login_required
@admin_required
def api_usuarios_toggle(uid):
    if uid == session.get('uid'):
        return jsonify({'ok': False, 'erro': 'Não é possível desativar seu próprio usuário'})
    c = m.conn()
    c.execute("UPDATE usuarios SET ativo = CASE WHEN ativo=1 THEN 0 ELSE 1 END WHERE id=?", (uid,))
    c.commit()
    novo = c.execute("SELECT ativo FROM usuarios WHERE id=?", (uid,)).fetchone()['ativo']
    c.close()
    return jsonify({'ok': True, 'ativo': novo})

@app.route('/api/usuarios/reset-senha', methods=['POST'])
@login_required
@admin_required
def api_usuarios_reset_senha():
    d = request.json; c = m.conn()
    c.execute("UPDATE usuarios SET senha_hash=? WHERE id=?",
              (m.hash_senha(d['senha']), d['uid']))
    c.commit(); c.close()
    return jsonify({'ok': True})

if __name__ == '__main__':
    app.run(debug=False, use_reloader=False, host='0.0.0.0', port=5050)
