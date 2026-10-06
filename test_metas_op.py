import unittest
from datetime import datetime, date
from test_painel_tv import application, seed, connect
from metas_op import calcular, intervalos


class MetasTest(unittest.TestCase):
    def setUp(self):
        c=connect()
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
        self.assertEqual(r['saida'],'2026-10-06T15:51:48')
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

if __name__=='__main__':unittest.main()
