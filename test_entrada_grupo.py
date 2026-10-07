import unittest
from datetime import datetime
from unittest.mock import patch
from test_painel_tv import application, seed, connect
from metas_op import calcular_fila, planos_fila
from entrada_grupo import metas_entrada


class EntradaGrupoTests(unittest.TestCase):
    def setUp(self):
        seed()
        self.client = application.app.test_client()
        self.login(1)
        self.d = dict(op_id=1, data='2026-10-04', hora='08:00', quantidade=150, meta=180)

    def login(self, uid):
        with self.client.session_transaction() as session:
            session['uid'] = uid

    def painel(self):
        return self.client.get('/api/painel-producao?data=2026-10-04').json

    def test_entrada_nao_soma_na_saida_nem_no_mes(self):
        antes = self.painel()
        self.assertEqual(self.client.post('/api/entrada-grupo', json=self.d).status_code, 200)
        depois = self.painel()
        self.assertEqual(depois['entrada']['resumo']['produzido'], 150)
        self.assertEqual(depois['entrada']['resumo']['saldo'], -30)
        self.assertEqual(depois['resumo'], antes['resumo'])
        self.assertEqual(depois['mes'], antes['mes'])
        self.assertEqual(depois['ops'], antes['ops'])

    def test_editar_excluir_e_isolamento(self):
        self.client.post('/api/entrada-grupo', json=self.d)
        r = self.client.get('/api/entrada-grupo?data=2026-10-04')
        self.assertEqual(r.headers['Cache-Control'], 'no-store')
        lid = r.json[0]['id']
        self.login(2)
        self.assertEqual(self.client.get('/api/entrada-grupo?data=2026-10-04').json, [])
        self.assertEqual(self.client.post('/api/entrada-grupo', json=dict(self.d, id=lid, op_id=3)).status_code, 403)
        self.assertEqual(self.client.delete(f'/api/entrada-grupo/{lid}').status_code, 403)
        self.login(1)
        self.assertEqual(self.client.post('/api/entrada-grupo', json=dict(self.d, id=lid, quantidade=200)).status_code, 200)
        self.assertEqual(self.painel()['entrada']['resumo']['produzido'], 200)
        self.assertEqual(self.client.delete(f'/api/entrada-grupo/{lid}').status_code, 200)
        self.assertEqual(self.painel()['entrada']['resumo']['produzido'], 0)

    def test_validacao_e_sessao(self):
        for campo, valor in [('quantidade', -1), ('quantidade', 1.5), ('quantidade', True),
                              ('hora', '25:00'), ('hora', '8:00'), ('data', '2026-02-30'), ('meta', -1)]:
            self.assertEqual(self.client.post('/api/entrada-grupo', json=dict(self.d, **{campo:valor})).status_code, 400)
        self.assertEqual(self.client.post('/api/entrada-grupo', json=dict(self.d, op_id=3)).status_code, 403)
        with self.client.session_transaction() as session:
            session.clear()
        self.assertEqual(self.client.get('/api/entrada-grupo?data=2026-10-04').status_code, 401)
        self.assertEqual(self.client.post('/api/entrada-grupo', json=self.d).status_code, 401)
        self.assertEqual(self.client.delete('/api/entrada-grupo/1').status_code, 401)

    def test_periodos_futuros_e_minutos(self):
        self.client.post('/api/entrada-grupo', json=dict(self.d, hora='09:30'))
        with patch('painel_tv.datetime') as clock:
            clock.now.return_value = datetime.fromisoformat('2026-10-04T09:59:59-03:00')
            antes = self.painel()['entrada']
            self.assertEqual(antes['periodos'][0]['hora'], '10:00')
            self.assertIsNone(antes['periodos'][0]['saldo'])
            self.assertEqual(antes['acompanhamento']['saldo'], 0)
            clock.now.return_value = datetime.fromisoformat('2026-10-04T10:00:00-03:00')
            depois = self.painel()['entrada']
            self.assertEqual(depois['acompanhamento']['saldo'], -30)

    def test_meta_entrada_primeiro_time_conserva_quantidade_e_antecipa_saida(self):
        c = connect()
        try:
            c.execute('DELETE FROM jornada_calendario')
            c.execute('DELETE FROM turnos')
            c.execute("INSERT INTO turnos(id,fabrica_id,nome,hora_entrada,hora_saida_almoco,hora_entrada_almoco,hora_saida,hora_saida_sexta) VALUES(1,1,'Dia','07:00','12:00','13:10','17:10','16:30')")
            c.commit()
            plano = dict(op_id=1, turno_id=1, data='2026-10-05', inicio='2026-10-05T07:00',
                         tempo_padrao='18.5', operadores='45', times='12', ciclo='15', eficiencia='100', salvar=True)
            self.assertEqual(self.client.post('/api/metas-op', json=plano).status_code, 200)
            fila = calcular_fila(c, planos_fila(c, 1))
            metas = metas_entrada(c, fila)
            self.assertAlmostEqual(sum(d['meta'] for d in metas.values()), 1000)
            dados = self.client.get('/api/painel-producao?data=2026-10-05').json
            por_hora = {p['hora']:p for p in dados['entrada']['periodos']}
            self.assertGreater(por_hora['08:00']['meta'], 0)
            saida = {p['hora']:p for p in dados['periodos']}
            self.assertEqual(saida['08:00']['meta'], 0)
            self.assertAlmostEqual(dados['entrada']['resumo']['meta'], metas['2026-10-05']['meta'])
        finally:
            c.close()


if __name__ == '__main__':
    unittest.main()
