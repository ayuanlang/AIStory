with open('backend/app/api/endpoints.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('re.compile("^file\\d', 're.compile(r"^file\d')

with open('backend/app/api/endpoints.py', 'w', encoding='utf-8') as f:
    f.write(text)
