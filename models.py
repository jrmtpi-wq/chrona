import os, hashlib
from datetime import date

DATABASE_URL = os.environ.get('DATABASE_URL')
PG_MODE = bool(DATABASE_URL)

if PG_MODE:
    import psycopg2
    import psycopg2.extras
else:
    import sqlite3
    DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'chrona.db')


class _Cursor:
    def __init__(self, cur):
        self._c = cur

    def fetchone(self):
        return self._c.fetchone()

    def fetchall(self):
        return self._c.fetchall()

    def __getitem__(self, k):
        return self._c[k]

    def __iter__(self):
        return iter(self._c)


class _Conn:
    def __init__(self, raw, pg):
        self._raw = raw
        self._pg = pg
        self.lastrowid = None

    def _prep(self, sql):
        if self._pg:
            # escape literal % (e.g. LIKE '%FERIA%') then convert ? to %s
            return sql.replace('%', '%%').replace('?', '%s')
        return sql

    def execute(self, sql, params=()):
        sql = self._prep(sql)
        cur = self._raw.cursor()
        if params:
            cur.execute(sql, list(params) if self._pg else params)
        else:
            cur.execute(sql)
        if not self._pg:
            self.lastrowid = cur.lastrowid
        return _Cursor(cur)

    def insert_id(self, sql, params=()):
        """INSERT e retorna o id gerado."""
        if self._pg:
            sql = self._prep(sql).rstrip().rstrip(';') + ' RETURNING id'
            cur = self._raw.cursor()
            cur.execute(sql, list(params))
            row = cur.fetchone()
            return row[0] if row else None
        else:
            cur = self._raw.cursor()
            cur.execute(sql, params)
            return cur.lastrowid

    def commit(self):
        self._raw.commit()

    def close(self):
        self._raw.close()


def conn():
    if PG_MODE:
        url = DATABASE_URL
        if url.startswith('postgres://'):
            url = url.replace('postgres://', 'postgresql://', 1)
        raw = psycopg2.connect(url, cursor_factory=psycopg2.extras.DictCursor)
        return _Conn(raw, True)
    else:
        os.makedirs(os.path.dirname(DB), exist_ok=True)
        raw = sqlite3.connect(DB)
        raw.row_factory = sqlite3.Row
        raw.execute("PRAGMA foreign_keys=ON")
        return _Conn(raw, False)


def _pg_exec(c, sql):
    """Executa blocos DDL linha a linha (sem executescript no PG)."""
    for stmt in sql.split(';'):
        s = stmt.strip()
        if s:
            c.execute(s)


