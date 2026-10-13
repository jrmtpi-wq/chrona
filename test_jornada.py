import unittest
from datetime import date
from test_painel_tv import application, connect, seed
from metas_op import intervalos


class JornadaTest(unittest.TestCase):
    def setUp(self):
        seed()
        self.c = connect()
        self.c.execute('DELETE FROM jornada_calendario')
        self.c.execute('DELETE FROM turnos')
        self.c.execute('''INSERT INTO turnos(id,fabrica_id,nome,hora_entrada,hora_saida_almoco,
                          hora_entrada_almoco,hora_saida,hora_saida_sexta,minutos_normal,minutos_sexta)
                          VALUES(1,1,'Dia','07:00','12:00','13:00','17:00','16:00',540,480)''')
        self.c.commit()
        self.turno = dict(self.c.execute('SELECT * FROM turnos WHERE id=1').fetchone())
        self.client = application.app.test_client()
        with self.client.session_transaction() as s:
            s['uid'] = 1

    def tearDown(self):
        self.c.close()

    def gerar(self, **extras):
        return self.client.post('/api/jornada/gerar', json=dict(mes='2026-10', turno_id=1, fabrica_id=1, **extras))

    def test_feriado_e_sabados_escolhidos(self):
        self.assertEqual(self.gerar(feriados='12', sabados_trabalhados='3, 17').status_code, 200)
        rows = self.c.execute('SELECT * FROM jornada_calendario ORDER BY data').fetchall()
        self.assertEqual(sum(r['minutos_disponiveis'] > 0 for r in rows), 23)
        self.assertEqual([r['data'] for r in rows if r['tipo'] == 'SABADO'], ['2026-10-03', '2026-10-17'])
        self.assertEqual(intervalos(self.c, self.turno, date(2026, 10, 12)), [])
        self.assertTrue(intervalos(self.c, self.turno, date(2026, 10, 17)))
        self.assertEqual(intervalos(self.c, self.turno, date(2026, 10, 10)), [])

    def test_corrige_mes_existente_sem_duplicar(self):
        self.gerar()
        registro = self.c.execute("SELECT * FROM jornada_calendario WHERE data='2026-10-12'").fetchone()
        self.gerar(feriados='12')
        novo = self.c.execute('SELECT * FROM jornada_calendario WHERE id=?', (registro['id'],)).fetchone()
        self.assertEqual((novo['tipo'], novo['minutos_disponiveis']), ('FERIADO', 0))
        self.assertEqual(self.gerar(feriados='12').json['inseridos'], 0)
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM jornada_calendario').fetchone()[0], 22)

    def test_validacao_nao_grava_parcialmente(self):
        for extras in [dict(feriados='32'), dict(sabados_trabalhados='12'), dict(feriados='abc')]:
            self.assertEqual(self.gerar(**extras).status_code, 400)
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM jornada_calendario').fetchone()[0], 0)

    def test_folga_e_reativacao_sabado(self):
        self.gerar(sabados_trabalhados='17')
        row = dict(self.c.execute("SELECT * FROM jornada_calendario WHERE data='2026-10-17'").fetchone())
        response = self.client.post('/api/jornada/salvar', json=dict(row, tipo='FOLGA', minutos_disponiveis=540, hora_extra=1))
        self.assertTrue(response.json['ok'])
        row = dict(self.c.execute('SELECT * FROM jornada_calendario WHERE id=?', (row['id'],)).fetchone())
        self.assertEqual((row['minutos_disponiveis'], row['hora_extra']), (0, 0))
        self.assertEqual(intervalos(self.c, self.turno, date(2026, 10, 17)), [])
        self.gerar()
        self.assertEqual(self.c.execute('SELECT tipo FROM jornada_calendario WHERE id=?', (row['id'],)).fetchone()[0], 'FOLGA')
        self.gerar(sabados_trabalhados='17')
        self.assertTrue(intervalos(self.c, self.turno, date(2026, 10, 17)))

    def test_feriado_prevalece_sobre_sabado(self):
        self.gerar(feriados='17', sabados_trabalhados='17', include_sabado=True)
        self.assertEqual(intervalos(self.c, self.turno, date(2026, 10, 17)), [])

    def test_turno_de_outra_fabrica_bloqueado(self):
        with self.client.session_transaction() as s:
            s['uid'] = 2
        self.assertEqual(self.gerar(feriados='12').status_code, 403)

    def test_salva_feriado_sem_substituir_id(self):
        self.gerar()
        row = dict(self.c.execute("SELECT * FROM jornada_calendario WHERE data='2026-10-12'").fetchone())
        original = row.pop('id')
        self.assertTrue(self.client.post('/api/jornada/salvar', json=dict(row, tipo='FERIADO')).json['ok'])
        saved = self.c.execute('SELECT * FROM jornada_calendario WHERE id=?', (original,)).fetchone()
        self.assertEqual((saved['tipo'], saved['minutos_disponiveis']), ('FERIADO', 0))


if __name__ == '__main__':
    unittest.main()
