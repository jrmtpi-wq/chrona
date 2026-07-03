import sqlite3
c = sqlite3.connect('data/chrona.db')
c.execute("UPDATE fabricas SET nome='Fabrica Matriz' WHERE id=1")
c.execute("UPDATE fabricas SET nome='Fabrica 3' WHERE id=2")
c.execute("UPDATE fabricas SET nome='Fabrica 2' WHERE id=3")
c.execute("UPDATE fabricas SET nome='Fabrica 1' WHERE id=4")
c.commit()
c.close()
print('OK!')