SCHEMA_SQLITE = """
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
    bonificacao REAL DEFAULT 0,
    ifood REAL DEFAULT 0,
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
    data TEXT,
    valor REAL DEFAULT 0,
    tipo TEXT DEFAULT 'FIXA',
    numero_doc TEXT DEFAULT '',
    fornecedor TEXT DEFAULT '',
    foto TEXT,
    obs TEXT,
    FOREIGN KEY(fabrica_id) REFERENCES fabricas(id),
    FOREIGN KEY(categoria_id) REFERENCES categorias_despesa(id)
);
CREATE TABLE IF NOT EXISTS contas_pagar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fabrica_id INTEGER,
    categoria_id INTEGER,
    fornecedor TEXT,
    descricao TEXT,
    valor_total REAL DEFAULT 0,
    num_parcelas INTEGER DEFAULT 1,
    data_lancamento TEXT,
    obs TEXT,
    criado_em TEXT DEFAULT (datetime('now','localtime')),
    FOREIGN KEY(fabrica_id) REFERENCES fabricas(id),
    FOREIGN KEY(categoria_id) REFERENCES categorias_despesa(id)
);
CREATE TABLE IF NOT EXISTS contas_pagar_parcelas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conta_id INTEGER NOT NULL,
    numero INTEGER DEFAULT 1,
    valor REAL DEFAULT 0,
    data_vencimento TEXT,
    status TEXT DEFAULT 'PENDENTE',
    data_pagamento TEXT,
    foto TEXT,
    FOREIGN KEY(conta_id) REFERENCES contas_pagar(id)
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
    data_entrega_costura TEXT,
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
    modelo TEXT DEFAULT '',
    ativo INTEGER DEFAULT 1,
    FOREIGN KEY(equipamento_id) REFERENCES equipamentos(id)
);
CREATE TABLE IF NOT EXISTS operacao_tempos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operacao_id INTEGER NOT NULL,
    funcionario_id INTEGER NOT NULL,
    tempo REAL NOT NULL,
    criado_em TEXT DEFAULT (datetime('now','localtime')),
    FOREIGN KEY(operacao_id) REFERENCES operacoes(id),
    FOREIGN KEY(funcionario_id) REFERENCES funcionarios(id)
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
    numero_nf TEXT DEFAULT '',
    tipo TEXT DEFAULT 'CONCLUIDA',
    obs TEXT,
    FOREIGN KEY(fabrica_id) REFERENCES fabricas(id),
    FOREIGN KEY(op_id) REFERENCES ordens_producao(id)
);
CREATE TABLE IF NOT EXISTS ref_sequencia (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    referencia_id INTEGER NOT NULL,
    operacao_id INTEGER NOT NULL,
    ordem INTEGER DEFAULT 0,
    equipamento_id INTEGER,
    funcionario_id INTEGER,
    tempo_padrao REAL DEFAULT 0,
    FOREIGN KEY(referencia_id) REFERENCES referencias(id),
    FOREIGN KEY(operacao_id) REFERENCES operacoes(id)
);
CREATE TABLE IF NOT EXISTS sequencias_banco (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    modelo TEXT DEFAULT '',
    tempo_total REAL DEFAULT 0,
    total_ops INTEGER DEFAULT 0,
    criado_por INTEGER,
    criado_em TEXT DEFAULT (datetime('now','localtime')),
    FOREIGN KEY(criado_por) REFERENCES usuarios(id)
);
CREATE TABLE IF NOT EXISTS sequencia_banco_ops (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sequencia_id INTEGER NOT NULL,
    operacao_id INTEGER NOT NULL,
    ordem INTEGER DEFAULT 0,
    tempo_padrao REAL DEFAULT 0,
    equipamento_id INTEGER,
    FOREIGN KEY(sequencia_id) REFERENCES sequencias_banco(id),
    FOREIGN KEY(operacao_id) REFERENCES operacoes(id)
);
CREATE TABLE IF NOT EXISTS tipos_ocorrencia (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL UNIQUE,
    horas_padrao REAL DEFAULT 9,
    ativo INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS ocorrencias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    funcionario_id INTEGER NOT NULL,
    fabrica_id INTEGER,
    data TEXT NOT NULL,
    tipo_id INTEGER NOT NULL,
    horas REAL DEFAULT 0,
    direto TEXT DEFAULT 'DIRETO',
    obs TEXT,
    criado_em TEXT DEFAULT (datetime('now','localtime')),
    FOREIGN KEY(funcionario_id) REFERENCES funcionarios(id),
    FOREIGN KEY(fabrica_id) REFERENCES fabricas(id),
    FOREIGN KEY(tipo_id) REFERENCES tipos_ocorrencia(id)
);
CREATE TABLE IF NOT EXISTS notas_fiscais (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    numero TEXT,
    data TEXT,
    cliente TEXT,
    fabrica_id INTEGER,
    valor REAL DEFAULT 0,
    ops_vinculadas TEXT,
    foto TEXT,
    obs TEXT,
    FOREIGN KEY(fabrica_id) REFERENCES fabricas(id)
);
CREATE TABLE IF NOT EXISTS despesas_docs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    numero TEXT,
    data TEXT,
    fornecedor TEXT,
    categoria_id INTEGER,
    fabrica_id INTEGER,
    valor REAL DEFAULT 0,
    obs TEXT,
    FOREIGN KEY(fabrica_id) REFERENCES fabricas(id)
);
"""

