import json

with open('frontend/src/pages/ProjectList.jsx', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "Scene Analysis Dimensions" in line or "Sharing and Review Settings" in line or "Collaborators" in line:
        print(f"Line {i+1}: {line.strip()}")
