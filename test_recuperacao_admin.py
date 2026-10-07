import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from recuperacao_admin import recuperar_admin, SENHA_HASH, CHAVE
from exclusao_ops import LIMPEZA_TESTES


class TestConnection(sqlite3.Connection):
    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()


class RecuperacaoAdminTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.temp.name) / 'teste.db')
        self.agora = datetime(2026, 10, 7, 18, tzinfo=timezone.utc)
        with self.conn() as c:
            c.executescript('''CREATE TABLE fabricas(id INTEGER PRIMARY KEY,nome TEXT);
                CREATE TABLE usuarios(id INTEGER PRIMARY KEY,login TEXT,perfil TEXT,fabrica_id INTEGER,senha_hash TEXT);
                CREATE TABLE exclusoes_ops_backup(chave TEXT PRIMARY KEY);
                CREATE TABLE producao(id INTEGER PRIMARY KEY,quantidade INTEGER);
                INSERT INTO fabricas VALUES(1,'JTMTPI CONFECÇÕES'),(2,'Outra empresa');
                INSERT INTO usuarios VALUES(1,'admin','admin',1,'antiga'),(2,'gestor','gestor',1,'gestor'),(3,'admin','admin',2,'outra');
                INSERT INTO producao VALUES(1,680);''')
            c.execute('INSERT INTO exclusoes_ops_backup VALUES(?)', (LIMPEZA_TESTES,))

    def tearDown(self):
        self.temp.cleanup()

    def conn(self):
        c = sqlite3.connect(self.db, factory=TestConnection)
        c.row_factory = sqlite3.Row
        return c

    def test_only_requested_admin_once_preserving_production(self):
        self.assertTrue(recuperar_admin(self.conn, agora=self.agora))
        with self.conn() as c:
            self.assertEqual([r['senha_hash'] for r in c.execute('SELECT senha_hash FROM usuarios ORDER BY id')], [SENHA_HASH,'gestor','outra'])
            self.assertEqual(c.execute('SELECT quantidade FROM producao').fetchone()[0], 680)
            self.assertEqual(c.execute('SELECT chave FROM recuperacoes_acesso').fetchone()[0], CHAVE)
            c.execute("UPDATE usuarios SET senha_hash='alterada-pelo-usuario' WHERE id=1")
        self.assertFalse(recuperar_admin(self.conn, agora=self.agora))
        with self.conn() as c:
            self.assertEqual(c.execute('SELECT senha_hash FROM usuarios WHERE id=1').fetchone()[0], 'alterada-pelo-usuario')

    def test_other_installation_and_future_deploy_are_untouched(self):
        self.assertFalse(recuperar_admin(self.conn, agora=datetime(2026,10,8,tzinfo=timezone.utc)))
        with self.conn() as c:
            c.execute('DELETE FROM exclusoes_ops_backup')
        self.assertFalse(recuperar_admin(self.conn, agora=self.agora))
        with self.conn() as c:
            self.assertEqual(c.execute('SELECT senha_hash FROM usuarios WHERE id=1').fetchone()[0], 'antiga')

    def test_ambiguous_account_is_untouched(self):
        with self.conn() as c:
            c.execute("INSERT INTO usuarios VALUES(4,'ADMIN','admin',1,'segunda')")
        self.assertFalse(recuperar_admin(self.conn, agora=self.agora))

    def test_failure_rolls_back_password_and_marker_together(self):
        with self.conn() as c:
            c.executescript('''CREATE TABLE recuperacoes_acesso(chave TEXT PRIMARY KEY,usuario_id INTEGER,criado_em TEXT);
                CREATE TRIGGER abortar BEFORE INSERT ON recuperacoes_acesso BEGIN SELECT RAISE(ABORT,'teste'); END;''')
        with self.assertRaises(sqlite3.IntegrityError):
            recuperar_admin(self.conn, agora=self.agora)
        with self.conn() as c:
            self.assertEqual(c.execute('SELECT senha_hash FROM usuarios WHERE id=1').fetchone()[0], 'antiga')
            self.assertEqual(c.execute('SELECT COUNT(*) FROM recuperacoes_acesso').fetchone()[0], 0)


if __name__ == '__main__':
    unittest.main()
