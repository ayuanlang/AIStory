import sqlite3

c = sqlite3.connect("aistory.db")
cur = c.cursor()

r = cur.execute(
    "select id, name, category, provider, model, length(coalesce(api_key, '')), base_url "
    "from system_api_settings where id = 113"
).fetchone()
print("row113", r)

# nearest ids
print(
    "around113",
    cur.execute(
        "select id, provider, model, category, length(coalesce(api_key, '')) "
        "from system_api_settings where id between 100 and 130 order by id"
    ).fetchall(),
)

print(
    "user_settings_pointing_113",
    cur.execute(
        "select id, user_id, category, system_api_id, mode from api_settings where system_api_id = 113"
    ).fetchall(),
)

print(
    "active_llm_user_settings",
    cur.execute(
        "select id, user_id, category, system_api_id, mode from api_settings where category = 'LLM' order by id desc limit 20"
    ).fetchall(),
)

# resolve what those system ids are
ids = [row[3] for row in cur.execute(
    "select id, user_id, category, system_api_id, mode from api_settings where category = 'LLM' order by id desc limit 20"
).fetchall()]
for sid in ids:
    if not sid:
        continue
    s = cur.execute(
        "select id, provider, model, length(coalesce(api_key, '')), base_url from system_api_settings where id = ?",
        (sid,),
    ).fetchone()
    print("system", sid, "->", s)

print(
    "task_defaults",
    cur.execute("select * from system_task_default_apis").fetchall(),
)

# search model name
print(
    "luna models",
    cur.execute(
        "select id, provider, model, category from system_api_settings where model like '%luna%' or model like '%gpt-5.6%'"
    ).fetchall(),
)
