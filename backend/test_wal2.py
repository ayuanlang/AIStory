import sqlite3, os
from threading import Thread

db = "test.db"
c1 = sqlite3.connect(db, timeout=2)
c1.execute("PRAGMA journal_mode=WAL")
c1.execute("BEGIN EXCLUSIVE") # Gets exclusive lock

def test_writer():
    try:
        c2 = sqlite3.connect(db, timeout=2)
        c2.execute("INSERT INTO t VALUES (3)")
        c2.commit()
        print("Success 2")
    except Exception as e:
        print("Writer error 2:", e)

t = Thread(target=test_writer)
t.start()
t.join()

