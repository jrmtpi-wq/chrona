"""Recuperação única do admin solicitada pelo proprietário em 07/10/2026."""
from datetime import datetime, timezone
from exclusao_ops import LIMPEZA_TESTES, tabelas_existentes

CHAVE = 'recuperacao-admin-jtmtpi-2026-10-07'
SENHA_HASH = '9f553e88d33a1927209b3eaff808ae3beec40d2cbb1561065296a67164bedeb4'


def recuperar_admin(conn, pg=False, agora=None):
    agora = agora or datetime.now(timezone.utc)
    if agora.date().isoformat() != '2026-10-07':
        return False
    c = conn()
    try:
        if pg:
            c.execute('SELECT pg_advisory_xact_lock(74210007)')
        else:
            c.execute('BEGIN IMMEDIATE')
        # Só a instalação existente onde a manutenção autorizada foi concluída.
        if 'exclusoes_ops_backup' not in tabelas_existentes(c, pg):
            c.commit()
            return False
        if not c.execute('SELECT chave FROM exclusoes_ops_backup WHERE chave=?', (LIMPEZA_TESTES,)).fetchone():
            c.commit()
            return False
        fabricas = c.execute("SELECT id FROM fabricas WHERE nome='JTMTPI CONFECÇÕES'").fetchall()
        if len(fabricas) != 1:
            c.commit()
            return False
        usuarios = c.execute("""SELECT id FROM usuarios WHERE LOWER(login)='admin'
            AND perfil='admin' AND (fabrica_id=? OR fabrica_id IS NULL)""", (fabricas[0]['id'],)).fetchall()
        if len(usuarios) != 1:
            c.commit()
            return False
        c.execute('''CREATE TABLE IF NOT EXISTS recuperacoes_acesso (
            chave TEXT PRIMARY KEY, usuario_id INTEGER NOT NULL, criado_em TEXT NOT NULL)''')
        if c.execute('SELECT chave FROM recuperacoes_acesso WHERE chave=?', (CHAVE,)).fetchone():
            c.commit()
            return False
        uid = usuarios[0]['id']
        c.execute('UPDATE usuarios SET senha_hash=? WHERE id=?', (SENHA_HASH, uid))
        c.execute('INSERT INTO recuperacoes_acesso(chave,usuario_id,criado_em) VALUES(?,?,?)',
                  (CHAVE, uid, agora.isoformat()))
        c.commit()
        return True
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()
