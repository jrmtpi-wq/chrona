import unittest
from unittest.mock import patch
from datetime import datetime, date
from test_painel_tv import application, seed, connect
from metas_op import calcular, intervalos, importar_planejamentos, planos_fila, calcular_fila, metas_programadas, atualizar_previsoes, avancar


class MetasTest(unittest.TestCase):
    def setUp(self):
        c=connect()
        c.execute('DELETE FROM sequencia_metas_op')
        c.execute('DELETE FROM planejamento_metas_op')
        c.execute('DELETE FROM jornada_calendario')
        c.execute('DELETE FROM turnos')
        c.commit(); c.close()
        seed()
        self.c=connect()
        self.c.execute("INSERT INTO turnos(id,fabrica_id,nome,hora_entrada,hora_saida_almoco,hora_entrada_almoco,hora_saida,hora_saida_sexta) VALUES(1,1,'Dia','07:00','12:00','13:10','17:10','16:30')")
        self.c.execute('UPDATE ordens_producao SET quantidade_total=2000 WHERE id=1')
        self.c.commit()
        self.turno=dict(self.c.execute('SELECT * FROM turnos WHERE id=1').fetchone())
        self.op=dict(self.c.execute('SELECT * FROM ordens_producao WHERE id=1').fetchone())
        self.d=dict(op_id=1, turno_id=1,data='2026-10-05',inicio='2026-10-05T07:00',tempo_padrao='18.50',operadores='45',times='12',ciclo='15',eficiencia='100')
        self.client=application.app.test_client()
    def tearDown(self):
        self.c.close()
    def test_exemplo(self):
        r=calcular(self.c,self.op,self.turno,self.d)
        self.assertAlmostEqual(r['meta_dia'],1313.5135135)
        self.assertAlmostEqual(r['meta_hora'],145.9459459)
        self.assertEqual(r['primeira_peca'],'2026-10-05T10:00:00')
        self.assertTrue(r['saida'].startswith('2026-10-06T15:51:48'))
    def test_first_finished_piece_anchor_persists_and_supplies_next_day_target(self):
        self.login(1)
        self.c.execute('UPDATE ordens_producao SET quantidade_total=892 WHERE id=1')
        self.c.commit()
        payload = dict(self.d, data='2026-10-06', inicio='2026-10-06T15:30',
                       referencia_inicio='primeira_peca', tempo_padrao='30', operadores='60', salvar=True)
        response = self.client.post('/api/metas-op', json=payload)
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(response.json['resultado']['primeira_peca'], '2026-10-06T15:30:00')
        fila = calcular_fila(self.c, planos_fila(self.c, 1))
        self.assertEqual(fila[0]['resultado']['primeira_peca'], '2026-10-06T15:30:00')
        metas = metas_programadas(self.c, fila)
        self.assertGreater(metas['2026-10-07']['meta'], 0)
        self.assertAlmostEqual(sum(d['meta'] for d in metas.values()), 892)
        for hora in ('08:00', '09:00', '10:00', '11:00', '12:00'):
            self.client.post('/api/lancamento/salvar', json=dict(op_id=1,data='2026-10-07',hora=hora,
                operadores=60,qtd_produzida=120,qtd_projetada=0,eficiencia=0,faturamento_hora=0,resultado_hora=0))
        dados = self.client.get('/api/painel-producao?data=2026-10-07').json
        self.assertGreater(dados['meta_dia']['quantidade'], 0)
        self.assertEqual(next(p['produzido'] for p in dados['periodos'] if p['hora']=='11:00'), 120)

    def test_ciclo_por_op(self):
        r=calcular(self.c,self.op,self.turno,dict(self.d,ciclo='20'))
        self.assertEqual(r['primeira_peca'],'2026-10-05T11:00:00')
    def test_pausa_feriado_sexta(self):
        self.assertEqual(sum((b-a).total_seconds()/60 for a,b in intervalos(self.c,self.turno,date(2026,10,9))),500)
        self.c.execute("INSERT INTO jornada_calendario(fabrica_id,turno_id,data,tipo,minutos_disponiveis) VALUES(1,1,'2026-10-06','FERIADO',0)")
        r=calcular(self.c,self.op,self.turno,dict(self.d,inicio='2026-10-05T11:00'))
        self.assertEqual(r['primeira_peca'],'2026-10-05T15:10:00')
        self.assertTrue(r['saida'].startswith('2026-10-08'))
    def login(self,uid):
        with self.client.session_transaction() as s:s['uid']=uid
    def test_acesso_e_salvar(self):
        self.assertEqual(self.client.post('/api/metas-op',json=self.d).status_code,401)
        self.login(2)
        self.assertEqual(self.client.post('/api/metas-op',json=self.d).status_code,403)
        self.login(1)
        self.assertEqual(self.client.get('/metas-op').status_code,200)
        r=self.client.post('/api/metas-op',json=dict(self.d,salvar=True))
        self.assertEqual(r.status_code,200,r.json)
        r=self.client.get('/api/metas-op?op_id=1&data=2026-10-05')
        self.assertEqual(r.json['plano']['ciclo'],15)
        self.assertEqual(self.client.post('/api/metas-op',json=dict(self.d,op_id=3)).status_code,403)
    def test_invalidos(self):
        self.login(1)
        for chave,valor in [('ciclo','nan'),('operadores','1.5'),('tempo_padrao','0'),('eficiencia','101'),('inicio','2026-10-06T07:00')]:
            self.assertEqual(self.client.post('/api/metas-op',json=dict(self.d,**{chave:valor})).status_code,400)

    def salvar(self, **campos):
        r=self.client.post('/api/metas-op',json=dict(self.d,salvar=True,**campos))
        self.assertEqual(r.status_code,200,r.json)
        return r.json

    def test_fila_datas_e_recalculo(self):
        self.login(1)
        primeiro=self.salvar()
        segundo=self.salvar(op_id=2,ciclo='20')
        fila=segundo['fila']
        self.assertEqual(fila[1]['resultado']['entrada'],fila[0]['resultado']['fim_entrada'])
        self.assertGreaterEqual(datetime.fromisoformat(fila[1]['resultado']['primeira_peca']),
                         avancar(self.c, self.turno, datetime.fromisoformat(fila[0]['resultado']['saida']), 20))
        self.assertGreater(fila[1]['resultado']['primeira_peca'],fila[1]['resultado']['entrada'])
        chave=segundo['data_original']
        novo=self.salvar(data_original=primeiro['data_original'],data='2026-10-07',inicio='2026-10-07T07:00')
        self.assertEqual(novo['fila'][1]['resultado']['entrada'],novo['fila'][0]['resultado']['fim_entrada'])
        self.assertEqual(novo['fila'][1]['plano']['data'],chave)
        self.salvar(op_id=2,data_original=chave,ciclo='25')
        self.assertEqual(len(self.client.get('/api/metas-op/fila').json['fila']),2)

    def test_fila_fim_turno_e_folga(self):
        self.login(1)
        self.c.execute('UPDATE ordens_producao SET quantidade_total=1 WHERE id=1')
        self.c.execute("INSERT INTO jornada_calendario(fabrica_id,turno_id,data,tipo,minutos_disponiveis) VALUES(1,1,'2026-10-12','FERIADO',0)")
        self.c.commit()
        self.salvar(data='2026-10-09',inicio='2026-10-09T16:00',times='2',ciclo='15')
        segundo=self.salvar(op_id=2)
        self.assertEqual(segundo['resultado']['entrada'],'2026-10-09T16:15:00')
        self.assertEqual(segundo['resultado']['primeira_peca'],'2026-10-13T09:45:00')

    def test_gestao_planejado_sem_apontamentos(self):
        self.login(1)
        self.salvar()
        self.salvar(op_id=2,ciclo='20')
        fila=calcular_fila(self.c,planos_fila(self.c,1))
        dias=metas_programadas(self.c,fila)
        self.assertAlmostEqual(sum(p['meta'] for p in dias.values()),2500,places=5)
        self.assertAlmostEqual(dias['2026-10-05']['meta'],1+360*45/18.5,places=5)
        r=self.client.get('/api/painel-producao?data=2026-10-05').json
        self.assertEqual(r['fonte_meta'],'programacao')
        self.assertAlmostEqual(r['meta_dia']['quantidade'],dias['2026-10-05']['meta'])
        self.assertAlmostEqual(sum(p['meta'] for p in r['periodos']),r['meta_dia']['quantidade'])
        self.assertEqual(r['resumo']['produzido'],700)
        self.assertFalse(r['pode_editar_meta'])
        self.assertEqual(len(r['programacao']),1)
        por_hora={p['hora']:p for p in r['periodos']}
        self.assertEqual(por_hora['08:00']['meta'],0)
        self.assertEqual(por_hora['09:00']['meta'],0)
        self.assertEqual(por_hora['10:00']['meta'],1)
        self.assertEqual(r['ops'][0]['numero'],'101')
        # Dias posteriores à data escolhida não entram no acumulado mensal.
        self.assertAlmostEqual(r['mes']['meta'],r['meta_dia']['quantidade'])
        self.assertEqual(self.client.get('/api/painel-producao?data=2026-10-04').json['fonte_meta'],'lancamentos')

    def test_troca_continua_ultimo_pacote_1630_proximo_1645(self):
        self.login(1)
        self.c.execute('UPDATE ordens_producao SET quantidade_total=961 WHERE id=1')
        self.c.commit()
        self.salvar(tempo_padrao='15')
        fila = self.salvar(op_id=2, tempo_padrao='15')['fila']
        self.assertEqual(fila[0]['resultado']['saida'], '2026-10-05T16:30:00')
        self.assertEqual(fila[1]['resultado']['entrada'], '2026-10-05T13:45:00')
        self.assertEqual(fila[1]['resultado']['primeira_peca'], '2026-10-05T16:45:00')
        dias = metas_programadas(self.c, fila)
        self.assertAlmostEqual(dias['2026-10-05']['ops'][2], 76)
        self.assertAlmostEqual(dias['2026-10-05']['meta'], 1037)
        self.assertAlmostEqual(sum(d['meta'] for d in dias.values()), 1461)

    def test_troca_no_primeiro_time_0730_proximo_pacote_0745(self):
        self.login(1)
        self.c.execute('UPDATE ordens_producao SET quantidade_total=46 WHERE id=1')
        self.c.commit()
        self.salvar(tempo_padrao='15', times='2')
        fila = self.salvar(op_id=2, tempo_padrao='15', times='2')['fila']
        self.assertEqual(fila[0]['resultado']['fim_entrada'], '2026-10-05T07:30:00')
        self.assertEqual(fila[1]['resultado']['entrada'], '2026-10-05T07:30:00')
        self.assertEqual(avancar(self.c, self.turno, datetime.fromisoformat(fila[1]['resultado']['entrada']), 15),
                         datetime.fromisoformat('2026-10-05T07:45:00'))
        self.assertEqual(fila[1]['resultado']['primeira_peca'], '2026-10-05T08:00:00')

    def test_tv_nao_antecipa_perda_dos_periodos_futuros(self):
        self.login(1)
        self.salvar()
        for relogio, pendente in [('10:59:59', True), ('11:00:00', False)]:
            with patch('painel_tv.datetime') as clock:
                clock.now.return_value = datetime.fromisoformat('2026-10-05T' + relogio + '-03:00')
                dados = self.client.get('/api/painel-producao?data=2026-10-05').json
                periodo = next(p for p in dados['periodos'] if p['hora'] == '11:00')
                self.assertGreater(periodo['meta'], 0)
                self.assertEqual(periodo['pendente'], pendente)
                encerrados = [p for p in dados['periodos'] if not p['pendente']]
                self.assertAlmostEqual(dados['acompanhamento']['meta'], sum(p['meta'] for p in encerrados))
                self.assertAlmostEqual(dados['acompanhamento']['saldo'],
                                       sum(p['produzido'] - p['meta'] for p in encerrados))
                if pendente:
                    self.assertIsNone(periodo['saldo'])
                    self.assertIsNone(periodo['eficiencia'])
                else:
                    self.assertEqual(periodo['saldo'], -periodo['meta'])
                    self.assertEqual(periodo['eficiencia'], 0)
                futuro = self.client.get('/api/painel-producao?data=2026-10-06').json
                self.assertTrue(all(p['pendente'] for p in futuro['periodos']))
                self.assertEqual(futuro['acompanhamento']['saldo'], 0)
                self.assertIsNone(futuro['acompanhamento']['eficiencia'])
        with patch('painel_tv.datetime') as clock:
            clock.now.return_value = datetime.fromisoformat('2026-10-07T07:00:00-03:00')
            historico = self.client.get('/api/painel-producao?data=2026-10-05').json
            self.assertTrue(all(not p['pendente'] for p in historico['periodos']))
            self.assertEqual(historico['meta_dia']['quantidade'], dados['meta_dia']['quantidade'])

    def test_daily_actual_and_forecast_ignore_future_reports_from_screenshot(self):
        self.login(1)
        self.salvar()
        self.c.execute('DELETE FROM producao WHERE fabrica_id=1')
        pontos = [('08:00',120),('09:00',260),('10:00',120),('11:00',120),('12:00',60),
                  ('16:00',120),('17:00',120),('18:00',145)]
        self.c.executemany('INSERT INTO producao(fabrica_id,op_id,data,hora,qtd_produzida) VALUES(1,1,?,?,?)',
                           [('2026-10-05',hora,qtd) for hora,qtd in pontos])
        self.c.commit()
        with patch('painel_tv.datetime') as clock:
            clock.now.return_value = datetime.fromisoformat('2026-10-05T14:22:31-03:00')
            dados = self.client.get('/api/painel-producao?data=2026-10-05').json
            self.assertEqual(dados['resumo']['produzido'], 1065)
            self.assertEqual(dados['acompanhamento']['produzido'], 680)
            self.assertEqual(dados['meta_dia']['atingimento'], round(680/dados['meta_dia']['quantidade']*100,1))
            clock.now.return_value = datetime.fromisoformat('2026-10-05T18:00:00-03:00')
            encerrado = self.client.get('/api/painel-producao?data=2026-10-05').json
            self.assertEqual(encerrado['acompanhamento']['produzido'], 1065)
            clock.now.return_value = datetime.fromisoformat('2026-10-05T14:22:31-03:00')
            self.c.execute("DELETE FROM producao WHERE hora IN ('16:00','17:00','18:00')")
            self.c.commit()
            sem_futuros = self.client.get('/api/painel-producao?data=2026-10-05').json
            self.assertEqual(dados['previsao_dia'], sem_futuros['previsao_dia'])
        with patch('painel_tv.datetime') as clock:
            clock.now.return_value = datetime.fromisoformat('2026-10-06T08:00:00-03:00')
            historico = self.client.get('/api/painel-producao?data=2026-10-05').json
            self.assertEqual(historico['acompanhamento']['produzido'], 680)

    def test_period_source_explains_sum_across_ops_and_original_minutes(self):
        self.login(1)
        self.salvar()
        self.c.execute('DELETE FROM producao WHERE fabrica_id=1')
        self.c.executemany('INSERT INTO producao(fabrica_id,op_id,data,hora,qtd_produzida) VALUES(1,?,?,?,?)',
                           [(1,'2026-10-05','09:00',120),(2,'2026-10-05','08:30',140)])
        self.c.commit()
        dados = self.client.get('/api/painel-producao?data=2026-10-05').json
        nove = next(p for p in dados['periodos'] if p['hora']=='09:00')
        self.assertEqual(nove['produzido'],260)
        self.assertEqual({(a['op_id'],a['hora'],a['quantidade']) for a in nove['apontamentos']},
                         {(1,'09:00',120),(2,'08:30',140)})
        registros = self.client.get('/api/lancamentos?op_id=1&data=2026-10-05').json
        self.assertEqual(sum(r['qtd_produzida'] for r in registros),120)
        self.assertEqual(sum(a['quantidade'] for a in nove['apontamentos']),nove['produzido'])

    def test_previsao_por_lancamento_preserva_meta_e_recalcula_seguinte(self):
        self.login(1)
        self.salvar()
        self.salvar(op_id=2)
        self.c.execute("DELETE FROM producao WHERE fabrica_id=1")
        self.c.execute("INSERT INTO producao(fabrica_id,op_id,data,hora,qtd_produzida) VALUES(1,1,'2026-10-05','11:00',50)")
        self.c.commit()
        fila = calcular_fila(self.c, planos_fila(self.c, 1))
        original = metas_programadas(self.c, fila)
        agora = datetime.fromisoformat('2026-10-05T11:01:00-03:00')
        revisao = atualizar_previsoes(self.c, fila, agora)
        self.assertEqual(revisao[0]['restante'], 1950)
        self.assertGreater(revisao[0]['resultado']['saida'], fila[0]['resultado']['saida'])
        self.assertEqual(revisao[1]['resultado']['entrada'], revisao[0]['resultado']['fim_entrada'])
        self.assertEqual(metas_programadas(self.c, fila), original)
        self.assertAlmostEqual(sum(d['meta'] for d in metas_programadas(self.c, revisao).values()), 2450)
        with patch('painel_tv.datetime') as clock:
            clock.now.return_value = agora
            dados = self.client.get('/api/painel-producao?data=2026-10-05').json
        self.assertEqual(dados['meta_dia']['quantidade'], original['2026-10-05']['meta'])
        self.assertLess(dados['previsao_dia']['quantidade'], dados['meta_dia']['quantidade'])
        # Editar ou excluir apontamento muda a previsão sem mexer no plano.
        self.c.execute('UPDATE producao SET qtd_produzida=200 WHERE fabrica_id=1')
        self.c.commit()
        adiantada = atualizar_previsoes(self.c, fila, agora)
        self.assertLess(adiantada[0]['resultado']['saida'], fila[0]['resultado']['saida'])
        self.c.execute('DELETE FROM producao WHERE fabrica_id=1')
        self.c.commit()
        sem_pontos = atualizar_previsoes(self.c, fila, agora)
        self.assertEqual(sem_pontos[0]['resultado'], fila[0]['resultado'])

    def test_previsao_ignora_periodo_futuro_e_outra_fabrica(self):
        self.login(1)
        self.salvar()
        self.c.execute("DELETE FROM producao WHERE fabrica_id=1")
        self.c.execute("INSERT INTO producao(fabrica_id,op_id,data,hora,qtd_produzida) VALUES(1,1,'2026-10-05','11:30',100)")
        self.c.execute("INSERT INTO producao(fabrica_id,op_id,data,hora,qtd_produzida) VALUES(2,1,'2026-10-05','10:00',999)")
        self.c.commit()
        fila = calcular_fila(self.c, planos_fila(self.c, 1))
        antes = atualizar_previsoes(self.c, fila, datetime.fromisoformat('2026-10-05T11:59:59-03:00'))
        self.assertEqual(antes[0]['produzido'], 0)
        depois = atualizar_previsoes(self.c, fila, datetime.fromisoformat('2026-10-05T12:00:00-03:00'))
        self.assertEqual(depois[0]['produzido'], 100)

    def test_importacao_preserva_ordem_e_planos(self):
        self.login(1)
        self.salvar()
        self.salvar(op_id=2)
        antes=[dict(r) for r in self.c.execute('SELECT * FROM planejamento_metas_op ORDER BY op_id')]
        self.c.execute('DELETE FROM sequencia_metas_op')
        importar_planejamentos(self.c)
        importar_planejamentos(self.c)
        self.assertEqual(len(planos_fila(self.c,1)),2)
        self.assertEqual([dict(r) for r in self.c.execute('SELECT * FROM planejamento_metas_op ORDER BY op_id')],antes)
        self.c.commit()

    def test_previa_nao_salva_e_fila_isolada(self):
        self.login(1)
        self.salvar()
        r=self.client.post('/api/metas-op',json=dict(self.d,op_id=2))
        self.assertEqual(len(r.json['fila']),2)
        self.assertEqual(len(self.client.get('/api/metas-op/fila').json['fila']),1)
        self.login(2)
        self.assertEqual(self.client.get('/api/metas-op/fila').json['fila'],[])
        self.login(1)
        r=self.client.post('/api/metas-op',json=dict(self.d,salvar=True,ciclo='0'))
        self.assertEqual(r.status_code,400)
        self.assertEqual(self.client.get('/api/metas-op/fila').json['fila'][0]['plano']['ciclo'],15)

    def test_atravessamento_sem_meta_nao_divide_por_zero(self):
        self.login(1)
        self.c.execute('UPDATE ordens_producao SET quantidade_total=1 WHERE id=1')
        self.c.commit()
        self.salvar(data='2026-11-02',inicio='2026-11-02T07:00',times='50',ciclo='15')
        r=self.client.get('/api/painel-producao?data=2026-11-02')
        self.assertEqual(r.status_code,200,r.json)
        self.assertEqual(r.json['meta_dia']['quantidade'],0)
        self.assertIsNone(r.json['mes']['eficiencia'])
        self.assertEqual(len(r.json['periodos']),10)
        self.assertTrue(all(p['meta']==0 for p in r.json['periodos']))
        dias=metas_programadas(self.c,calcular_fila(self.c,planos_fila(self.c,1)))
        self.assertAlmostEqual(sum(d['meta'] for d in dias.values()),1)

if __name__=='__main__':
    import sys
    if '--serve' in sys.argv:
        from flask import session, redirect
        fixture=MetasTest()
        fixture.setUp()
        @application.app.get('/test-login')
        def test_login():
            session['uid']=1
            session['perfil']='gestor'
            return redirect('/metas-op')
        application.app.run(host='127.0.0.1',port=5052,use_reloader=False,debug=False)
    else:
        unittest.main()
