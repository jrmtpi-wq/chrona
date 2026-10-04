"""Cada instalação atende uma empresa em seu próprio banco."""
from flask import g, jsonify, request, session, redirect, url_for
import secrets


def chave_da_instalacao(connect):
    c = connect()
    try:
        c.execute('''INSERT INTO configuracao_instalacao(chave,valor) VALUES ('session_secret',?)
                     ON CONFLICT (chave) DO NOTHING''', (secrets.token_urlsafe(48),))
        c.commit()
        return c.execute("SELECT valor FROM configuracao_instalacao WHERE chave='session_secret'").fetchone()['valor']
    finally:
        c.close()


def fabrica_da_instalacao(app, m):
    if not app.config.get('FABRICA_UNICA', True):
        return None
    if hasattr(g, 'fabrica_da_instalacao'):
        return g.fabrica_da_instalacao
    c = m.conn()
    try:
        rows = c.execute('SELECT id,nome FROM fabricas WHERE ativa=1 ORDER BY id').fetchall()
    finally:
        c.close()
    if len(rows) != 1:
        raise RuntimeError('Esta instalação precisa de uma única fábrica consolidada.')
    g.fabrica_da_instalacao = dict(rows[0])
    return g.fabrica_da_instalacao


def registrar_instalacao(app, m, get_user):
    @app.before_request
    def validar_instalacao():
        if request.endpoint == 'static':
            return
        empresa = fabrica_da_instalacao(app, m)
        if empresa is None:
            return
        if request.path.startswith('/api/admin-') or request.path in (
                '/api/diag-fabricas', '/api/diag-usuarios', '/api/transferir-fabrica',
                '/api/corrigir-usuario', '/api/fix-icara'):
            return jsonify(erro='Esta instalação utiliza uma única fábrica.'), 410
        if 'uid' in session:
            user = get_user()
            if user is None:
                session.clear()
                if request.path.startswith('/api/'):
                    return jsonify(erro='Entre novamente no sistema.'), 401
                return redirect(url_for('login'))
            session.update(perfil=user['perfil'], fab_id=empresa['id'], nome=user['nome'])
        data = request.get_json(silent=True)
        candidates = [request.args.get('fabrica_id'), request.form.get('fabrica_id')]
        if isinstance(data, dict):
            candidates.append(data.get('fabrica_id'))
        for value in candidates:
            if value is None or value == '':
                continue
            try:
                valid = not isinstance(value, bool) and str(value) == str(empresa['id'])
            except (TypeError, ValueError):
                valid = False
            if not valid:
                return jsonify(erro='O acesso pertence somente à fábrica desta instalação.'), 403
