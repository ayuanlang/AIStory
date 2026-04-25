import psycopg2
import sys
import os

try:
    from dotenv import load_dotenv
    load_dotenv('backend/.env')
except:
    pass

local_url = os.environ.get('DATABASE_URL', 'postgresql://aistory_user:password@localhost:5432/aistory')

remote_url = 'postgresql://aistory_user:857R3uszoXImWFYBNC2wNTtXNoc0fpIt@dpg-d61o097gi27c73es1jo0-a.oregon-postgres.render.com/aistory_tm6i'

def get_schema(url):
    try:
        conn = psycopg2.connect(url)
        cur = conn.cursor()
        cur.execute('''
            SELECT table_name, column_name, data_type 
            FROM information_schema.columns 
            WHERE table_schema = 'public'
            ORDER BY table_name, column_name;
        ''')
        rows = cur.fetchall()
        
        schema = {}
        for table_name, column_name, data_type in rows:
            if table_name not in schema:
                schema[table_name] = {}
            schema[table_name][column_name] = data_type
        return schema
    except Exception as e:
        print(f"Error connecting to {url}: {e}")
        return None

local_schema = get_schema(local_url)
remote_schema = get_schema(remote_url)

if local_schema is None or remote_schema is None:
    print("Could not retrieve schemas.")
    sys.exit(1)

print('=== Missing Tables ===')
local_tables = set(local_schema.keys())
remote_tables = set(remote_schema.keys())

missing_in_remote = local_tables - remote_tables
missing_in_local = remote_tables - local_tables

if missing_in_remote:
    print(f"Tables in Local but missing in Remote:")
    for t in sorted(missing_in_remote):
        print(f"  - {t}")
else:
    print('No tables missing in Remote.')

if missing_in_local:
    print(f"\nTables in Remote but missing in Local:")
    for t in sorted(missing_in_local):
         print(f"  - {t}")
else:
    print('\nNo tables missing in Local.')

print('\n=== Column Differences for Shared Tables ===')
for table in sorted(local_tables.intersection(remote_tables)):
    local_cols = set(local_schema[table].keys())
    remote_cols = set(remote_schema[table].keys())
    
    missing_in_remote_cols = local_cols - remote_cols
    missing_in_local_cols = remote_cols - local_cols
    
    if missing_in_remote_cols:
        print(f"Table {table} - missing in Remote: {', '.join(missing_in_remote_cols)}")
        
    if missing_in_local_cols:
        print(f"Table {table} - missing in Local: {', '.join(missing_in_local_cols)}")
        
    # check type differences
    for col in local_cols.intersection(remote_cols):
        ltype = local_schema[table][col]
        rtype = remote_schema[table][col]
        if ltype != rtype:
            print(f"Table {table} - column {col} type mismatch: Local({ltype}) != Remote({rtype})")
