with open('backend/app/api/endpoints.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('    \\"\\"\\"\\n    safe_kind', '    """\n    safe_kind')

with open('backend/app/api/endpoints.py', 'w', encoding='utf-8') as f:
    f.write(text)
