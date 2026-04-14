with open("app/api/endpoints.py", "r", encoding="utf-8") as f:
    text = f.read()

lines = text.split("\n")
for i in range(5070, min(5150, len(lines))):
    print(f"Line {i+1}: {lines[i]}")
