# Uma empresa por instalação

A instalação existente consolida todas as unidades em **JTMTPI CONFECÇÕES**.
Preserva IDs, cadastros, OPs, usuários, senhas e históricos; somente o vínculo da
unidade muda. Metas diárias coincidentes são somadas. Turnos e calendários
continuam cadastrados, sem substituir seus horários.

Antes de alterar vínculos, a transação grava as unidades e todos os registros das
tabelas com `fabrica_id` em `consolidacao_fabricas_backup`, registro `id=1`, campo
`dados_json`. Essa cópia contém dados confidenciais e não deve ser exposta por API.
Ela permite recuperar os valores anteriores mediante restauração administrativa;
não substitui um backup integral do banco. Falhas revertem toda a consolidação.
A migração não se repete após o registro de conclusão. No PostgreSQL, a
inicialização dos workers é serializada por advisory lock.

Todas as contas existentes passam a acessar a empresa consolidada, mantendo seus
perfis. Ferramentas antigas de transferência e renomeação de unidades são
desativadas. A chave antiga de sessão é substituída, exigindo novo login.

Para outro cliente, criar um serviço Render e um banco PostgreSQL exclusivos.
Não compartilhar `DATABASE_URL` nem `SECRET_KEY` entre clientes. Configurar:

- `CHRONA_EMPRESA_NOME`: nome da nova empresa.
- `CHRONA_ADMIN_LOGIN`: login inicial, padrão `admin`.
- `CHRONA_ADMIN_SENHA`: senha inicial de pelo menos 12 caracteres.
- `SECRET_KEY`: segredo exclusivo gerado pelo Render.
- `DATABASE_URL`: banco exclusivo da instalação.

O bootstrap cria apenas uma empresa e um administrador em banco vazio. Não
substitui usuários ou senhas existentes. O administrador cadastra as demais
contas. O blueprint `render.yaml` fornece as variáveis para novas instalações;
alterar o arquivo não implica provisionar novos clientes automaticamente.

Validação local: testes de preservação, rollback, idempotência, isolamento de
segredos, inicialização real SQLite, APIs e navegador. O acesso público permite
verificar a marca e o início da nova versão; a conferência individual dos
cadastros reais exige uma sessão autenticada.
