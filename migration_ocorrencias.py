import sqlite3
c = sqlite3.connect('data/chrona.db')

# Criar tabela tipos_ocorrencia
c.execute("""
CREATE TABLE IF NOT EXISTS tipos_ocorrencia (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL UNIQUE,
    horas_padrao REAL DEFAULT 9,
    ativo INTEGER DEFAULT 1
)
""")
print('Tabela tipos_ocorrencia criada')

# Inserir tipos padrão
tipos = [
    ('FALTA', 9),
    ('MEIA FALTA', 4.5),
    ('ATESTADO', 9),
    ('MEIO ATESTADO', 4.5),
    ('FERIAS', 9),
    ('OBITO', 9),
    ('NAO TRABALHADO', 9),
    ('BANCO DE HORA', 9),
    ('B.H. MEIO DIA', 4.5),
    ('SUSPENSAO', 9),
    ('INSS', 9),
    ('LICENCA', 9),
    ('ADVERTENCIA', 0),
]
for nome, horas in tipos:
    try:
        c.execute("INSERT INTO tipos_ocorrencia (nome,horas_padrao) VALUES (?,?)", (nome, horas))
        print(f'Tipo {nome} adicionado')
    except: print(f'Tipo {nome} ja existe')

# Criar tabela ocorrencias
c.execute("""
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
)
""")
print('Tabela ocorrencias criada')

c.commit(); c.close()
print('OK!')
