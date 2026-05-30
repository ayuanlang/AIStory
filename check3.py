import glob

# frontend JS files
files = glob.glob('frontend/src/**/*.js*', recursive=True)
for f in files:
    with open(f, 'r', encoding='utf-8') as fp:
        lines = fp.readlines()
        for i, line in enumerate(lines):
            if 'negative' in line.lower() and ('+' in line or 'concat' in line or '`' in line):
                print('FE:', f, i+1, line.strip()[:100])

# backend PY files
files = glob.glob('backend/**/*.py', recursive=True)
for f in files:
    with open(f, 'r', encoding='utf-8') as fp:
        lines = fp.readlines()
        for i, line in enumerate(lines):
            if 'negative' in line.lower() and ('+' in line or 'append' in line or 'f"' in line or "f'" in line or '%s' in line):
                print('BE:', f, i+1, line.strip()[-100:])
