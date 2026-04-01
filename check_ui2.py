with open('frontend/src/pages/ProjectList.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

idx = content.find("Scene Analysis Dimensions")
print("Context for Scene Analysis:")
print(content[idx-200:idx+200])

idx_collab = content.find("Collaborators")
print("\nContext for Collaborators:")
print(content[idx_collab-200:idx_collab+200])
