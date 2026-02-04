import sqlite3
import os

db_path = "aistory.db"
if not os.path.exists(db_path):
    print("DB not found at", db_path)
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("--- Checking 'scenes' table schema ---")
cursor.execute("PRAGMA table_info(scenes)")
columns_info = cursor.fetchall()
# PRAGMA table_info returns: (cid, name, type, notnull, dflt_value, pk)
column_names = [info[1] for info in columns_info]

print(f"Columns found ({len(column_names)}):")
for col in column_names:
    print(f" - {col}")

expected_columns = [
    "id", "episode_id", "scene_number", "title", "location", 
    "time_of_day", "description", "core_goal", "environment_anchor", 
    "linked_characters", "key_props"
]

removed_columns = [
    "equivalent_duration", "core_conflict", "visual_foreshadowing", "three_act_structure"
]

all_good = True
print("\n--- Verification ---")
# Check for presence of expected columns
for col in expected_columns:
    if col in column_names:
        print(f"[OK] Found expected column: {col}")
    else:
        print(f"[FAIL] Missing expected column: {col}")
        all_good = False

# Check for absence of removed columns
for col in removed_columns:
    if col not in column_names:
        print(f"[OK] Removed column is gone: {col}")
    else:
        print(f"[FAIL] unwanted column still exists: {col}")
        all_good = False

if all_good:
    print("\nSUCCESS: Schema update verified successfully.")
else:
    print("\nFAILURE: Schema verification failed.")

conn.close()
