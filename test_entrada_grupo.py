import unittest
from datetime import datetime
from unittest.mock import patch
from test_painel_tv import application, seed, connect
from metas_op import calcular_fila, planos_fila
from entrada_grupo import metas_entrada, painel_entrada


class EntradaGrupoTests(unittest.TestCase):
    def test_meta_da_op_em_entrada_independente_da_op_prevista(self):
        c = connect()
        try:
            c.execute('DELETE FROM jornada_calendario')
            c.execute('DELETE FROM turnos')
            c.execute("INSERT INTO turnos(id,fabrica_id,nome,hora_entrada,hora_saida_almoco,hora_entrada_almoco,hora_saida) VALUES(1,1,'Dia','07:00','12:00','13:30','17:30')")
            c.execute("UPDATE ordens_producao SET numero='24418' WHERE id=1")
            c.execute("UPDATE ordens_producao SET numero='24249' WHERE id=2")
            c.commit()
            fila = [dict(plano=dict(op_id=oid,numero=numero,data='2026-10-01',turno_id=1,
                                    operadores=meta,tempo_padrao=60,eficiencia=100))
                    for oid,numero,meta in [(1,'24418',105),(2,'24249',122)]]
            previsto = dict(meta=105*8.5,periodos={'08:00':105,'09:00':105,'10:00':105,
                '11:00':105,'12:00':105,'14:00':52.5,'15:00':105,'16:00':105,'17:00':105,'18:00':52.5})
            self.client.post('/api/entrada-grupo',json=dict(self.d,op_id=2,data='2026-10-13',quantidade=122,meta=0))
            resultado=painel_entrada(c,1,'2026-10-13',datetime(2026,10,13,15,10),previsto,fila)
            horas={p['hora']:p for p in resultado['periodos']}
            self.assertEqual(horas['08:00']['meta'],122)
            self.assertEqual(horas['08:00']['saldo'],0)
            self.assertEqual(horas['08:00']['eficiencia'],100)
            self.assertEqual(horas['14:00']['meta'],61)
            self.assertEqual(horas['16:00']['meta'],122)
            self.assertEqual(horas['16:00']['op_meta']['numero'],'24249')
            self.assertEqual(previsto['periodos']['08:00'],105)
            self.assertEqual(resultado['resumo']['meta'],122*9)
            # Mudança efetivamente apontada altera apenas os períodos posteriores.
            self.client.post('/api/entrada-grupo',json=dict(self.d,op_id=1,data='2026-10-13',hora='15:00',quantidade=105,meta=0))
            resultado=painel_entrada(c,1,'2026-10-13',datetime(2026,10,13,15,10),previsto,fila)
            horas={p['hora']:p for p in resultado['periodos']}
            self.assertEqual(horas['08:00']['meta'],122)
            self.assertEqual(horas['15:00']['meta'],105)
            self.assertEqual(horas['16:00']['meta'],105)
        finally:
            c.close()

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

    def test_apontamentos_08_permanecem_08_sem_voltar_para_entrada_07(self):
        self.assertEqual(self.client.post('/api/entrada-grupo', json=self.d).status_code, 200)
        self.assertEqual(self.client.post('/api/lancamento/salvar', json=dict(op_id=1,data='2026-10-04',hora='08:00',
                         operadores=45,qtd_produzida=150,qtd_projetada=180,eficiencia=83.3,
                         faturamento_hora=0,resultado_hora=0)).status_code, 200)
        dados = self.painel()
        for periodos in (dados['entrada']['periodos'], dados['periodos']):
            self.assertNotIn('07:00', [p['hora'] for p in periodos])
            self.assertGreater(next(p['produzido'] for p in periodos if p['hora'] == '08:00'), 0)
        self.assertEqual(self.client.get('/api/entrada-grupo?data=2026-10-04').json[0]['hora'], '08:00')


if __name__ == '__main__':
    unittest.main()
