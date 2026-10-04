"""Consolidação transacional das unidades existentes em uma fábrica."""
from datetime import datetime, timezone
import json
import re


def consolidar_fabricas(connect, nome_empresa, pg_mode=False):
    c = connect()
    try:
        if pg_mode:
            c.execute('SELECT pg_advisory_xact_lock(74201951)')
        else:
            c.execute('BEGIN IMMEDIATE')
        c.execute('''CREATE TABLE IF NOT EXISTS consolidacao_fabricas_backup (
            id INTEGER PRIMARY KEY, empresa TEXT NOT NULL,
            criado_em TEXT NOT NULL, dados_json TEXT NOT NULL)''')
        if c.execute('SELECT id FROM consolidacao_fabricas_backup WHERE id=1').fetchone():
            c.commit()
            return
        fabricas = [dict(r) for r in c.execute('SELECT * FROM fabricas ORDER BY id').fetchall()]
        if not fabricas:
            c.commit()
            return
        destino = fabricas[0]['id']
        if pg_mode:
            tabelas = [r[0] for r in c.execute('''SELECT col.table_name FROM information_schema.columns col
                JOIN information_schema.tables t ON t.table_schema=col.table_schema AND t.table_name=col.table_name
                WHERE col.table_schema=current_schema() AND col.column_name='fabrica_id'
                AND t.table_type='BASE TABLE' ORDER BY col.table_name''').fetchall()]
        else:
            tabelas = []
            for row in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall():
                name = row[0]
                if not re.fullmatch(r'[a-zA-Z_][a-zA-Z_0-9]*', name):
                    raise RuntimeError('Nome de tabela inválido na consolidação.')
                if any(col['name'] == 'fabrica_id' for col in c.execute(f'PRAGMA table_info("{name}")').fetchall()):
                    tabelas.append(name)
        snapshot = dict(fabrica_destino_id=destino, fabricas=fabricas, tabelas={})
        for tabela in tabelas:
            if not re.fullmatch(r'[a-zA-Z_][a-zA-Z_0-9]*', tabela):
                raise RuntimeError('Nome de tabela inválido na consolidação.')
            snapshot['tabelas'][tabela] = [dict(r) for r in c.execute(f'SELECT * FROM "{tabela}"').fetchall()]
        # Grava os valores originais, incluindo a unidade de origem, antes de alterar.
        c.execute('INSERT INTO consolidacao_fabricas_backup(id,empresa,criado_em,dados_json) VALUES (1,?,?,?)',
                  (nome_empresa, datetime.now(timezone.utc).isoformat(), json.dumps(snapshot, ensure_ascii=False, default=str)))
        for tabela in tabelas:
            if tabela == 'metas_producao_dia':
                # Metas simultâneas de unidades tornam-se a meta total da empresa.
                metas = c.execute('''SELECT data,SUM(quantidade) quantidade,MAX(atualizado_por) atualizado_por,
                                     MAX(atualizado_em) atualizado_em FROM metas_producao_dia GROUP BY data''').fetchall()
                c.execute('DELETE FROM metas_producao_dia')
                for meta in metas:
                    c.execute('''INSERT INTO metas_producao_dia(fabrica_id,data,quantidade,atualizado_por,atualizado_em)
                                 VALUES (?,?,?,?,?)''', (destino, meta['data'], meta['quantidade'], meta['atualizado_por'], meta['atualizado_em']))
            else:
                c.execute(f'UPDATE "{tabela}" SET fabrica_id=? WHERE fabrica_id IS NULL OR fabrica_id<>?', (destino, destino))
                total = c.execute(f'SELECT COUNT(*) FROM "{tabela}"').fetchone()[0]
                if total != len(snapshot['tabelas'][tabela]):
                    raise RuntimeError('A consolidação alterou a quantidade de registros.')
            if c.execute(f'SELECT COUNT(*) FROM "{tabela}" WHERE fabrica_id IS NULL OR fabrica_id<>?', (destino,)).fetchone()[0]:
                raise RuntimeError('Há registros fora da fábrica consolidada.')
        c.execute('UPDATE fabricas SET nome=?,ativa=1 WHERE id=?', (nome_empresa, destino))
        c.execute('DELETE FROM fabricas WHERE id<>?', (destino,))
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()
