import json
import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from test_painel_tv import application, seed, connect
from exclusao_ops import limpar_testes_autorizados, LIMPEZA_TESTES


def connect_fk():
    c = connect()
    c.execute('PRAGMA foreign_keys=ON')
    return c


class ExclusaoOpsTests(unittest.TestCase):
    def setUp(self):
        c = connect()
        for table in ('fila_estado', 'exclusoes_ops_backup', 'lancamentos_fila'):
            c.execute(f'DROP TABLE IF EXISTS {table}')
        for table in ('faturamento', 'sequencia_op', 'balanceamento', 'balanceamento_operadoras', 'balanceamento_atribuicoes', 'notas_fiscais'):
            c.execute(f'DELETE FROM {table}')
        c.commit(); c.close()
        seed()
        self.client = application.app.test_client()
        self.login(1)

    def tearDown(self):
        c = connect()
        for table in ('fila_estado', 'exclusoes_ops_backup', 'lancamentos_fila'):
            c.execute(f'DROP TABLE IF EXISTS {table}')
        for table in ('faturamento', 'sequencia_op', 'balanceamento', 'balanceamento_operadoras', 'balanceamento_atribuicoes', 'notas_fiscais'):
            c.execute(f'DELETE FROM {table}')
        c.commit(); c.close()

    def login(self, uid):
        with self.client.session_transaction() as session:
            session['uid'] = uid

    def vincular(self):
        c = connect()
        c.execute("INSERT INTO turnos(id,fabrica_id,nome,hora_entrada,hora_saida) VALUES(99,1,'Teste','07:00','17:00') ON CONFLICT(id) DO NOTHING")
        c.execute("INSERT INTO planejamento_metas_op VALUES(1,'2026-10-04',99,18.5,45,12,15,100,'2026-10-04T07:00',1)")
        c.execute("INSERT INTO sequencia_metas_op(op_id,data) VALUES(1,'2026-10-04')")
        c.execute("INSERT INTO entradas_producao(fabrica_id,op_id,data,hora,qtd_produzida) VALUES(1,1,'2026-10-04','08:00',100)")
        c.execute("INSERT INTO faturamento(fabrica_id,op_id,data,quantidade) VALUES(1,1,'2026-10-04',100)")
        c.execute("INSERT INTO balanceamento(op_id,fabrica_id) VALUES(1,1)")
        c.execute("CREATE TABLE lancamentos_fila(id INTEGER PRIMARY KEY,op_id INTEGER REFERENCES ordens_producao(id),quantidade INTEGER)")
        c.execute('INSERT INTO lancamentos_fila VALUES(1,1,100)')
        c.execute('CREATE TABLE fila_estado(id INTEGER PRIMARY KEY,fila_json TEXT)')
        c.execute('INSERT INTO fila_estado VALUES(1,?)', (json.dumps([dict(opId='1'),dict(opId='3')]),))
        c.execute("INSERT INTO notas_fiscais(id,numero,fabrica_id,ops_vinculadas) VALUES(1,'NF01',1,'OP101, OP999')")
        c.execute("INSERT INTO metas_producao_dia VALUES(1,'2026-10-04',500,1,'teste')")
        c.execute("INSERT INTO metas_producao_dia VALUES(2,'2026-10-04',600,2,'teste')")
        c.commit(); c.close()

    def test_individual_limpa_vinculos_preserva_cadastros_e_outras_ops(self):
        self.vincular()
        with patch.object(application.m, 'conn', connect_fk):
            r = self.client.delete('/api/op/excluir/1', json={'confirmacao':'EXCLUIR'})
        self.assertEqual(r.status_code, 200, r.json)
        self.assertEqual(r.json['excluidas'], 1)
        c = connect()
        self.assertEqual([r[0] for r in c.execute('SELECT id FROM ordens_producao ORDER BY id')], [2,3])
        for table in ('producao','entradas_producao','faturamento','planejamento_metas_op','sequencia_metas_op','balanceamento','lancamentos_fila'):
            self.assertEqual(c.execute(f'SELECT COUNT(*) FROM {table} WHERE op_id=1').fetchone()[0], 0)
        self.assertEqual(c.execute('SELECT COUNT(*) FROM referencias').fetchone()[0], 2)
        self.assertEqual(c.execute('SELECT COUNT(*) FROM usuarios').fetchone()[0], 3)
        self.assertEqual(json.loads(c.execute('SELECT fila_json FROM fila_estado').fetchone()[0]), [dict(opId='3')])
        self.assertEqual(c.execute('SELECT ops_vinculadas FROM notas_fiscais').fetchone()[0], 'OP999')
        self.assertEqual(c.execute('SELECT COUNT(*) FROM metas_producao_dia').fetchone()[0], 2)
        copia = json.loads(c.execute('SELECT dados_json FROM exclusoes_ops_backup').fetchone()[0])
        self.assertEqual(copia['ops'][0]['numero'], '101')
        self.assertEqual(len(copia['tabelas']['producao']), 4)
        c.close()

    def test_todas_inclui_canceladas_e_preserva_outra_fabrica(self):
        self.vincular()
        c = connect(); c.execute("UPDATE ordens_producao SET situacao='CANCELADA' WHERE id=2"); c.commit(); c.close()
        with patch.object(application.m, 'conn', connect_fk):
            r = self.client.delete('/api/ops/excluir-todas', json={'confirmacao':'EXCLUIR TODAS'})
        self.assertEqual(r.status_code, 200, r.json)
        self.assertEqual(r.json['excluidas'], 2)
        c = connect()
        self.assertEqual(c.execute('SELECT id FROM ordens_producao').fetchone()[0], 3)
        self.assertEqual(c.execute('SELECT fabrica_id FROM metas_producao_dia').fetchone()[0], 2)
        c.close()
        self.assertEqual(self.client.get('/api/painel-producao?data=2026-10-04').json['resumo']['produzido'], 0)

    def test_permissoes_e_confirmacao(self):
        self.assertEqual(self.client.delete('/api/ops/excluir-todas', json={}).status_code, 400)
        self.assertEqual(self.client.delete('/api/op/excluir/3', json={'confirmacao':'EXCLUIR'}).status_code, 404)
        self.assertEqual(self.client.delete('/api/ops/excluir-todas', json={'confirmacao':'EXCLUIR TODAS','fabrica_id':2}).status_code, 403)
        self.login(2)
        self.assertEqual(self.client.delete('/api/ops/excluir-todas', json={'confirmacao':'EXCLUIR TODAS'}).status_code, 403)
        with self.client.session_transaction() as session:
            session.clear()
        self.assertEqual(self.client.delete('/api/op/excluir/1', json={'confirmacao':'EXCLUIR'}).status_code, 401)

    def test_falha_na_exclusao_reverte_tambem_backup_e_vinculos(self):
        self.vincular()
        c = connect(); c.execute("CREATE TRIGGER falha_exclusao BEFORE DELETE ON ordens_producao BEGIN SELECT RAISE(ABORT,'falha teste'); END"); c.commit(); c.close()
        try:
            with patch.object(application.m, 'conn', connect_fk), patch.object(application.app.logger, 'exception'):
                r = self.client.delete('/api/op/excluir/1', json={'confirmacao':'EXCLUIR'})
            self.assertEqual(r.status_code, 500)
            c = connect()
            self.assertEqual(c.execute('SELECT COUNT(*) FROM ordens_producao').fetchone()[0], 3)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM entradas_producao').fetchone()[0], 1)
            self.assertEqual(c.execute('SELECT ops_vinculadas FROM notas_fiscais').fetchone()[0], 'OP101, OP999')
            c.execute('DROP TRIGGER falha_exclusao'); c.commit(); c.close()
        finally:
            c = connect(); c.execute('DROP TRIGGER IF EXISTS falha_exclusao'); c.commit(); c.close()

    def preparar_instalacao_antiga(self):
        c = connect()
        c.execute("UPDATE fabricas SET nome='JTMTPI CONFECÇÕES' WHERE id=1")
        c.execute("INSERT INTO configuracao_instalacao VALUES('session_secret','teste') ON CONFLICT(chave) DO NOTHING")
        c.execute('CREATE TABLE consolidacao_fabricas_backup(id INTEGER PRIMARY KEY,criado_em TEXT)')
        c.execute("INSERT INTO consolidacao_fabricas_backup VALUES(1,'2026-10-04T12:00:00+00:00')")
        c.commit(); c.close()

    def test_limpeza_autorizada_uma_vez_preserva_op_real_posterior(self):
        self.preparar_instalacao_antiga()
        agora = datetime(2026,10,7,12,tzinfo=timezone.utc)
        self.assertTrue(limpar_testes_autorizados(connect_fk, agora=agora))
        c = connect()
        self.assertEqual(c.execute('SELECT COUNT(*) FROM ordens_producao WHERE fabrica_id=1').fetchone()[0], 0)
        c.execute("INSERT INTO ordens_producao(id,numero,fabrica_id,quantidade_total) VALUES(10,'REAL',1,1000)")
        c.commit(); c.close()
        self.assertFalse(limpar_testes_autorizados(connect_fk, agora=agora))
        c = connect(); self.assertEqual(c.execute('SELECT numero FROM ordens_producao WHERE id=10').fetchone()[0], 'REAL'); c.close()
        self.assertTrue(self.client.get('/api/status-publicacao-ops').json['limpeza_testes_concluida'])

    def test_limpeza_nao_roda_em_instalacao_nova_ou_outra_data(self):
        self.assertFalse(limpar_testes_autorizados(connect_fk, agora=datetime(2026,10,7,tzinfo=timezone.utc)))
        self.preparar_instalacao_antiga()
        self.assertFalse(limpar_testes_autorizados(connect_fk, agora=datetime(2026,10,8,tzinfo=timezone.utc)))
        c = connect(); self.assertEqual(c.execute('SELECT COUNT(*) FROM ordens_producao').fetchone()[0], 3); c.close()

    def test_edicao_preserva_data_saida_e_atualiza_situacao(self):
        c = connect(); c.execute("UPDATE ordens_producao SET data_entrega_costura='2026-10-10',obs='manter' WHERE id=1"); c.commit(); c.close()
        r = self.client.post('/api/op/salvar', json=dict(id=1,numero='REAL-EDIT',fabrica_id=1,referencia_id=1,
                                 descricao='Real',quantidade_total=1200,valor_unitario=10,situacao='PRODUCAO'))
        self.assertTrue(r.json['ok'], r.json)
        op = self.client.get('/api/op/1').json
        self.assertEqual(op['situacao'], 'PRODUCAO')
        self.assertEqual(op['quantidade_total'], 1200)
        self.assertEqual(op['data_entrega_costura'], '2026-10-10')
        self.assertEqual(op['obs'], 'manter')

    def test_nova_op_real_apos_limpeza_e_edicao_de_outra_fabrica(self):
        self.client.delete('/api/ops/excluir-todas', json={'confirmacao':'EXCLUIR TODAS'})
        dados = dict(numero='REAL',fabrica_id=1,ref_codigo='JEANS-01',quantidade_total=1500,
                     valor_unitario=10,situacao='PRODUCAO',data_entrega='2026-10-20')
        r = self.client.post('/api/op/salvar', json=dados)
        self.assertTrue(r.json['ok'], r.json)
        self.assertEqual(self.client.get('/api/op/'+str(r.json['op_id'])).json['situacao'], 'PRODUCAO')
        self.assertEqual(self.client.post('/api/op/salvar', json=dict(dados, id=3)).status_code, 403)


if __name__ == '__main__':
    unittest.main()
