import sqlite3
c = sqlite3.connect('data/chrona.db')

# Adicionar colunas faltantes na tabela despesas
for col, tipo in [('data','TEXT'),('tipo',"TEXT DEFAULT 'FIXA'"),('numero_doc','TEXT'),('fornecedor','TEXT')]:
    try:
        c.execute(f"ALTER TABLE despesas ADD COLUMN {col} {tipo}")
        print(f'{col} adicionado')
    except: print(f'{col} ja existe')

# Criar tabela despesas_docs
c.execute("""
CREATE TABLE IF NOT EXISTS despesas_docs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    numero TEXT NOT NULL,
    data TEXT NOT NULL,
    fornecedor TEXT,
    categoria_id INTEGER,
    fabrica_id INTEGER,
    valor REAL DEFAULT 0,
    obs TEXT,
    criado_em TEXT DEFAULT (datetime('now','localtime')),
    FOREIGN KEY(categoria_id) REFERENCES categorias_despesa(id),
    FOREIGN KEY(fabrica_id) REFERENCES fabricas(id)
)
""")
print('Tabela despesas_docs criada')

c.commit(); c.close()
print('OK!')
