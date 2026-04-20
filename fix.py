with open('backend/app/api/endpoints.py', 'r', encoding='utf-8') as f:
    t = f.read()
t = t.replace('\"\"\"Async', '\"\"\"Async').replace('\"\"\"\\n    safe', '\"\"\"\\n    safe')
t = t.replace('\\\"\\\"\\\"Async', '\"\"\"Async').replace('\\\"\\\"\\\"\\n', '\"\"\"\\n')
with open('backend/app/api/endpoints.py', 'w', encoding='utf-8') as f:
    f.write(t)
