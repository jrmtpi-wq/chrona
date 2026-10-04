import ast
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import os

from fabrica_unica import consolidar_fabricas
from instalacao import chave_da_instalacao
import test_painel_tv as base


class ConsolidacaoTests(unittest.TestCase):
    def setUp(self):
        base.seed()

    def test_preserves_records_ids_logins_and_history(self):
        c = base.connect()
        c.execute("INSERT INTO metas_producao_dia VALUES (1,'2026-10-04',500,1,'teste')")
        c.execute("INSERT INTO metas_producao_dia VALUES (2,'2026-10-04',600,2,'teste')")
        before = {t:[dict(r) for r in c.execute(f'SELECT * FROM {t} ORDER BY id').fetchall()]
                  for t in ('usuarios','ordens_producao','producao','referencias')}
        c.commit(); c.close()
        consolidar_fabricas(base.connect, 'JTMTPI CONFECÇÕES')
        c = base.connect()
        self.assertEqual([dict(r) for r in c.execute('SELECT id,nome FROM fabricas')], [dict(id=1,nome='JTMTPI CONFECÇÕES')])
        for tabela, rows in before.items():
            current = [dict(r) for r in c.execute(f'SELECT * FROM {tabela} ORDER BY id')]
            self.assertEqual(len(current),len(rows))
            for old, new in zip(rows,current):
                if 'fabrica_id' in old:
                    old['fabrica_id'] = 1
                self.assertEqual(old,new)
        self.assertEqual(c.execute('SELECT quantidade FROM metas_producao_dia').fetchone()[0],1100)
        backup = json.loads(c.execute('SELECT dados_json FROM consolidacao_fabricas_backup').fetchone()[0])
        self.assertEqual(len(backup['fabricas']),2)
        self.assertEqual(len(backup['tabelas']['metas_producao_dia']),2)
        self.assertEqual(backup['tabelas']['usuarios'][1]['fabrica_id'],2)
        c.close()

    def test_repeat_does_not_overwrite_backup_or_daily_targets(self):
        consolidar_fabricas(base.connect, 'JTMTPI CONFECÇÕES')
        c = base.connect()
        saved = c.execute('SELECT dados_json FROM consolidacao_fabricas_backup').fetchone()[0]
        c.execute("INSERT INTO metas_producao_dia VALUES (1,'2026-10-04',500,1,'teste')")
        c.commit(); c.close()
        consolidar_fabricas(base.connect, 'JTMTPI CONFECÇÕES')
        c = base.connect()
        self.assertEqual(c.execute('SELECT dados_json FROM consolidacao_fabricas_backup').fetchone()[0],saved)
        self.assertEqual(c.execute('SELECT quantidade FROM metas_producao_dia').fetchone()[0],500)
        c.close()

    def test_failure_rolls_back_all_changes(self):
        c = base.connect()
        c.execute('CREATE TABLE collision_test(id INTEGER PRIMARY KEY,fabrica_id INTEGER, codigo TEXT, UNIQUE(fabrica_id,codigo))')
        c.executemany('INSERT INTO collision_test VALUES (?,?,?)',[(1,1,'X'),(2,2,'X')])
        c.commit(); c.close()
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                consolidar_fabricas(base.connect,'JTMTPI CONFECÇÕES')
            c = base.connect()
            self.assertEqual(c.execute('SELECT COUNT(*) FROM fabricas').fetchone()[0],2)
            self.assertEqual(c.execute('SELECT fabrica_id FROM usuarios WHERE id=2').fetchone()[0],2)
            self.assertFalse(c.execute("SELECT name FROM sqlite_master WHERE name='consolidacao_fabricas_backup'").fetchone())
            c.close()
        finally:
            c = base.connect(); c.execute('DROP TABLE collision_test'); c.commit(); c.close()

    def test_secret_is_stable_and_independent_per_database(self):
        first = chave_da_instalacao(base.connect)
        self.assertEqual(first,chave_da_instalacao(base.connect))
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp)/'outro.db')
            def connect():
                c = sqlite3.connect(db); c.row_factory=sqlite3.Row; return c
            c = connect(); c.execute('CREATE TABLE configuracao_instalacao(chave TEXT PRIMARY KEY,valor TEXT)'); c.close()
            self.assertNotEqual(first,chave_da_instalacao(connect))


