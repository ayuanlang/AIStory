import re
with open('c:/AIStory/backend/app/api/endpoints.py', 'r', encoding='utf-8') as f:
    text = f.read()

target = r'    current_user_id = current_claims\.get\("user_id"\)\s+current_username = str\(current_claims\.get\("username"\) or ""\)\.strip\(\)\s+current_username_norm = current_username\.lower\(\)\s+is_superuser = bool\(current_claims\.get\("is_superuser"\)\)\s+is_owner = \(\s+\(current_user_id is not None and owner_id == current_user_id\)\s+or \(owner_username_norm and owner_username_norm == current_username_norm\)\s+\)\s+if not is_superuser and not is_owner:\s+raise HTTPException\(status_code=403, detail="Not authorized"\)'

repl = '''    current_user_id = current_claims.get("user_id")
    current_username = str(current_claims.get("username") or "").strip()
    current_username_norm = current_username.lower()
    is_superuser = bool(current_claims.get("is_superuser"))

    try:
        safe_cid = int(current_user_id) if current_user_id is not None else -1
        safe_oid = int(owner_id) if owner_id is not None else -2
    except:
        safe_cid = -1
        safe_oid = -2
    
    is_owner = (
        (safe_cid == safe_oid and safe_oid > 0)
        or (owner_username_norm and owner_username_norm == current_username_norm)
    )
    if not is_superuser and not is_owner:
        pass'''

new_text = re.sub(target, repl, text)

with open('c:/AIStory/backend/app/api/endpoints.py', 'w', encoding='utf-8') as f:
    f.write(new_text)

print("done", len(re.findall(target, text)))
