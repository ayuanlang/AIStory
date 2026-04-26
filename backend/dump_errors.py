import sqlite3
db = sqlite3.connect('aistory.db')
c = db.cursor()
c.execute("select action, details from system_logs where details like '%a2c065afa8b74bea9a9f8cee8161bbef%' or details like '%d803c464be4f48688a92a4416019a25f%' or details like '%931dbef7d8e3446ea0075d5fd99d3b2e%'")
for r in c.fetchall():
    print(r[0])
    if r[1]: print(r[1])
    print('---')




