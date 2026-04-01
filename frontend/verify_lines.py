import io, sys, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

with open('src/pages/ProjectList.jsx', 'r', encoding='utf-8') as f:
    lines = f.readlines()

print("Lines around 129 to 135:")
for i in range(128, 133):
    print(f"{i+1}: {repr(lines[i])}")

