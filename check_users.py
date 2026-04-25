import psycopg2

try:
    conn = psycopg2.connect("postgresql://aistory_user:857R3uszoXImWFYBNC2wNTtXNoc0fpIt@dpg-d61o097gi27c73es1jo0-a.oregon-postgres.render.com/aistory_tm6i")
    cur = conn.cursor()
    cur.execute('SELECT email, is_active FROM users LIMIT 10')
    print("Users:", cur.fetchall())
except Exception as e:
    print(e)
