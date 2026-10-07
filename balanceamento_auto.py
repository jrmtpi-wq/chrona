"""Geração e validação do balanceamento, sem alterar dados da produção."""
import math


def numero(valor, nome, minimo=0):
    try:
        valor = float(valor)
    except (TypeError, ValueError):
        raise ValueError(f'{nome} inválido')
    if not math.isfinite(valor) or valor < minimo:
        raise ValueError(f'{nome} inválido')
    return valor


def gerar(seq, pessoas, habilidades, equipamentos, ciclo, meta, n_times):
    """Heurística sequencial: duplas fixas, carga global e apoio a distância <= 2.

    Uma geração sem cobertura não substitui a montagem atual. Falha da
    heurística não é prova matemática de inviabilidade da meta.
    """
    ciclo = numero(ciclo, 'Ciclo', 1)
    if not ciclo.is_integer():
        raise ValueError('O ciclo deve ser informado em minutos inteiros')
    limite = ciclo + 1
    meta = numero(meta, 'Meta por ciclo', 1)
    if not meta.is_integer():
        raise ValueError('A meta por ciclo deve ser um número inteiro de peças')
    meta = int(meta)
    if n_times < 1 or n_times > 100:
        raise ValueError('Informe entre 1 e 100 times')
    if len(pessoas) < n_times * 2:
        raise ValueError(f'São necessárias {n_times * 2} operadoras ativas para formar {n_times} duplas neste grupo')
    pessoas = {p['id']: p for p in pessoas}
    times = [{'num': i + 1, 'ops': [], 'operadoras': []} for i in range(n_times)]
    principais, cargas = {}, {}
    alertas = []

    def principal(fid, tn):
        principais[fid] = tn
        return slot(fid, tn)

    def slot(fid, tn):
        time = times[tn - 1]
        existente = next((o for o in time['operadoras'] if o['id'] == fid), None)
        if existente is None:
            existente = dict(id=fid, nome=pessoas[fid]['nome'], apoio=principais[fid] != tn,
                             time_principal=principais[fid], atribuicoes=[], carga=0)
            time['operadoras'].append(existente)
        return existente

    def vaga_principal(tn):
        # A dupla do próprio time tem preferência; apoios anteriores e seguintes
        # usam a mesma capacidade global da pessoa.
        proximos = sorted(range(1, n_times + 1), key=lambda n: (abs(n - tn), n))
        return next((n for n in proximos if abs(n - tn) <= 2
                     and sum(v == n for v in principais.values()) < 2), None)

    tn = 1
    for idx, op in enumerate(seq):
        candidatos = [h for h in habilidades.get(op['operacao_id'], []) if h['func_id'] in pessoas]
        fallback = not candidatos
        if fallback:
            equipamento = op.get('op_equip_id')
            candidatos = [dict(h, tempo=op['tempo_padrao'])
                          for h in (equipamentos.get(equipamento, []) if equipamento else []) if h['func_id'] in pessoas]
        if not candidatos:
            raise ValueError(f"{op['descricao']}: nenhuma operadora do grupo tem treinamento ou equipamento compatível")
        candidatos = [dict(h, tempo=numero(h['tempo'], 'Tempo da operação', 0.000001)) for h in candidatos]
        restante = meta
        partes = []
        while restante:
            validos = []
            for h in candidatos:
                fid = h['func_id']
                pt = principais.get(fid)
                if pt is None:
                    pt = vaga_principal(tn)
                if pt is None or abs(pt - tn) > 2:
                    continue
                capacidade = math.floor((limite - cargas.get(fid, 0) + 1e-8) / h['tempo'])
                if capacidade > 0:
                    validos.append((h['tempo'], abs(pt - tn), fid, pt, capacidade, h))
            if not validos:
                tn += 1
                if tn > n_times:
                    raise ValueError(f"Não foi encontrada uma montagem completa: faltam {restante} peças/ciclo de {op['descricao']}. Confira duplas, banco de tempos ou reduza a meta por ciclo.")
                continue
            _, _, fid, pt, capacidade, h = min(validos, key=lambda v: v[:3])
            if fid not in principais:
                principal(fid, pt)
            quantidade = min(restante, capacidade)
            carga = h['tempo'] * quantidade
            atribuicao = dict(op_idx=idx, operacao_id=op['operacao_id'], sequencia_id=op['id'],
                              descricao=op['descricao'], tempo_padrao=h['tempo'], qtd=quantidade, carga=carga)
            oper = slot(fid, tn)
            oper['atribuicoes'].append(atribuicao)
            oper['carga'] += carga
            cargas[fid] = cargas.get(fid, 0) + carga
            parte = dict(atribuicao, idx=idx + 1, equipamento_id=op.get('op_equip_id'),
                         operadora_id=fid, operadora_nome=pessoas[fid]['nome'], apoio=pt != tn,
                         alerta='sem_treino' if fallback else None, dividida=False)
            times[tn - 1]['ops'].append(parte)
            partes.append(parte)
            restante -= quantidade
        if len(partes) > 1:
            for parte in partes:
                parte['dividida'] = True
        if fallback:
            alertas.append(f"{op['descricao']}: atribuída por equipamento compatível; confira o treinamento antes de executar.")

    livres = iter(p for fid, p in pessoas.items() if fid not in principais)
    for time in times:
        while sum(v == time['num'] for v in principais.values()) < 2:
            principal(next(livres)['id'], time['num'])
        time['operadoras'].sort(key=lambda o: (o['apoio'], o['id']))
        time['carga_total'] = sum(op['carga'] for op in time['ops'])
        # Uma linha por item do roteiro no time; as partes por pessoa ficam
        # nas atribuições, inclusive quando usam tempos individuais diferentes.
        agrupadas = {}
        for op in time['ops']:
            if op['op_idx'] not in agrupadas:
                agrupadas[op['op_idx']] = dict(op)
            else:
                linha = agrupadas[op['op_idx']]
                linha['qtd'] += op['qtd']
                linha['carga'] += op['carga']
                linha['operadora_nome'] = 'Distribuída entre operadoras'
                linha['operadora_id'] = None
        time['ops'] = list(agrupadas.values())
    return dict(ok=True, times=times, alertas=alertas, limite_por_operadora=limite)