SCHEMA_PG = """
CREATE TABLE IF NOT EXISTS fabricas (
    id SERIAL PRIMARY KEY,
    nome TEXT NOT NULL,
    cidade TEXT,
    endereco TEXT,
    ativa INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS usuarios (
    id SERIAL PRIMARY KEY,
    nome TEXT NOT NULL,
    login TEXT NOT NULL UNIQUE,
    senha_hash TEXT NOT NULL,
    perfil TEXT DEFAULT 'operador',
    fabrica_id INTEGER,
    ativo INTEGER DEFAULT 1,
    FOREIGN KEY(fabrica_id) REFERENCES fabricas(id)
);
CREATE TABLE IF NOT EXISTS funcoes (
    id SERIAL PRIMARY KEY,
    nome TEXT NOT NULL UNIQUE,
    descricao TEXT,
    salario_base REAL DEFAULT 0,
    ativa INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS funcionarios (
    id SERIAL PRIMARY KEY,
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
    bonificacao REAL DEFAULT 0,
    ifood REAL DEFAULT 0,
    situacao TEXT DEFAULT 'ATIVO',
    observacao TEXT,
    foto TEXT,
    criado_em TEXT DEFAULT to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'),
    FOREIGN KEY(fabrica_id) REFERENCES fabricas(id),
    FOREIGN KEY(funcao_id) REFERENCES funcoes(id)
);
CREATE TABLE IF NOT EXISTS equipamentos (
    id SERIAL PRIMARY KEY,
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
    id SERIAL PRIMARY KEY,
    nome TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS tipos_produto (
    id SERIAL PRIMARY KEY,
    nome TEXT NOT NULL UNIQUE,
    genero_id INTEGER,
    FOREIGN KEY(genero_id) REFERENCES generos_produto(id)
);
CREATE TABLE IF NOT EXISTS turnos (
    id SERIAL PRIMARY KEY,
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
    id SERIAL PRIMARY KEY,
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
    id SERIAL PRIMARY KEY,
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
    id SERIAL PRIMARY KEY,
    funcionario_id INTEGER NOT NULL,
    data TEXT NOT NULL,
    tipo TEXT NOT NULL,
    obs TEXT,
    FOREIGN KEY(funcionario_id) REFERENCES funcionarios(id)
);
CREATE TABLE IF NOT EXISTS categorias_despesa (
    id SERIAL PRIMARY KEY,
    nome TEXT NOT NULL UNIQUE,
    ordem INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS despesas (
    id SERIAL PRIMARY KEY,
    fabrica_id INTEGER,
    categoria_id INTEGER,
    mes TEXT NOT NULL,
    data TEXT,
    valor REAL DEFAULT 0,
    tipo TEXT DEFAULT 'FIXA',
    numero_doc TEXT DEFAULT '',
    fornecedor TEXT DEFAULT '',
    foto TEXT,
    obs TEXT,
    FOREIGN KEY(fabrica_id) REFERENCES fabricas(id),
    FOREIGN KEY(categoria_id) REFERENCES categorias_despesa(id)
);
CREATE TABLE IF NOT EXISTS contas_pagar (
    id SERIAL PRIMARY KEY,
    fabrica_id INTEGER,
    categoria_id INTEGER,
    fornecedor TEXT,
    descricao TEXT,
    valor_total REAL DEFAULT 0,
    num_parcelas INTEGER DEFAULT 1,
    data_lancamento TEXT,
    obs TEXT,
    criado_em TEXT DEFAULT to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'),
    FOREIGN KEY(fabrica_id) REFERENCES fabricas(id),
    FOREIGN KEY(categoria_id) REFERENCES categorias_despesa(id)
);
CREATE TABLE IF NOT EXISTS contas_pagar_parcelas (
    id SERIAL PRIMARY KEY,
    conta_id INTEGER NOT NULL,
    numero INTEGER DEFAULT 1,
    valor REAL DEFAULT 0,
    data_vencimento TEXT,
    status TEXT DEFAULT 'PENDENTE',
    data_pagamento TEXT,
    foto TEXT,
    FOREIGN KEY(conta_id) REFERENCES contas_pagar(id)
);
CREATE TABLE IF NOT EXISTS referencias (
    id SERIAL PRIMARY KEY,
    codigo TEXT NOT NULL,
    descricao TEXT,
    genero_id INTEGER,
    tipo_produto_id INTEGER,
    ativo INTEGER DEFAULT 1,
    FOREIGN KEY(genero_id) REFERENCES generos_produto(id),
    FOREIGN KEY(tipo_produto_id) REFERENCES tipos_produto(id)
);
CREATE TABLE IF NOT EXISTS ordens_producao (
    id SERIAL PRIMARY KEY,
    numero TEXT NOT NULL,
    fabrica_id INTEGER,
    referencia_id INTEGER,
    descricao TEXT,
    quantidade_total INTEGER DEFAULT 0,
    valor_unitario REAL DEFAULT 0,
    valor_total REAL DEFAULT 0,
    data_entrada TEXT,
    data_entrega TEXT,
    data_entrega_costura TEXT,
    situacao TEXT DEFAULT 'ABERTA',
    obs TEXT,
    FOREIGN KEY(fabrica_id) REFERENCES fabricas(id),
    FOREIGN KEY(referencia_id) REFERENCES referencias(id)
);
CREATE TABLE IF NOT EXISTS operacoes (
    id SERIAL PRIMARY KEY,
    codigo INTEGER,
    descricao TEXT NOT NULL,
    equipamento_id INTEGER,
    tempo_padrao REAL DEFAULT 0,
    tipo TEXT DEFAULT 'C',
    modelo TEXT DEFAULT '',
    ativo INTEGER DEFAULT 1,
    FOREIGN KEY(equipamento_id) REFERENCES equipamentos(id)
);
CREATE TABLE IF NOT EXISTS operacao_tempos (
    id SERIAL PRIMARY KEY,
    operacao_id INTEGER NOT NULL,
    funcionario_id INTEGER NOT NULL,
    tempo REAL NOT NULL,
    criado_em TEXT DEFAULT (NOW()::text),
    FOREIGN KEY(operacao_id) REFERENCES operacoes(id),
    FOREIGN KEY(funcionario_id) REFERENCES funcionarios(id)
);
CREATE TABLE IF NOT EXISTS sequencia_op (
    id SERIAL PRIMARY KEY,
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
    id SERIAL PRIMARY KEY,
    op_id INTEGER NOT NULL,
    fabrica_id INTEGER,
    ciclo_minutos INTEGER DEFAULT 15,
    total_operadores INTEGER DEFAULT 0,
    minutos_disponiveis INTEGER DEFAULT 540,
    meta_dia INTEGER DEFAULT 0,
    meta_ciclo REAL DEFAULT 0,
    total_times INTEGER DEFAULT 0,
    criado_em TEXT DEFAULT to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'),
    FOREIGN KEY(op_id) REFERENCES ordens_producao(id)
);
CREATE TABLE IF NOT EXISTS producao (
    id SERIAL PRIMARY KEY,
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
    criado_em TEXT DEFAULT to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'),
    FOREIGN KEY(fabrica_id) REFERENCES fabricas(id),
    FOREIGN KEY(op_id) REFERENCES ordens_producao(id)
);
CREATE TABLE IF NOT EXISTS faturamento (
    id SERIAL PRIMARY KEY,
    fabrica_id INTEGER,
    op_id INTEGER,
    data TEXT NOT NULL,
    quantidade INTEGER DEFAULT 0,
    valor_unitario REAL DEFAULT 0,
    valor_total REAL DEFAULT 0,
    numero_nf TEXT DEFAULT '',
    tipo TEXT DEFAULT 'CONCLUIDA',
    obs TEXT,
    FOREIGN KEY(fabrica_id) REFERENCES fabricas(id),
    FOREIGN KEY(op_id) REFERENCES ordens_producao(id)
);
CREATE TABLE IF NOT EXISTS ref_sequencia (
    id SERIAL PRIMARY KEY,
    referencia_id INTEGER NOT NULL,
    operacao_id INTEGER NOT NULL,
    ordem INTEGER DEFAULT 0,
    equipamento_id INTEGER,
    funcionario_id INTEGER,
    tempo_padrao REAL DEFAULT 0,
    FOREIGN KEY(referencia_id) REFERENCES referencias(id),
    FOREIGN KEY(operacao_id) REFERENCES operacoes(id)
);
CREATE TABLE IF NOT EXISTS sequencias_banco (
    id SERIAL PRIMARY KEY,
    nome TEXT NOT NULL,
    modelo TEXT DEFAULT '',
    tempo_total REAL DEFAULT 0,
    total_ops INTEGER DEFAULT 0,
    criado_por INTEGER,
    criado_em TEXT DEFAULT to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'),
    FOREIGN KEY(criado_por) REFERENCES usuarios(id)
);
CREATE TABLE IF NOT EXISTS sequencia_banco_ops (
    id SERIAL PRIMARY KEY,
    sequencia_id INTEGER NOT NULL,
    operacao_id INTEGER NOT NULL,
    ordem INTEGER DEFAULT 0,
    tempo_padrao REAL DEFAULT 0,
    equipamento_id INTEGER,
    FOREIGN KEY(sequencia_id) REFERENCES sequencias_banco(id),
    FOREIGN KEY(operacao_id) REFERENCES operacoes(id)
);
CREATE TABLE IF NOT EXISTS tipos_ocorrencia (
    id SERIAL PRIMARY KEY,
    nome TEXT NOT NULL UNIQUE,
    horas_padrao REAL DEFAULT 9,
    ativo INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS ocorrencias (
    id SERIAL PRIMARY KEY,
    funcionario_id INTEGER NOT NULL,
    fabrica_id INTEGER,
    data TEXT NOT NULL,
    tipo_id INTEGER NOT NULL,
    horas REAL DEFAULT 0,
    direto TEXT DEFAULT 'DIRETO',
    obs TEXT,
    criado_em TEXT DEFAULT to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'),
    FOREIGN KEY(funcionario_id) REFERENCES funcionarios(id),
    FOREIGN KEY(fabrica_id) REFERENCES fabricas(id),
    FOREIGN KEY(tipo_id) REFERENCES tipos_ocorrencia(id)
);
CREATE TABLE IF NOT EXISTS notas_fiscais (
    id SERIAL PRIMARY KEY,
    numero TEXT,
    data TEXT,
    cliente TEXT,
    fabrica_id INTEGER,
    valor REAL DEFAULT 0,
    ops_vinculadas TEXT,
    foto TEXT,
    obs TEXT,
    FOREIGN KEY(fabrica_id) REFERENCES fabricas(id)
);
CREATE TABLE IF NOT EXISTS despesas_docs (
    id SERIAL PRIMARY KEY,
    numero TEXT,
    data TEXT,
    fornecedor TEXT,
    categoria_id INTEGER,
    fabrica_id INTEGER,
    valor REAL DEFAULT 0,
    obs TEXT,
    FOREIGN KEY(fabrica_id) REFERENCES fabricas(id)
);
"""


