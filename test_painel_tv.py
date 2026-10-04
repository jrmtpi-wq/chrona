"""Testes isolados: importa o app com SQLite temporário, sem init/seed de produção."""
import ast
from datetime import date
from pathlib import Path
import sqlite3
import sys
import tempfile
import types
import unittest

ROOT = Path(__file__).resolve().parent
TEMP = tempfile.TemporaryDirectory(prefix='chrona-painel-test-')
DB = str(Path(TEMP.name) / 'test.db')


def connect():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


# Aproveita o schema real sem importar models, que inicializa e semeia o banco.
tree = ast.parse((ROOT / 'models.py').read_text(encoding='utf-8-sig'))
schema = next(ast.literal_eval(node.value) for node in tree.body
              if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'SCHEMA_SQLITE' for t in node.targets))
c = connect()
c.executescript(schema)
c.close()
model = types.ModuleType('models')
model.conn = connect
sys.modules['models'] = model
import app as application


def seed():
    c = connect()
    for table in ('metas_producao_dia', 'producao', 'ordens_producao', 'referencias', 'usuarios', 'fabricas'):
        c.execute(f'DELETE FROM {table}')
    c.executemany('INSERT INTO fabricas(id,nome) VALUES (?,?)', [(1,'Fábrica Centro'),(2,'Fábrica Norte')])
    c.executemany('INSERT INTO usuarios(id,nome,login,senha_hash,perfil,fabrica_id) VALUES (?,?,?,?,?,?)',
                  [(1,'Gestor','gestor','test','gestor',1),(2,'Norte','norte','test','operador',2),(3,'Admin','admin','test','admin',None)])
    c.executemany('INSERT INTO referencias(id,codigo,descricao) VALUES (?,?,?)',
                  [(1,'JEANS-01','Jeans'),(2,'CAMISA-02','Camisa')])
    c.executemany('INSERT INTO ordens_producao(id,numero,fabrica_id,referencia_id,quantidade_total) VALUES (?,?,?,?,?)',
                  [(1,'101',1,1,1000),(2,'102',1,2,500),(3,'999',2,1,900)])
    c.executemany('INSERT INTO producao(id,fabrica_id,op_id,data,hora,qtd_produzida,qtd_projetada,operadores) VALUES (?,?,?,?,?,?,?,?)',
                  [(1,1,1,'2026-10-03','08:00',200,200,4),
                   (2,1,1,'2026-10-04','08:00',80,100,4),
                   (3,1,1,'2026-10-04','09:00',100,120,4),
                   (4,1,2,'2026-10-04','09:30',120,80,2),
                   (5,2,3,'2026-10-04','08:00',999,999,8),
                   (6,1,1,'2026-10-05','08:00',700,700,4)])
    c.commit()
    c.close()


