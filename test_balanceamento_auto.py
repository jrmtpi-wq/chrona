"""Regressões do automático e da gravação, exclusivamente em banco temporário."""
import copy
import unittest
from balanceamento_auto import gerar, validar, consolidar_operacoes
from test_painel_tv import application, connect, seed


def sequencia(tempos):
    return [dict(id=i, operacao_id=i, ordem=i, descricao=f'Operação {i}', tempo_padrao=t,
                 op_equip_id=None) for i, t in enumerate(tempos, 1)]


def pessoas(n):
    return [dict(id=i, nome=f'Pessoa {i}') for i in range(1, n + 1)]


def skills(seq, n):
    return {op['operacao_id']: [dict(func_id=i, tempo=op['tempo_padrao']) for i in range(1, n + 1)] for op in seq}


def payload(resultado, n_times, meta=1):
    return dict(copy.deepcopy(resultado), op_id=1, ciclo_minutos=15, total_operadores=n_times * 2,
                total_times=n_times, meta_ciclo=meta, meta_dia=meta * 36, minutos_disponiveis=540, turno_id=None)


class RegrasTests(unittest.TestCase):
    def test_duplas_capacidade_e_divisao_grande(self):
        seq = sequencia([15])
        r = gerar(seq, pessoas(4), skills(seq, 4), {}, 15, 3, 2)
        validar(payload(r, 2, 3), seq, pessoas(4))
        self.assertEqual(sum(a['qtd'] for t in r['times'] for o in t['operadoras'] for a in o['atribuicoes']), 3)
        self.assertTrue(all(len([o for o in t['operadoras'] if not o['apoio']]) == 2 for t in r['times']))
        cargas = {}
        for t in r['times']:
            for o in t['operadoras']:
                cargas[o['id']] = cargas.get(o['id'], 0) + sum(a['carga'] for a in o['atribuicoes'])
        self.assertLessEqual(max(cargas.values()), 16)

    def test_tolerancia_um_minuto_sem_reaplicar_dezoito_porcento(self):
        seq = sequencia([8, 8])
        r = gerar(seq, pessoas(2), {i: [dict(func_id=1, tempo=8)] for i in (1, 2)}, {}, 15, 1, 1)
        validar(payload(r, 1), seq, pessoas(2))
        self.assertEqual(r['times'][0]['operadoras'][0]['carga'], 16)

    def test_nao_reutiliza_capacidade_global(self):
        seq = sequencia([10, 10])
        with self.assertRaisesRegex(ValueError, 'montagem completa'):
            gerar(seq, pessoas(4), {i: [dict(func_id=1, tempo=10)] for i in (1, 2)}, {}, 15, 1, 2)

    def test_sem_pessoa_treinada_nao_retorna_sucesso(self):
        with self.assertRaisesRegex(ValueError, 'nenhuma operadora'):
            gerar(sequencia([1]), pessoas(2), {}, {}, 15, 1, 1)
        with self.assertRaisesRegex(ValueError, 'nenhuma operadora'):
            gerar(sequencia([1]), pessoas(2), {}, {None: [dict(func_id=1, tempo=1)]}, 15, 1, 1)

    def test_fallback_usa_tempo_padrao_da_operacao(self):
        seq = sequencia([8]); seq[0]['op_equip_id'] = 1
        r = gerar(seq, pessoas(2), {}, {1: [dict(func_id=1, tempo=.01)]}, 15, 1, 1)
        self.assertEqual(r['times'][0]['operadoras'][0]['atribuicoes'][0]['carga'], 8)
        self.assertTrue(r['alertas'])

    def test_falta_de_dupla(self):
        with self.assertRaisesRegex(ValueError, '2 operadoras'):
            gerar(sequencia([1]), pessoas(1), {}, {}, 15, 1, 1)

    def test_apoio_dois_times_antes_e_depois(self):
        seq = sequencia([1])
        for origem, destino in [(1, 3), (3, 1)]:
            d = dict(ciclo_minutos=15, meta_ciclo=1, total_operadores=6, total_times=3, times=[])
            for tn in range(1, 4):
                d['times'].append(dict(num=tn, ops=[], operadoras=[dict(id=i, nome=f'Pessoa {i}',
                    apoio=False, time_principal=tn, atribuicoes=[]) for i in (tn * 2 - 1, tn * 2)]))
            fid = origem * 2 - 1
            d['times'][destino - 1]['operadoras'].append(dict(id=fid, nome=f'Pessoa {fid}',
                apoio=True, time_principal=origem, atribuicoes=[dict(op_idx=0, operacao_id=1,
                    qtd=1, tempo_padrao=1, carga=1)]))
            validar(d, seq, pessoas(6))

    def test_divisao_preserva_ordem_e_limite_distancia(self):
        seq = sequencia([15])
        r = gerar(seq, pessoas(8), skills(seq, 8), {}, 15, 7, 4)
        validar(payload(r, 4, 7), seq, pessoas(8))
        self.assertGreaterEqual(sum(bool(t['ops']) for t in r['times']), 2)
        self.assertTrue(all(abs(o['time_principal'] - t['num']) <= 2
                            for t in r['times'] for o in t['operadoras']))

    def test_distancia_e_carga_validacao_servidor(self):
        seq = sequencia([1])
        r = gerar(seq, pessoas(8), skills(seq, 8), {}, 15, 1, 4)
        d = payload(r, 4)
        oper = next(o for o in d['times'][0]['operadoras'] if o['atribuicoes'])
        d['times'][3]['operadoras'].append(dict(oper, apoio=True))
        d['times'][0]['operadoras'][0]['atribuicoes'] = []
        with self.assertRaisesRegex(ValueError, 'dois times'):
            validar(d, seq, pessoas(8))
        d = payload(r, 4)
        oper = next(o for o in d['times'][0]['operadoras'] if o['atribuicoes'])
        oper['atribuicoes'][0].update(tempo_padrao=17, carga=17)
        with self.assertRaisesRegex(ValueError, 'ultrapassa 16'):
            validar(d, seq, pessoas(8))

    def test_duplicacao_cobertura_e_tempo_invalido(self):
        seq = sequencia([1]); r = gerar(seq, pessoas(2), skills(seq, 2), {}, 15, 1, 1)
        d = payload(r, 1)
        d['times'][0]['operadoras'][0]['atribuicoes'] *= 2
        with self.assertRaisesRegex(ValueError, 'duplicar'):
            validar(d, seq, pessoas(2))
        for tempo in (0, -1, float('nan'), float('inf')):
            with self.subTest(tempo=tempo), self.assertRaises(ValueError):
                gerar(seq, pessoas(2), {1: [dict(func_id=1, tempo=tempo)]}, {}, 15, 1, 1)