def init():
    c = conn()
    schema = SCHEMA_PG if PG_MODE else SCHEMA_SQLITE
    _pg_exec(c, schema)
    # Migrações: adicionar colunas que podem não existir em bancos antigos
    if PG_MODE:
        try:
            c.execute("ALTER TABLE funcionarios ADD COLUMN IF NOT EXISTS bonificacao REAL DEFAULT 0")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE funcionarios ADD COLUMN IF NOT EXISTS ifood REAL DEFAULT 0")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE funcionarios ADD COLUMN IF NOT EXISTS matricula INTEGER")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE operacoes ADD COLUMN IF NOT EXISTS modelo TEXT DEFAULT ''")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE funcoes ADD COLUMN IF NOT EXISTS ativa INTEGER DEFAULT 1")
            c.execute("UPDATE funcoes SET ativa=1 WHERE ativa IS NULL")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE faturamento ADD COLUMN IF NOT EXISTS numero_nf TEXT DEFAULT ''")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE faturamento ADD COLUMN IF NOT EXISTS tipo TEXT DEFAULT 'CONCLUIDA'")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE despesas ADD COLUMN IF NOT EXISTS data TEXT")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE despesas ADD COLUMN IF NOT EXISTS tipo TEXT DEFAULT 'FIXA'")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE despesas ADD COLUMN IF NOT EXISTS numero_doc TEXT DEFAULT ''")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE despesas ADD COLUMN IF NOT EXISTS fornecedor TEXT DEFAULT ''")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE despesas ADD COLUMN IF NOT EXISTS foto TEXT")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE despesas_docs ADD COLUMN IF NOT EXISTS foto TEXT")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE notas_fiscais ADD COLUMN IF NOT EXISTS foto TEXT")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE ordens_producao ADD COLUMN IF NOT EXISTS data_entrega_costura TEXT")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE ordens_producao ADD COLUMN IF NOT EXISTS data_entrega_status TEXT DEFAULT 'verde'")
        except Exception:
            pass
        try:
            c.execute("""CREATE TABLE IF NOT EXISTS lancamentos_fila (
                id SERIAL PRIMARY KEY,
                op_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                fabrica_id INTEGER NOT NULL,
                data_hora TEXT NOT NULL,
                quantidade INTEGER DEFAULT 0,
                meta_ciclo INTEGER DEFAULT 0,
                FOREIGN KEY(op_id) REFERENCES ordens_producao(id),
                FOREIGN KEY(user_id) REFERENCES usuarios(id)
            )""")
        except Exception:
            pass
        try:
            c.execute("""CREATE TABLE IF NOT EXISTS contas_pagar (
                id SERIAL PRIMARY KEY,
                fabrica_id INTEGER,
                categoria_id INTEGER,
                fornecedor TEXT,
                descricao TEXT,
                valor_total REAL DEFAULT 0,
                num_parcelas INTEGER DEFAULT 1,
                data_lancamento TEXT,
                obs TEXT,
                criado_em TEXT DEFAULT to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'),
                FOREIGN KEY(fabrica_id) REFERENCES fabricas(id),
                FOREIGN KEY(categoria_id) REFERENCES categorias_despesa(id)
            )""")
        except Exception:
            pass
        try:
            c.execute("""CREATE TABLE IF NOT EXISTS contas_pagar_parcelas (
                id SERIAL PRIMARY KEY,
                conta_id INTEGER NOT NULL,
                numero INTEGER DEFAULT 1,
                valor REAL DEFAULT 0,
                data_vencimento TEXT,
                status TEXT DEFAULT 'PENDENTE',
                data_pagamento TEXT,
                foto TEXT,
                FOREIGN KEY(conta_id) REFERENCES contas_pagar(id)
            )""")
        except Exception:
            pass
        try:
            c.execute("""CREATE TABLE IF NOT EXISTS ref_sequencia (
                id SERIAL PRIMARY KEY,
                referencia_id INTEGER NOT NULL,
                operacao_id INTEGER NOT NULL,
                ordem INTEGER DEFAULT 0,
                equipamento_id INTEGER,
                funcionario_id INTEGER,
                tempo_padrao REAL DEFAULT 0,
                FOREIGN KEY(referencia_id) REFERENCES referencias(id),
                FOREIGN KEY(operacao_id) REFERENCES operacoes(id)
            )""")
        except Exception:
            pass
        try:
            c.execute("""CREATE TABLE IF NOT EXISTS fila_estado (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL UNIQUE,
                turno_id INTEGER,
                dt_inicio TEXT,
                minutos INTEGER DEFAULT 540,
                hora_entrada TEXT DEFAULT '07:00',
                hora_saida TEXT DEFAULT '17:30',
                fila_json TEXT DEFAULT '[]',
                atualizado TEXT
            )""")
        except Exception:
            pass
        try:
            c.execute("""CREATE TABLE IF NOT EXISTS sequencias_banco (
                id SERIAL PRIMARY KEY,
                nome TEXT NOT NULL,
                modelo TEXT DEFAULT '',
                tempo_total REAL DEFAULT 0,
                total_ops INTEGER DEFAULT 0,
                criado_por INTEGER,
                criado_em TEXT DEFAULT to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'),
                FOREIGN KEY(criado_por) REFERENCES usuarios(id)
            )""")
        except Exception:
            pass
        try:
            c.execute("""CREATE TABLE IF NOT EXISTS sequencia_banco_ops (
                id SERIAL PRIMARY KEY,
                sequencia_id INTEGER NOT NULL,
                operacao_id INTEGER NOT NULL,
                ordem INTEGER DEFAULT 0,
                tempo_padrao REAL DEFAULT 0,
                equipamento_id INTEGER,
                FOREIGN KEY(sequencia_id) REFERENCES sequencias_banco(id),
                FOREIGN KEY(operacao_id) REFERENCES operacoes(id)
            )""")
        except Exception:
            pass
        try:
            c.execute("""CREATE TABLE IF NOT EXISTS notas_fiscais (
                id SERIAL PRIMARY KEY,
                numero TEXT,
                data TEXT,
                cliente TEXT,
                fabrica_id INTEGER,
                valor REAL DEFAULT 0,
                ops_vinculadas TEXT,
                obs TEXT,
                FOREIGN KEY(fabrica_id) REFERENCES fabricas(id)
            )""")
        except Exception:
            pass
        try:
            c.execute("""CREATE TABLE IF NOT EXISTS despesas_docs (
                id SERIAL PRIMARY KEY,
                numero TEXT,
                data TEXT,
                fornecedor TEXT,
                categoria_id INTEGER,
                fabrica_id INTEGER,
                valor REAL DEFAULT 0,
                obs TEXT,
                FOREIGN KEY(fabrica_id) REFERENCES fabricas(id)
            )""")
        except Exception:
            pass
    else:
        try:
            c.execute("ALTER TABLE funcionarios ADD COLUMN bonificacao REAL DEFAULT 0")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE funcionarios ADD COLUMN ifood REAL DEFAULT 0")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE funcionarios ADD COLUMN matricula INTEGER")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE operacoes ADD COLUMN modelo TEXT DEFAULT ''")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE funcoes ADD COLUMN ativa INTEGER DEFAULT 1")
            c.execute("UPDATE funcoes SET ativa=1 WHERE ativa IS NULL")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE faturamento ADD COLUMN numero_nf TEXT DEFAULT ''")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE faturamento ADD COLUMN tipo TEXT DEFAULT 'CONCLUIDA'")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE despesas ADD COLUMN data TEXT")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE despesas ADD COLUMN tipo TEXT DEFAULT 'FIXA'")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE despesas ADD COLUMN numero_doc TEXT DEFAULT ''")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE despesas ADD COLUMN fornecedor TEXT DEFAULT ''")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE despesas ADD COLUMN foto TEXT")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE despesas_docs ADD COLUMN foto TEXT")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE notas_fiscais ADD COLUMN foto TEXT")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE ordens_producao ADD COLUMN data_entrega_costura TEXT")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE ordens_producao ADD COLUMN data_entrega_status TEXT DEFAULT 'verde'")
        except Exception:
            pass
        try:
            c.execute("""CREATE TABLE IF NOT EXISTS lancamentos_fila (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                op_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                fabrica_id INTEGER NOT NULL,
                data_hora TEXT NOT NULL,
                quantidade INTEGER DEFAULT 0,
                meta_ciclo INTEGER DEFAULT 0,
                FOREIGN KEY(op_id) REFERENCES ordens_producao(id),
                FOREIGN KEY(user_id) REFERENCES usuarios(id)
            )""")
        except Exception:
            pass
        try:
            c.execute("""CREATE TABLE IF NOT EXISTS contas_pagar (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fabrica_id INTEGER,
                categoria_id INTEGER,
                fornecedor TEXT,
                descricao TEXT,
                valor_total REAL DEFAULT 0,
                num_parcelas INTEGER DEFAULT 1,
                data_lancamento TEXT,
                obs TEXT,
                criado_em TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY(fabrica_id) REFERENCES fabricas(id),
                FOREIGN KEY(categoria_id) REFERENCES categorias_despesa(id)
            )""")
        except Exception:
            pass
        try:
            c.execute("""CREATE TABLE IF NOT EXISTS contas_pagar_parcelas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conta_id INTEGER NOT NULL,
                numero INTEGER DEFAULT 1,
                valor REAL DEFAULT 0,
                data_vencimento TEXT,
                status TEXT DEFAULT 'PENDENTE',
                data_pagamento TEXT,
                foto TEXT,
                FOREIGN KEY(conta_id) REFERENCES contas_pagar(id)
            )""")
        except Exception:
            pass
        try:
            c.execute("""CREATE TABLE IF NOT EXISTS ref_sequencia (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referencia_id INTEGER NOT NULL,
                operacao_id INTEGER NOT NULL,
                ordem INTEGER DEFAULT 0,
                equipamento_id INTEGER,
                funcionario_id INTEGER,
                tempo_padrao REAL DEFAULT 0,
                FOREIGN KEY(referencia_id) REFERENCES referencias(id),
                FOREIGN KEY(operacao_id) REFERENCES operacoes(id)
            )""")
        except Exception:
            pass
        try:
            c.execute("""CREATE TABLE IF NOT EXISTS fila_estado (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                turno_id INTEGER,
                dt_inicio TEXT,
                minutos INTEGER DEFAULT 540,
                hora_entrada TEXT DEFAULT '07:00',
                hora_saida TEXT DEFAULT '17:30',
                fila_json TEXT DEFAULT '[]',
                atualizado TEXT,
                UNIQUE(user_id)
            )""")
        except Exception:
            pass
        try:
            c.execute("""CREATE TABLE IF NOT EXISTS operacao_tempos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operacao_id INTEGER NOT NULL,
                funcionario_id INTEGER NOT NULL,
                tempo REAL NOT NULL,
                criado_em TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY(operacao_id) REFERENCES operacoes(id),
                FOREIGN KEY(funcionario_id) REFERENCES funcionarios(id)
            )""")
        except Exception:
            pass
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

