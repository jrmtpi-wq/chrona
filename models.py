import sqlite3, os, hashlib
from datetime import date

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'chrona.db')

def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    return c

def init():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    c = conn()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS fabricas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        cidade TEXT,
        endereco TEXT,
        ativa INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        login TEXT NOT NULL UNIQUE,
        senha_hash TEXT NOT NULL,
        perfil TEXT DEFAULT 'operador',
        fabrica_id INTEGER,
        ativo INTEGER DEFAULT 1,
        FOREIGN KEY(fabrica_id) REFERENCES fabricas(id)
    );

    CREATE TABLE IF NOT EXISTS funcoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL UNIQUE,
        descricao TEXT,
        salario_base REAL DEFAULT 0,
        ativa INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS funcionarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fabrica_id INTEGER NOT NULL,
        funcao_id INTEGER,
        nome TEXT NOT NULL,
        cpf TEXT,
        rg TEXT,
        sexo TEXT,
        data_nascimento TEXT,
        telefone TEXT,
        celular TEXT,
        email TEXT,
        endereco TEXT,
        numero TEXT,
        bairro TEXT,
        cidade TEXT,
        estado TEXT,
        cep TEXT,
        data_admissao TEXT,
        data_demissao TEXT,
        salario REAL DEFAULT 0,
        situacao TEXT DEFAULT 'ATIVO',
        observacao TEXT,
        foto TEXT,
        criado_em TEXT DEFAULT (datetime('now','localtime')),
        FOREIGN KEY(fabrica_id) REFERENCES fabricas(id),
        FOREIGN KEY(funcao_id) REFERENCES funcoes(id)
    );

    CREATE TABLE IF NOT EXISTS equipamentos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fabrica_id INTEGER,
        nome TEXT NOT NULL,
        marca TEXT,
        modelo TEXT,
        numero_serie TEXT,
        data_aquisicao TEXT,
        valor REAL DEFAULT 0,
        situacao TEXT DEFAULT 'ATIVO',
        observacao TEXT,
        FOREIGN KEY(fabrica_id) REFERENCES fabricas(id)
    );

    CREATE TABLE IF NOT EXISTS generos_produto (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL UNIQUE
    );

    CREATE TABLE IF NOT EXISTS tipos_produto (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL UNIQUE,
        genero_id INTEGER,
        FOREIGN KEY(genero_id) REFERENCES generos_produto(id)
    );

    CREATE TABLE IF NOT EXISTS turnos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fabrica_id INTEGER,
        nome TEXT NOT NULL,
        numero INTEGER DEFAULT 1,
        hora_entrada TEXT NOT NULL,
        hora_saida_almoco TEXT,
        hora_entrada_almoco TEXT,
        hora_saida TEXT NOT NULL,
        hora_saida_sexta TEXT,
        tem_almoco INTEGER DEFAULT 1,
        minutos_normal INTEGER DEFAULT 0,
        minutos_sexta INTEGER DEFAULT 0,
        max_hora_extra_dia REAL DEFAULT 1.0,
        ativo INTEGER DEFAULT 1,
        obs TEXT,
        FOREIGN KEY(fabrica_id) REFERENCES fabricas(id)
    );

    CREATE TABLE IF NOT EXISTS jornada_calendario (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fabrica_id INTEGER,
        turno_id INTEGER,
        data TEXT NOT NULL,
        dia_semana TEXT,
        tipo TEXT DEFAULT 'NORMAL',
        hora_entrada TEXT,
        hora_saida_almoco TEXT,
        hora_entrada_almoco TEXT,
        hora_saida TEXT,
        minutos_disponiveis INTEGER DEFAULT 0,
        hora_extra INTEGER DEFAULT 0,
        obs TEXT,
        UNIQUE(fabrica_id, data, turno_id),
        FOREIGN KEY(fabrica_id) REFERENCES fabricas(id),
        FOREIGN KEY(turno_id) REFERENCES turnos(id)
    );

    CREATE TABLE IF NOT EXISTS ponto (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        funcionario_id INTEGER NOT NULL,
        data TEXT NOT NULL,
        hora_entrada TEXT,
        hora_saida_almoco TEXT,
        hora_entrada_almoco TEXT,
        hora_saida TEXT,
        minutos_trabalhados INTEGER DEFAULT 0,
        horas_extras REAL DEFAULT 0,
        tipo TEXT DEFAULT 'NORMAL',
        obs TEXT,
        FOREIGN KEY(funcionario_id) REFERENCES funcionarios(id)
    );

    CREATE TABLE IF NOT EXISTS faltas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        funcionario_id INTEGER NOT NULL,
        data TEXT NOT NULL,
        tipo TEXT NOT NULL,
        obs TEXT,
        FOREIGN KEY(funcionario_id) REFERENCES funcionarios(id)
    );

    CREATE TABLE IF NOT EXISTS categorias_despesa (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL UNIQUE,
        ordem INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS despesas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fabrica_id INTEGER,
        categoria_id INTEGER,
        mes TEXT NOT NULL,
        valor REAL DEFAULT 0,
        obs TEXT,
        FOREIGN KEY(fabrica_id) REFERENCES fabricas(id),
        FOREIGN KEY(categoria_id) REFERENCES categorias_despesa(id)
    );

    CREATE TABLE IF NOT EXISTS referencias (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        codigo TEXT NOT NULL,
        descricao TEXT,
        genero_id INTEGER,
        tipo_produto_id INTEGER,
        ativo INTEGER DEFAULT 1,
        FOREIGN KEY(genero_id) REFERENCES generos_produto(id),
        FOREIGN KEY(tipo_produto_id) REFERENCES tipos_produto(id)
    );

    CREATE TABLE IF NOT EXISTS ordens_producao (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        numero TEXT NOT NULL,
        fabrica_id INTEGER,
        referencia_id INTEGER,
        descricao TEXT,
        quantidade_total INTEGER DEFAULT 0,
        valor_unitario REAL DEFAULT 0,
        valor_total REAL DEFAULT 0,
        data_entrada TEXT,
        data_entrega TEXT,
        situacao TEXT DEFAULT 'ABERTA',
        obs TEXT,
        FOREIGN KEY(fabrica_id) REFERENCES fabricas(id),
        FOREIGN KEY(referencia_id) REFERENCES referencias(id)
    );

    CREATE TABLE IF NOT EXISTS operacoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        codigo INTEGER,
        descricao TEXT NOT NULL,
        equipamento_id INTEGER,
        tempo_padrao REAL DEFAULT 0,
        tipo TEXT DEFAULT 'C',
        ativo INTEGER DEFAULT 1,
        FOREIGN KEY(equipamento_id) REFERENCES equipamentos(id)
    );

    CREATE TABLE IF NOT EXISTS sequencia_op (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        op_id INTEGER NOT NULL,
        operacao_id INTEGER NOT NULL,
        ordem INTEGER DEFAULT 0,
        equipamento_id INTEGER,
        funcionario_id INTEGER,
        tempo_padrao REAL DEFAULT 0,
        valor_rateado REAL DEFAULT 0,
        time_numero INTEGER DEFAULT 1,
        FOREIGN KEY(op_id) REFERENCES ordens_producao(id),
        FOREIGN KEY(operacao_id) REFERENCES operacoes(id),
        FOREIGN KEY(equipamento_id) REFERENCES equipamentos(id),
        FOREIGN KEY(funcionario_id) REFERENCES funcionarios(id)
    );

    CREATE TABLE IF NOT EXISTS balanceamento (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        op_id INTEGER NOT NULL,
        fabrica_id INTEGER,
        ciclo_minutos INTEGER DEFAULT 15,
        total_operadores INTEGER DEFAULT 0,
        minutos_disponiveis INTEGER DEFAULT 540,
        meta_dia INTEGER DEFAULT 0,
        meta_ciclo REAL DEFAULT 0,
        total_times INTEGER DEFAULT 0,
        criado_em TEXT DEFAULT (datetime('now','localtime')),
        FOREIGN KEY(op_id) REFERENCES ordens_producao(id)
    );

    CREATE TABLE IF NOT EXISTS producao (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fabrica_id INTEGER,
        op_id INTEGER,
        data TEXT NOT NULL,
        hora TEXT NOT NULL,
        ciclo_minutos INTEGER DEFAULT 60,
        operadores INTEGER DEFAULT 0,
        qtd_produzida INTEGER DEFAULT 0,
        qtd_projetada REAL DEFAULT 0,
        eficiencia REAL DEFAULT 0,
        faturamento_hora REAL DEFAULT 0,
        custo_hora REAL DEFAULT 0,
        resultado_hora REAL DEFAULT 0,
        obs TEXT,
        criado_em TEXT DEFAULT (datetime('now','localtime')),
        FOREIGN KEY(fabrica_id) REFERENCES fabricas(id),
        FOREIGN KEY(op_id) REFERENCES ordens_producao(id)
    );

    CREATE TABLE IF NOT EXISTS faturamento (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fabrica_id INTEGER,
        op_id INTEGER,
        data TEXT NOT NULL,
        quantidade INTEGER DEFAULT 0,
        valor_unitario REAL DEFAULT 0,
        valor_total REAL DEFAULT 0,
        obs TEXT,
        FOREIGN KEY(fabrica_id) REFERENCES fabricas(id),
        FOREIGN KEY(op_id) REFERENCES ordens_producao(id)
    );
    """)
    c.commit()
    c.close()

def hash_senha(s):
    return hashlib.sha256(s.encode()).hexdigest()

DESPESAS_PADRAO = [
    'AGUA','ENERGIA','INTERNET','LABORATORIO','CELULAR','CAIXINHA',
    'MANUTENCAO MAQUINAS PECAS','MANUTENCAO PATRIMONIO','SEGURO',
    'MAT. LIMPEZA','MAT ESCRITORIO','CONTABILIDADE','ALUGUEL','DEPRECIACAO',
    'GESTAO CLICK','PROGRAMA ISMAEL','ALARME','MEDICO','EVENTOS/BRINDES',
    'DEDETIZACAO','ADVOGADO','ALUGUEL CASA','ACII','TERCEIROS',
    'ALVARA FUNCIONAMENTO','IPTU','LICENCAS/TAXAS BANCO/MULTAS/ICMS',
    'TARIFAS BANCO','PROJETOS/AUDITORIA','FOLHA LIQUIDA','CARTAO IFOOD',
    'RECRUTA','PAGAMENTO RESCISAO','PREVISAO FOLHA 13','PREVISAO FERIAS',
    'PREVISAO 1/3','INDENIZACOES','SINDICATO','TRANSPORTE',
    'FGTS + FGTS RESCISAO','IRRF','GPS / IMPOSTO DE RENDA','SIMPLES'
]

def seed():
    c = conn()
    # Fabricas
    if c.execute("SELECT COUNT(*) FROM fabricas").fetchone()[0] == 0:
        for i, nome in enumerate(['CHRONA 1','CHRONA 2','CHRONA 3','CHRONA 4'], 1):
            c.execute("INSERT INTO fabricas (nome,cidade) VALUES (?,?)", (nome,'Icara'))
        # Admin
        c.execute("INSERT OR IGNORE INTO usuarios (nome,login,senha_hash,perfil) VALUES (?,?,?,?)",
                  ('Administrador','admin',hash_senha('admin123'),'admin'))
        for i in range(1,5):
            c.execute("INSERT OR IGNORE INTO usuarios (nome,login,senha_hash,perfil,fabrica_id) VALUES (?,?,?,?,?)",
                      (f'Operador {i}',f'fabrica{i}',hash_senha('chrona123'),'operador',i))
    # Despesas
    if c.execute("SELECT COUNT(*) FROM categorias_despesa").fetchone()[0] == 0:
        for i,nome in enumerate(DESPESAS_PADRAO):
            c.execute("INSERT OR IGNORE INTO categorias_despesa (nome,ordem) VALUES (?,?)",(nome,i))
    # Generos produto
    if c.execute("SELECT COUNT(*) FROM generos_produto").fetchone()[0] == 0:
        for g in ['FEMININO','MASCULINO','INFANTIL','ADULTO']:
            c.execute("INSERT OR IGNORE INTO generos_produto (nome) VALUES (?)",(g,))
    # Tipos produto
    if c.execute("SELECT COUNT(*) FROM tipos_produto").fetchone()[0] == 0:
        for t in ['SHORTS','CALCA','LEG','VESTIDO','BLUSA','CAMISETA','SAIA','MACACAO']:
            c.execute("INSERT OR IGNORE INTO tipos_produto (nome) VALUES (?)",(t,))
    # Funcoes basicas
    if c.execute("SELECT COUNT(*) FROM funcoes").fetchone()[0] == 0:
        for f in ['COSTUREIRA','CORTADOR(A)','REVISORA','AUXILIAR',
                  'ENCARREGADO(A)','SUPERVISOR(A)','GERENTE']:
            c.execute("INSERT OR IGNORE INTO funcoes (nome) VALUES (?)",(f,))
    c.commit()
    c.close()

# Calculos
def hm(s):
    try: h,m=s.split(':'); return int(h)*60+int(m)
    except: return 0

def mh(m):
    return f"{int(m)//60:02d}:{int(m)%60:02d}"

def calcular_minutos(he,hsa,hea,hs):
    return max(0,(hm(hsa)-hm(he))+(hm(hs)-hm(hea)))

def calcular_meta(minutos, tempo_padrao, operadores):
    if tempo_padrao <= 0: return 0
    return (minutos / tempo_padrao) * operadores

def calcular_meta_ciclo(meta_dia, minutos_dia, ciclo):
    if ciclo <= 0 or minutos_dia <= 0: return 0
    num_ciclos = minutos_dia / ciclo
    return meta_dia / num_ciclos if num_ciclos > 0 else 0

def efic_classe(ef):
    if not ef or ef == 0: return 'neutro'
    if ef < 85: return 'vermelho'
    if ef < 90: return 'amarelo'
    if ef <= 100: return 'verde'
    return 'azul'

init()
seed()