class RotasTests(unittest.TestCase):
    def setUp(self):
        c = connect()
        for tabela in ('balanceamento_atribuicoes', 'balanceamento_operadoras', 'balanceamento',
                       'sequencia_op', 'operacao_tempos', 'operacoes', 'funcionarios'):
            c.execute('DELETE FROM ' + tabela)
        c.commit(); c.close(); seed()
        c = connect()
        for uid, fab, status in [(1, 1, 'ATIVO'), (2, 1, 'ATIVO'), (3, 1, 'ATIVO'), (4, 1, 'ATIVO'),
                                 (5, 1, 'INATIVO'), (6, 2, 'ATIVO')]:
            c.execute('INSERT INTO funcionarios(id,fabrica_id,nome,situacao,grupo_id) VALUES(?,?,?,?,?)',
                      (uid, fab, f'Pessoa {uid}', status, 1))
        c.execute("INSERT INTO operacoes(id,descricao,tempo_padrao) VALUES(1,'Costura',15)")
        c.execute('INSERT INTO sequencia_op(op_id,operacao_id,ordem,tempo_padrao) VALUES(1,1,1,15)')
        for uid in range(1, 7):
            c.execute('INSERT INTO operacao_tempos(operacao_id,funcionario_id,tempo) VALUES(1,?,?)',
                      (uid, 15 if uid <= 4 else .01))
        c.commit(); c.close()
        self.client = application.app.test_client()
        with self.client.session_transaction() as s:
            s['uid'] = 1

    def auto(self, **changes):
        d = dict(op_id=1, ciclo=15, meta_ciclo=3, times=2, operadoras=4, grupo_id=1)
        d.update(changes)
        return self.client.post('/api/balanceamento/automatico', json=d).json

    def test_exclui_inativas_e_outra_fabrica(self):
        r = self.auto(); self.assertTrue(r['ok'], r)
        self.assertEqual({o['id'] for t in r['times'] for o in t['operadoras']}, {1, 2, 3, 4})

    def test_grupo_contagens_e_acesso(self):
        for changes in (dict(grupo_id=999), dict(times=1), dict(op_id=3), dict(ciclo='ruim')):
            with self.subTest(changes=changes):
                self.assertFalse(self.auto(**changes)['ok'])

    def test_preserva_divisoes_atribuicoes_e_parametros(self):
        r = self.auto(); self.assertTrue(r['ok'], r)
        d = payload(r, 2, 3)
        # Conversão da API para os índices zero-based usados na montagem.
        for t in d['times']:
            for op in t['ops']:
                op['idx'] -= 1
        response = self.client.post('/api/balanceamento/salvar', json=d).json
        self.assertTrue(response['ok'], response)
        bal = self.client.get('/api/balanceamento/1').json
        c = connect()
        _, seq, _ = application.dados_balanceamento(c, 1, dict(fabrica_id=1, perfil='gestor'), None)
        c.close()
        consolidar_operacoes(d['times'], seq, 3)
        self.assertEqual(bal['montagem']['times'], d['times'])
        self.assertEqual(bal['meta_ciclo'], 3)
        self.assertEqual(sum(len(o['atribuicoes']) for o in bal['operadoras_times']), 3)

    def test_salvamento_invalido_nao_substitui_anterior(self):
        r = self.auto(); d = payload(r, 2, 3)
        for t in d['times']:
            for op in t['ops']: op['idx'] -= 1
        self.assertTrue(self.client.post('/api/balanceamento/salvar', json=d).json['ok'])
        antes = self.client.get('/api/balanceamento/1').json['montagem']
        d['times'][0]['operadoras'][0]['atribuicoes'][0]['carga'] = 100
        self.assertFalse(self.client.post('/api/balanceamento/salvar', json=d).json['ok'])
        self.assertEqual(self.client.get('/api/balanceamento/1').json['montagem'], antes)

    def test_operacao_repetida_no_roteiro_tem_identidade_propria(self):
        c = connect()
        c.execute('UPDATE sequencia_op SET tempo_padrao=8 WHERE op_id=1')
        c.execute('INSERT INTO sequencia_op(op_id,operacao_id,ordem,tempo_padrao) VALUES(1,1,2,8)')
        c.execute('UPDATE operacao_tempos SET tempo=8 WHERE funcionario_id<=4')
        c.commit(); c.close()
        r = self.auto(meta_ciclo=1)
        self.assertTrue(r['ok'], r)
        d = payload(r, 2, 1)
        for t in d['times']:
            for op in t['ops']: op['idx'] -= 1
        self.assertTrue(self.client.post('/api/balanceamento/salvar', json=d).json['ok'])
        bal = self.client.get('/api/balanceamento/1').json
        atribuicoes = [a for t in bal['montagem']['times'] for o in t['operadoras'] for a in o['atribuicoes']]
        self.assertEqual({a['op_idx'] for a in atribuicoes}, {0, 1})
        self.assertEqual(len({a['sequencia_id'] for a in atribuicoes}), 2)


if __name__ == '__main__':
    unittest.main()