def validar(d, seq, pessoas):
    """Validação repetida no servidor: não confiar na capacidade exibida na tela."""
    ciclo = numero(d.get('ciclo_minutos'), 'Ciclo', 1)
    if not ciclo.is_integer():
        raise ValueError('O ciclo deve ser informado em minutos inteiros')
    limite = ciclo + 1
    meta = numero(d.get('meta_ciclo'), 'Meta por ciclo', 1)
    if not meta.is_integer():
        raise ValueError('A meta por ciclo deve ser inteira')
    times = d.get('times') or []
    if not times or len(times) != int(d.get('total_times', 0)):
        raise ValueError('A quantidade de times não corresponde à configuração')
    if int(d.get('total_operadores', 0)) != len(times) * 2:
        raise ValueError('Configure duas operadoras principais por time')
    disponiveis = {p['id'] for p in pessoas}
    principais, cargas, cobertura = {}, {}, [0.0] * len(seq)
    locais = [set() for _ in seq]
    numeros = {t['num'] for t in times}
    if numeros != set(range(1, len(times) + 1)):
        raise ValueError('Os times devem ser numerados em sequência')
    for t in times:
        dupla = [o for o in t.get('operadoras', []) if not o.get('apoio')]
        if len(dupla) != 2:
            raise ValueError(f"Time {t['num']}: selecione exatamente duas operadoras principais")
        ids = [o['id'] for o in t['operadoras']]
        if len(ids) != len(set(ids)) or not set(ids) <= disponiveis:
            raise ValueError('Operadoras repetidas, inativas ou de outra fábrica')
        for o in dupla:
            if o['id'] in principais:
                raise ValueError('Cada operadora deve pertencer a uma única dupla principal')
            principais[o['id']] = t['num']
    for t in times:
        for o in t['operadoras']:
            pt = principais.get(o['id'])
            if pt is None or abs(pt - t['num']) > 2 or bool(o.get('apoio')) != (pt != t['num']):
                raise ValueError(f"{o.get('nome', 'Operadora')}: apoio deve estar a até dois times do principal")
            o['time_principal'] = pt
            for a in o.get('atribuicoes', []):
                idx = a.get('op_idx')
                if not isinstance(idx, int) or not 0 <= idx < len(seq) or a.get('operacao_id') != seq[idx]['operacao_id']:
                    raise ValueError('A atribuição não corresponde ao roteiro desta OP')
                qtd = numero(a.get('qtd'), 'Quantidade atribuída', 1)
                if not qtd.is_integer():
                    raise ValueError('A quantidade atribuída deve ser inteira')
                tempo = numero(a.get('tempo_padrao'), 'Tempo aplicado', 0.000001)
                carga = numero(a.get('carga'), 'Carga atribuída')
                if not math.isclose(carga, qtd * tempo, abs_tol=0.001):
                    raise ValueError('Carga inconsistente com quantidade e tempo aplicado')
                cobertura[idx] += qtd
                locais[idx].add(t['num'])
                cargas[o['id']] = cargas.get(o['id'], 0) + carga
                if cargas[o['id']] > limite + 0.000001:
                    raise ValueError(f"{o.get('nome', 'Operadora')}: carga total ultrapassa {limite:g} minutos, incluindo apoios")
    if not seq or any(not math.isclose(q, meta, abs_tol=0.000001) for q in cobertura):
        raise ValueError('Complete todas as operações do roteiro, sem duplicar a meta por ciclo')
    if any(max(locais[i]) > min(locais[i + 1]) for i in range(len(seq) - 1)):
        raise ValueError('A distribuição deve respeitar a ordem das operações do roteiro')


def consolidar_operacoes(times, seq, meta):
    """O resumo salvo deriva das atribuições; não de rótulos antigos da tela."""
    for t in times:
        ops = {}
        for oper in t['operadoras']:
            for a in oper.get('atribuicoes', []):
                idx = a['op_idx']
                if idx not in ops:
                    ops[idx] = dict(idx=idx, operacao_id=seq[idx]['operacao_id'], sequencia_id=seq[idx]['id'],
                                    descricao=seq[idx]['descricao'], label=seq[idx]['descricao'],
                                    tempo_padrao=a['tempo_padrao'], qtd=0, carga=0,
                                    operadora_id=oper['id'], operadora_nome=oper['nome'], apoio=oper.get('apoio', False))
                op = ops[idx]
                if op['operadora_id'] != oper['id']:
                    op['operadora_id'] = None
                    op['operadora_nome'] = 'Distribuída entre operadoras'
                op['qtd'] += a['qtd']
                op['carga'] += a['carga']
                op['dividida'] = op['qtd'] < meta
        t['ops'] = [ops[i] for i in sorted(ops)]
