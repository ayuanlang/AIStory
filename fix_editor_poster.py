import re

file_path = r"C:\AS\AIStory\frontend\src\pages\Editor.jsx"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

old_block = """                    // Posters
                    const resolvedPosters = (data.posters && Array.isArray(data.posters)) ? data.posters : ((data.covers && Array.isArray(data.covers)) ? data.covers : null);
                    if (resolvedPosters) {"""

new_block = """                    // Posters
                    const resolvedPosters = (data.posters && Array.isArray(data.posters) && data.posters.length > 0) ? data.posters : ((data.covers && Array.isArray(data.covers) && data.covers.length > 0) ? data.covers : null);
                    if (resolvedPosters) {"""

content = content.replace(old_block, new_block)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Patched Editor.jsx!")