class FabricaUnicaAppTests(unittest.TestCase):
    def setUp(self):
        base.seed()
        consolidar_fabricas(base.connect,'JTMTPI CONFECÇÕES')
        self.app = base.application.app
        self.app.config['FABRICA_UNICA'] = True
        self.client = self.app.test_client()
        with self.client.session_transaction() as session:
            session.update(uid=3,perfil='admin')

    def tearDown(self):
        self.app.config['FABRICA_UNICA'] = False

    def test_admin_sees_only_company_and_combined_units(self):
        response = self.client.get('/api/painel-producao?data=2026-10-04')
        self.assertEqual(response.status_code,200)
        data = response.get_json()
        self.assertEqual(data['fabricas'],[dict(id=1,nome='JTMTPI CONFECÇÕES')])
        self.assertEqual(data['resumo']['produzido'],1299)
        self.assertEqual(len(data['ops']),3)
        self.assertEqual(self.client.get('/api/fabricas').get_json()[0]['nome'],'JTMTPI CONFECÇÕES')

    def test_rejects_another_factory_and_old_transfer_tools(self):
        self.assertEqual(self.client.get('/api/painel-producao?fabrica_id=2').status_code,403)
        self.assertEqual(self.client.post('/api/lancamento/salvar',json=dict(fabrica_id=2)).status_code,403)
        self.assertEqual(self.client.get('/api/admin-renomear-fabricas').status_code,410)
        self.assertEqual(self.client.post('/api/transferir-fabrica',json=dict(fabrica_destino=2)).status_code,410)

    def test_login_branding_and_users_have_no_multi_factory_choice(self):
        self.assertIn('JTMTPI CONFECÇÕES',self.client.get('/login').get_data(as_text=True))
        page = self.client.get('/usuarios').get_data(as_text=True)
        self.assertIn('Acesso completo à empresa',page)
        self.assertNotIn('Acesso a todas as fábricas',page)
        self.assertIn('grupo.style.display = true',page)

    def test_former_unit_user_retains_access(self):
        with self.client.session_transaction() as session:
            session.update(uid=2,perfil='operador',fab_id=2)
        response = self.client.get('/api/painel-producao?data=2026-10-04')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.get_json()['resumo']['produzido'],1299)
        with self.client.session_transaction() as session:
            self.assertEqual(session['fab_id'],1)


class BootstrapTests(unittest.TestCase):
    def test_real_bootstrap_and_restart_preserve_existing_users(self):
        # Executa o módulo real em banco temporário, sem o bootstrap de importação.
        path = Path(__file__).with_name('models.py')
        tree = ast.parse(path.read_text(encoding='utf-8'))
        tree.body = tree.body[:-1]
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'CHRONA_ADMIN_SENHA':'senha-somente-teste-123'}, clear=False):
            with patch.dict(os.environ):
                os.environ.pop('DATABASE_URL', None)
                namespace = {'__file__':str(path), '__name__':'models_bootstrap_test'}
                exec(compile(tree,str(path),'exec'),namespace)
                namespace['DB'] = str(Path(tmp)/'chrona.db')
                namespace['inicializar_instalacao']()
                c = namespace['conn']()
                self.assertEqual(c.execute('SELECT COUNT(*) FROM fabricas').fetchone()[0],1)
                user = dict(c.execute('SELECT * FROM usuarios').fetchone())
                self.assertEqual(user['fabrica_id'],1)
                self.assertEqual(user['senha_hash'],namespace['hash_senha']('senha-somente-teste-123'))
                c.close()
                namespace['inicializar_instalacao']()
                c = namespace['conn']()
                self.assertEqual(dict(c.execute('SELECT * FROM usuarios').fetchone()),user)
                self.assertEqual(c.execute('SELECT COUNT(*) FROM fabricas').fetchone()[0],1)
                c.close()


if __name__=='__main__':
    unittest.main()
