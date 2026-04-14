import sqlite3, os
from threading import Thread

db = "test.db"
if os.path.exists(db): os.remove(db)

c1 = sqlite3.connect(db, timeout=2)
c1.execute("PRAGMA journal_mode=WAL")
c1.execute("CREATE TABLE t (id INT)")
c1.execute("INSERT INTO t VALUES (1)")
c1.commit()

c1.execute("BEGIN DEFERRED")
c1.execute("SELECT * FROM t").fetchall() # Gets shared lock

def test_writer():
    try:
        c2 = sqlite3.connect(db, timeout=2)
        c2.execute("INSERT INTO t VALUES (2)")
        c2.commit()
        print("Success")
    except Exception as e:
        print("Writer error:", e)

t = Thread(target=test_writer)
t.start()
t.join()

