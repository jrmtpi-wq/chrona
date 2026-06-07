"""Executa uma vez para atualizar senhas de todos os usuarios (exceto admin)."""
import models as m

c = m.conn()
nova = m.hash_senha('giassi123')
c.execute("UPDATE usuarios SET senha_hash=? WHERE login != 'admin'", (nova,))
c.commit()
n = c.execute("SELECT COUNT(*) FROM usuarios WHERE login != 'admin'").fetchone()[0]
print(f'Senhas atualizadas: {n} usuarios -> giassi123')
c.close()
