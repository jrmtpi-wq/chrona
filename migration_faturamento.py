import sqlite3
c = sqlite3.connect('data/chrona.db')

# Adicionar colunas faltantes na tabela faturamento
try:
    c.execute("ALTER TABLE faturamento ADD COLUMN numero_nf TEXT")
    print('numero_nf adicionado')
except: print('numero_nf ja existe')

try:
    c.execute("ALTER TABLE faturamento ADD COLUMN tipo TEXT DEFAULT 'CONCLUIDA'")
    print('tipo adicionado')
except: print('tipo ja existe')

# Criar tabela notas_fiscais
c.execute("""
CREATE TABLE IF NOT EXISTS notas_fiscais (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    numero TEXT NOT NULL,
    data TEXT NOT NULL,
    cliente TEXT,
    fabrica_id INTEGER,
    valor REAL DEFAULT 0,
    ops_vinculadas TEXT,
    obs TEXT,
    criado_em TEXT DEFAULT (datetime('now','localtime')),
    FOREIGN KEY(fabrica_id) REFERENCES fabricas(id)
)
""")
print('Tabela notas_fiscais criada')

c.commit(); c.close()
print('OK!')