def _ins(sql, conflict=''):
    """Monta INSERT com ON CONFLICT para PG ou OR IGNORE para SQLite."""
    if PG_MODE:
        return sql + (' ON CONFLICT DO NOTHING' if conflict else '')
    else:
        return sql.replace('INSERT INTO', 'INSERT OR IGNORE INTO')


def seed():
    c = conn()
    if c.execute("SELECT COUNT(*) FROM fabricas").fetchone()[0] == 0:
        fabricas_nomes = [
            ('Giassi Confeccoes', 'Icara'),
            ('Icara Confeccoes',  'Icara'),
            ('Luiza Confeccoes',  'Icara'),
            ('DP Confeccoes',     'Icara'),
        ]
        for nome, cidade in fabricas_nomes:
            c.execute("INSERT INTO fabricas (nome,cidade) VALUES (?,?)", (nome, cidade))
        c.commit()

        # Busca os IDs reais das fábricas após commit
        fab_rows = c.execute("SELECT id, nome FROM fabricas ORDER BY id").fetchall()
        prefixos_map = {
            'Giassi Confeccoes': 'giassi',
            'Icara Confeccoes':  'icara',
            'Luiza Confeccoes':  'luiza',
            'DP Confeccoes':     'dp',
        }

        c.execute(_ins("INSERT INTO usuarios (nome,login,senha_hash,perfil) VALUES (?,?,?,?)", True),
                  ('Administrador', 'admin', hash_senha('admin123'), 'admin'))

        for row in fab_rows:
            fab_id = row[0]
            fab_nome = row[1]
            prefixo = prefixos_map.get(fab_nome, fab_nome.lower().split()[0])
            usuarios_fab = [
                (f'Gestor {prefixo.capitalize()}',     f'{prefixo}.gestor', 'gestor'),
                (f'Operador {prefixo.capitalize()} 1', f'{prefixo}.op1',    'operador'),
                (f'Operador {prefixo.capitalize()} 2', f'{prefixo}.op2',    'operador'),
                (f'Operador {prefixo.capitalize()} 3', f'{prefixo}.op3',    'operador'),
            ]
            for nome, login, perfil in usuarios_fab:
                c.execute(
                    _ins("INSERT INTO usuarios (nome,login,senha_hash,perfil,fabrica_id,ativo) VALUES (?,?,?,?,?,1)", True),
                    (nome, login, hash_senha('giassi123'), perfil, fab_id)
                )

    if c.execute("SELECT COUNT(*) FROM categorias_despesa").fetchone()[0] == 0:
        for i, nome in enumerate(DESPESAS_PADRAO):
            c.execute(_ins("INSERT INTO categorias_despesa (nome,ordem) VALUES (?,?)", True), (nome, i))

    if c.execute("SELECT COUNT(*) FROM generos_produto").fetchone()[0] == 0:
        for g in ['FEMININO', 'MASCULINO', 'INFANTIL', 'ADULTO']:
            c.execute(_ins("INSERT INTO generos_produto (nome) VALUES (?)", True), (g,))

    if c.execute("SELECT COUNT(*) FROM tipos_produto").fetchone()[0] == 0:
        for t in ['SHORTS', 'CALCA', 'LEG', 'VESTIDO', 'BLUSA', 'CAMISETA', 'SAIA', 'MACACAO']:
            c.execute(_ins("INSERT INTO tipos_produto (nome) VALUES (?)", True), (t,))

    if c.execute("SELECT COUNT(*) FROM funcoes").fetchone()[0] == 0:
        for f in ['COSTUREIRA', 'CORTADOR(A)', 'REVISORA', 'AUXILIAR',
                  'ENCARREGADO(A)', 'SUPERVISOR(A)', 'GERENTE']:
            c.execute(_ins("INSERT INTO funcoes (nome) VALUES (?)", True), (f,))

    c.commit()
    c.close()


# Cálculos
def hm(s):
    try:
        h, m = s.split(':')
        return int(h) * 60 + int(m)
    except:
        return 0

def mh(m):
    return f"{int(m)//60:02d}:{int(m)%60:02d}"

def calcular_minutos(he, hsa, hea, hs):
    return max(0, (hm(hsa) - hm(he)) + (hm(hs) - hm(hea)))

def calcular_meta(minutos, tempo_padrao, operadores):
    if tempo_padrao <= 0:
        return 0
    return (minutos / tempo_padrao) * operadores

def calcular_meta_ciclo(meta_dia, minutos_dia, ciclo):
    if ciclo <= 0 or minutos_dia <= 0:
        return 0
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
