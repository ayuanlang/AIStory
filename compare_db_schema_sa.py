import os
from sqlalchemy import create_engine, inspect

# 1. Local URL (SQLite or Postgres)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), 'backend'))
local_url = os.environ.get('DATABASE_URL', f"sqlite:///{BASE_DIR}/aistory.db")
if local_url.startswith("postgres://"):
    local_url = local_url.replace("postgres://", "postgresql://", 1)

# 2. Remote URL
remote_url = 'postgresql://aistory_user:857R3uszoXImWFYBNC2wNTtXNoc0fpIt@dpg-d61o097gi27c73es1jo0-a.oregon-postgres.render.com/aistory_tm6i'

def get_schema(url):
    try:
        engine = create_engine(url)
        inspector = inspect(engine)
        
        schema = {}
        for table_name in inspector.get_table_names():
            columns = inspector.get_columns(table_name)
            schema[table_name] = {col['name']: str(col['type']) for col in columns}
        return schema
    except Exception as e:
        print(f"Error connecting to {url}:\n{e}")
        return None

print(f"Analyzing Local DB: {local_url}")
local_schema = get_schema(local_url)

print(f"Analyzing Remote DB...")
remote_schema = get_schema(remote_url)

if local_schema is None or remote_schema is None:
    print("Could not retrieve both schemas.")
    import sys
    sys.exit(1)

print('\n=== Missing Tables ===')
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
    print('No tables missing in Local.')

print('\n=== Column Differences for Shared Tables ===')
for table in sorted(local_tables.intersection(remote_tables)):
    local_cols = set(local_schema[table].keys())
    remote_cols = set(remote_schema[table].keys())
    
    missing_in_remote_cols = local_cols - remote_cols
    missing_in_local_cols = remote_cols - local_cols
    
    if missing_in_remote_cols:
        print(f"Table '{table}' -> Missing in Remote: {', '.join(missing_in_remote_cols)}")
        
    if missing_in_local_cols:
        print(f"Table '{table}' -> Missing in Local: {', '.join(missing_in_local_cols)}")
        
    # Check type differences (basic string matching, might have false positives due to SQLite vs Postgres types)
    for col in sorted(local_cols.intersection(remote_cols)):
        ltype = local_schema[table][col]
        rtype = remote_schema[table][col]
        # Ignore minor SQLAlchemy type string differences for DB specific types like VARCHAR vs VARCHAR(255) if one is just VARCHAR. But we output it to review
        # Only report if they look significantly different to aid in debugging.
        if "JSON" in ltype and "VARCHAR" in rtype:
             print(f"Table '{table}', col '{col}' -> Type mismatch: Local({ltype}) vs Remote({rtype})")
