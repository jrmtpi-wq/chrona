import sqlite3
c = sqlite3.connect('data/chrona.db')
c.execute("UPDATE fabricas SET nome='Giassi Confeccoes' WHERE id=1")
c.execute("UPDATE fabricas SET nome='Icara Confeccoes' WHERE id=2")
c.execute("UPDATE fabricas SET nome='Luiza Confeccoes' WHERE id=3")
c.execute("UPDATE fabricas SET nome='DP Confeccoes' WHERE id=4")
c.commit()
c.close()
print('OK!')