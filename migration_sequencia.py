# Execute este script UMA VEZ para criar as tabelas no banco
# No terminal: python migration_sequencia.py

import sqlite3

conn = sqlite3.connect('data/chrona.db')
c = conn.cursor()

# Adicionar coluna modelo na tabela operacoes (se não existir)
try:
    c.execute("ALTER TABLE operacoes ADD COLUMN modelo TEXT DEFAULT 'UNIVERSAL'")
    print("✅ Coluna modelo adicionada em operacoes")
except:
    print("ℹ️ Coluna modelo já existe em operacoes")

# Criar tabela sequencias_banco
c.execute("""
CREATE TABLE IF NOT EXISTS sequencias_banco (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    modelo TEXT DEFAULT 'UNIVERSAL',
    tempo_total REAL DEFAULT 0,
    total_ops INTEGER DEFAULT 0,
    criado_por INTEGER,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")
print("✅ Tabela sequencias_banco criada")

# Criar tabela sequencia_banco_ops
c.execute("""
CREATE TABLE IF NOT EXISTS sequencia_banco_ops (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sequencia_id INTEGER NOT NULL,
    operacao_id INTEGER NOT NULL,
    ordem INTEGER DEFAULT 1,
    tempo_padrao REAL DEFAULT 0,
    equipamento_id INTEGER,
    FOREIGN KEY(sequencia_id) REFERENCES sequencias_banco(id),
    FOREIGN KEY(operacao_id) REFERENCES operacoes(id)
)
""")
print("✅ Tabela sequencia_banco_ops criada")

conn.commit()
conn.close()
print("\n🎉 Migration concluída!")