class PainelTVTests(unittest.TestCase):
    def setUp(self):
        seed()
        self.client = application.app.test_client()
        self.login(1)

    def login(self, uid):
        with self.client.session_transaction() as session:
            session['uid'] = uid

    def get(self, query=''):
        return self.client.get('/api/painel-producao?data=2026-10-04' + query)

    def test_totals_weighted_efficiency_and_hourly(self):
        response = self.get()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        data = response.get_json()
        self.assertEqual(data['resumo'], dict(produzido=300, meta=300, eficiencia=100.0, lancamentos=3, saldo=0))
        self.assertEqual(data['horas'][1]['produzido'], 220)
        self.assertEqual(data['horas'][1]['meta'], 200)
        op = next(o for o in data['ops'] if o['op_id'] == 1)
        self.assertEqual(op['eficiencia'], 81.8)
        self.assertEqual(op['acumulado'], 380)
        self.assertEqual(op['restante'], 620)
        self.assertEqual(data['recentes'][0]['hora'], '09:30')

    def test_isolation_and_authorized_admin_selection(self):
        self.assertEqual(self.get('&fabrica_id=2').status_code, 403)
        self.assertEqual(len(self.get().get_json()['fabricas']), 1)
        self.login(3)
        data = self.get('&fabrica_id=2').get_json()
        self.assertEqual(len(data['fabricas']), 2)
        self.assertEqual(data['resumo']['produzido'], 999)
        self.assertEqual(len(data['ops']), 1)

    def test_authentication(self):
        self.client = application.app.test_client()
        self.assertEqual(self.get().status_code, 401)
        self.assertEqual(self.client.get('/painel-producao').status_code, 302)
        self.login(123456)
        self.assertEqual(self.get().status_code, 401)

    def test_empty_day_and_zero_production(self):
        data = self.client.get('/api/painel-producao?data=2026-01-01').get_json()
        self.assertEqual(data['resumo']['produzido'], 0)
        self.assertIsNone(data['resumo']['eficiencia'])
        self.assertEqual(data['ops'], [])
        c = connect()
        c.execute("UPDATE producao SET qtd_produzida=0 WHERE data='2026-10-04' AND fabrica_id=1")
        c.commit(); c.close()
        self.assertEqual(self.get().get_json()['resumo']['eficiencia'], 0)

    def test_no_meta_and_invalid_filters(self):
        c = connect()
        c.execute("UPDATE producao SET qtd_projetada=0 WHERE data='2026-10-04' AND fabrica_id=1")
        c.commit(); c.close()
        self.assertIsNone(self.get().get_json()['resumo']['eficiencia'])
        for query in ('data=2026-02-30','data=20261004','fabrica_id=abc'):
            self.assertEqual(self.client.get('/api/painel-producao?' + query).status_code, 400)

    def test_source_save_edit_delete_updates_panel(self):
        payload = dict(op_id=1, data='2026-10-04', hora='10:00', operadores=4,
                       qtd_produzida=20, qtd_projetada=10, eficiencia=200,
                       faturamento_hora=0, resultado_hora=0)
        self.assertTrue(self.client.post('/api/lancamento/salvar', json=payload).get_json()['ok'])
        self.assertEqual(self.get().get_json()['resumo']['produzido'], 320)
        c = connect()
        payload['id'] = c.execute('SELECT MAX(id) FROM producao').fetchone()[0]
        c.close()
        payload['qtd_produzida'] = 30
        self.assertTrue(self.client.post('/api/lancamento/salvar', json=payload).get_json()['ok'])
        self.assertEqual(self.get().get_json()['resumo']['produzido'], 330)
        self.assertTrue(self.client.delete('/api/lancamento/excluir/' + str(payload['id'])).get_json()['ok'])
        self.assertEqual(self.get().get_json()['resumo']['produzido'], 300)

    def test_corrupted_cross_factory_record_does_not_leak(self):
        c = connect()
        c.execute("INSERT INTO producao(fabrica_id,op_id,data,hora,qtd_produzida) VALUES (1,3,'2026-10-04','10:00',555)")
        c.commit(); c.close()
        self.assertEqual(self.get().get_json()['resumo']['produzido'], 300)

    def test_page_and_navigation(self):
        self.assertEqual(self.client.get('/painel-producao').status_code, 200)
        page = self.client.get('/lancamento').get_data(as_text=True)
        self.assertIn('Gestão à vista · TV', page)

    def test_daily_target_save_replace_and_date_isolation(self):
        self.assertIsNone(self.get().get_json()['meta_dia']['quantidade'])
        target = dict(fabrica_id=1, data='2026-10-04', quantidade=500)
        self.assertTrue(self.client.post('/api/painel-producao/meta-dia', json=target).get_json()['ok'])
        self.assertEqual(self.get().get_json()['meta_dia'], dict(quantidade=500, atingimento=60.0, faltam=200))
        self.assertEqual(self.get().get_json()['resumo']['meta'], 300)
        target['quantidade'] = 200
        self.assertEqual(self.client.post('/api/painel-producao/meta-dia', json=target).status_code, 200)
        self.assertEqual(self.get().get_json()['meta_dia'], dict(quantidade=200, atingimento=150.0, faltam=0))
        self.assertIsNone(self.client.get('/api/painel-producao?data=2026-10-03').get_json()['meta_dia']['quantidade'])
        self.login(3)
        self.assertIsNone(self.get('&fabrica_id=2').get_json()['meta_dia']['quantidade'])
        c = connect()
        self.assertEqual(c.execute('SELECT COUNT(*) FROM metas_producao_dia').fetchone()[0], 1)
        c.close()

    def test_daily_target_permissions_and_validation(self):
        target = dict(fabrica_id=1, data='2026-10-04', quantidade=500)
        self.assertEqual(self.client.post('/api/painel-producao/meta-dia', json={**target, 'fabrica_id':2}).status_code, 403)
        for quantidade in (0, -5, 2.5, True, '500', None, 10000001):
            self.assertEqual(self.client.post('/api/painel-producao/meta-dia', json={**target, 'quantidade':quantidade}).status_code, 400)
        self.assertEqual(self.client.post('/api/painel-producao/meta-dia', json={**target, 'data':'2026-02-30'}).status_code, 400)
        self.login(2)
        self.assertFalse(self.get('&fabrica_id=2').get_json()['pode_editar_meta'])
        self.assertEqual(self.client.post('/api/painel-producao/meta-dia', json={**target,'fabrica_id':2}).status_code, 403)
        self.client = application.app.test_client()
        self.assertEqual(self.client.post('/api/painel-producao/meta-dia', json=target).status_code, 401)

    def test_daily_target_before_first_pointing(self):
        target = dict(fabrica_id=1, data='2026-01-01', quantidade=500)
        self.assertEqual(self.client.post('/api/painel-producao/meta-dia', json=target).status_code, 200)
        data = self.client.get('/api/painel-producao?data=2026-01-01').get_json()
        self.assertEqual(data['meta_dia'], dict(quantidade=500, atingimento=0.0, faltam=500))


if __name__ == '__main__':
    if '--serve' in sys.argv:
        seed()
        @application.app.get('/test-login')
        def test_login():
            from flask import session, redirect
            session['uid'] = 1
            return redirect('/painel-producao?data=2026-10-04')
        application.app.run(host='127.0.0.1', port=5051, debug=False, use_reloader=False)
    else:
        unittest.main()
