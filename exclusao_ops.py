"""Exclusão transacional de OPs, com cópia dos vínculos removidos."""
from datetime import datetime, timezone
import json
import re
from flask import jsonify, request

LIMPEZA_TESTES = 'ops-teste-jtmtpi-2026-10-07'
VINCULOS = ('sequencia_metas_op', 'planejamento_metas_op', 'entradas_producao',
            'producao', 'lancamentos_fila', 'balanceamento_atribuicoes',
            'balanceamento_operadoras', 'balanceamento', 'sequencia_op', 'faturamento')


def tabelas_existentes(c, pg):
    sql = ("SELECT table_name FROM information_schema.tables WHERE table_schema=current_schema() AND table_type='BASE TABLE'"
           if pg else "SELECT name FROM sqlite_master WHERE type='table'")
    return {r[0] for r in c.execute(sql).fetchall()}


def preparar_backup(c):
    c.execute('''CREATE TABLE IF NOT EXISTS exclusoes_ops_backup (
        chave TEXT PRIMARY KEY, criado_em TEXT NOT NULL,
        usuario_id INTEGER, dados_json TEXT NOT NULL)''')


def excluir_registros(c, op_ids, fabrica_ids, chave, usuario_id=None, pg=False, limpar_metas=False):
    """O chamador abre a transação; a cópia e a exclusão são confirmadas juntas."""
    existentes = tabelas_existentes(c, pg)
    preparar_backup(c)
    ph = ','.join('?' * len(op_ids))
    fab_ph = ','.join('?' * len(fabrica_ids))
    backup = dict(ops=[], tabelas={}, filas=[], notas=[])
    if op_ids:
        backup['ops'] = [dict(r) for r in c.execute(f'SELECT * FROM ordens_producao WHERE id IN ({ph})', op_ids).fetchall()]
        for tabela in VINCULOS:
            if tabela in existentes:
                backup['tabelas'][tabela] = [dict(r) for r in c.execute(f'SELECT * FROM {tabela} WHERE op_id IN ({ph})', op_ids).fetchall()]
        if 'fila_estado' in existentes:
            for row in c.execute('SELECT * FROM fila_estado').fetchall():
                itens = json.loads(row['fila_json'] or '[]')
                restantes = [i for i in itens if str(i.get('opId', i.get('op_id'))) not in {str(oid) for oid in op_ids}]
                if len(restantes) != len(itens):
                    backup['filas'].append(dict(row))
                    c.execute('UPDATE fila_estado SET fila_json=? WHERE id=?', (json.dumps(restantes, ensure_ascii=False), row['id']))
        if 'notas_fiscais' in existentes:
            numeros = {re.sub(r'^OP[\s-]*', '', str(r['numero']).strip(), flags=re.I) for r in backup['ops']}
            for row in c.execute(f'SELECT * FROM notas_fiscais WHERE fabrica_id IN ({fab_ph})', fabrica_ids).fetchall():
                vinculos = re.split(r'[,;\n]+', row['ops_vinculadas'] or '')
                restantes = [v for v in vinculos if re.sub(r'^OP[\s-]*', '', v.strip(), flags=re.I) not in numeros]
                if len(restantes) != len(vinculos):
                    backup['notas'].append(dict(row))
                    c.execute('UPDATE notas_fiscais SET ops_vinculadas=? WHERE id=?', (', '.join(v.strip() for v in restantes if v.strip()), row['id']))
    if limpar_metas and fabrica_ids:
        backup['tabelas']['metas_producao_dia'] = [dict(r) for r in c.execute(
            f'SELECT * FROM metas_producao_dia WHERE fabrica_id IN ({fab_ph})', fabrica_ids).fetchall()]
    c.execute('INSERT INTO exclusoes_ops_backup(chave,criado_em,usuario_id,dados_json) VALUES(?,?,?,?)',
              (chave, datetime.now(timezone.utc).isoformat(), usuario_id, json.dumps(backup, ensure_ascii=False, default=str)))
    if op_ids:
        for tabela in VINCULOS:
            if tabela in existentes:
                c.execute(f'DELETE FROM {tabela} WHERE op_id IN ({ph})', op_ids)
        c.execute(f'DELETE FROM ordens_producao WHERE id IN ({ph})', op_ids)
    if limpar_metas and fabrica_ids:
        c.execute(f'DELETE FROM metas_producao_dia WHERE fabrica_id IN ({fab_ph})', fabrica_ids)
    return len(op_ids)


