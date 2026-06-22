import psycopg2
DSN = "postgresql://aistory_user:857R3uszoXImWFYBNC2wNTtXNoc0fpIt@dpg-d61o097gi27c73es1jo0-a.oregon-postgres.render.com/aistory_tm6i"
EP = 722
conn = psycopg2.connect(DSN)
cur = conn.cursor()
cur.execute("SELECT id FROM scenes WHERE episode_id=%s", (EP,))
scene_ids = [r[0] for r in cur.fetchall()]
print("before scenes", len(scene_ids), scene_ids)
if scene_ids:
    cur.execute("DELETE FROM shots WHERE scene_id = ANY(%s)", (scene_ids,))
    print("deleted shots", cur.rowcount)
    cur.execute("DELETE FROM scenes WHERE episode_id=%s", (EP,))
    print("deleted scenes", cur.rowcount)
cur.execute("DELETE FROM script_progress_scene_units WHERE episode_id=%s", (EP,))
print("deleted progress units", cur.rowcount)
cur.execute("""
UPDATE episodes SET
  ai_scene_analysis_result='',
  ai_scene_analysis_scene_markdown='',
  ai_scene_analysis_subject_index='',
  ai_scene_analysis_adaptation='',
  ai_entity_design_result='',
  ai_stage_outputs=''
WHERE id=%s
""", (EP,))
print("cleared episode analysis fields", cur.rowcount)
conn.commit()
cur.execute("SELECT count(*) FROM scenes WHERE episode_id=%s", (EP,))
print("after scene count", cur.fetchone()[0])
conn.close()