def limpar_testes_autorizados(connect, pg=False, agora=None):
    """Pedido de 07/10: somente a instalação existente JTMTPI, nessa data, uma vez."""
    agora = agora or datetime.now(timezone.utc)
    if agora.date().isoformat() != '2026-10-07':
        return False
    c = connect()
    try:
        if pg:
            c.execute('SELECT pg_advisory_xact_lock(74210007)')
        else:
            c.execute('BEGIN IMMEDIATE')
        preparar_backup(c)
        if c.execute('SELECT chave FROM exclusoes_ops_backup WHERE chave=?', (LIMPEZA_TESTES,)).fetchone():
            c.commit()
            return False
        # Exige a instalação antiga já consolidada, evitando atingir instalações novas.
        tabelas = tabelas_existentes(c, pg)
        consolidacao = (c.execute('SELECT criado_em FROM consolidacao_fabricas_backup WHERE id=1').fetchone()
                        if 'consolidacao_fabricas_backup' in tabelas else None)
        fabrica = c.execute("SELECT id FROM fabricas WHERE nome='JTMTPI CONFECÇÕES'").fetchall()
        if not consolidacao or consolidacao['criado_em'][:10] >= '2026-10-07' or len(fabrica) != 1:
            c.commit()
            return False
        fid = fabrica[0]['id']
        ids = [r['id'] for r in c.execute('SELECT id FROM ordens_producao WHERE fabrica_id=?', (fid,)).fetchall()]
        excluir_registros(c, ids, [fid], LIMPEZA_TESTES, pg=pg, limpar_metas=True)
        c.commit()
        return True
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


def registrar_exclusao(app, m, get_user, fab_ids):
    @app.get('/api/status-publicacao-ops')
    def status_publicacao_ops():
        # Somente a conclusão da manutenção: nenhum cadastro ou backup é exposto.
        c = m.conn()
        try:
            if 'exclusoes_ops_backup' not in tabelas_existentes(c, getattr(m, 'PG_MODE', False)):
                concluida = False
            else:
                concluida = c.execute('SELECT chave FROM exclusoes_ops_backup WHERE chave=?', (LIMPEZA_TESTES,)).fetchone() is not None
            response = jsonify(limpeza_testes_concluida=concluida)
            response.headers['Cache-Control'] = 'no-store'
            return response
        finally:
            c.close()

    def executar(oid=None):
        user = get_user()
        if user is None:
            return jsonify(erro='Entre no sistema.'), 401
        if user['perfil'] not in ('admin', 'gestor'):
            return jsonify(erro='Somente gestores e administradores podem excluir OPs.'), 403
        d = request.get_json(silent=True) or {}
        if d.get('confirmacao') != ('EXCLUIR TODAS' if oid is None else 'EXCLUIR'):
            return jsonify(erro='Confirme a exclusão solicitada.'), 400
        fids = [i for i in fab_ids(user) if i is not None]
        if oid is None and d.get('fabrica_id') is not None:
            if type(d['fabrica_id']) is not int or d['fabrica_id'] not in fids:
                return jsonify(erro='Fábrica não autorizada.'), 403
            fids = [d['fabrica_id']]
        if not fids:
            return jsonify(erro='Fábrica não autorizada.'), 403
        c = m.conn()
        try:
            pg = getattr(m, 'PG_MODE', False)
            if pg:
                c.execute('SELECT pg_advisory_xact_lock(74210007)')
            else:
                c.execute('BEGIN IMMEDIATE')
            ph = ','.join('?' * len(fids))
            params = list(fids)
            sql = f'SELECT id FROM ordens_producao WHERE fabrica_id IN ({ph})'
            if oid is not None:
                sql += ' AND id=?'
                params.append(oid)
            ids = [r['id'] for r in c.execute(sql, params).fetchall()]
            if oid is not None and not ids:
                return jsonify(erro='OP não autorizada ou não encontrada.'), 404
            from uuid import uuid4
            quantidade = excluir_registros(c, ids, fids, uuid4().hex, user['id'], pg, limpar_metas=oid is None)
            c.commit()
            return jsonify(ok=True, excluidas=quantidade)
        except Exception:
            c.rollback()
            app.logger.exception('Falha ao excluir OPs')
            return jsonify(erro='Não foi possível excluir as OPs. Nenhum registro foi removido.'), 500
        finally:
            c.close()

    @app.delete('/api/op/excluir/<int:oid>')
    def excluir_op(oid):
        return executar(oid)

    @app.delete('/api/ops/excluir-todas')
    def excluir_todas_ops():
        return executar()
