
path = r"c:\AS\AIStory\backend\app\services\media_service.py"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

target = "r\"@(?!(?:Image\\\\d+\\\\b))(?=[A-Za-z0-9_\\\\u4e00-\\\\u9fff])\""
replacement = "r\"@(?!(?:Image|Video|Vedie|Vedio)\\\\s*\\\\d+)(?=[A-Za-z0-9_\\\\u4e00-\\\\u9fff])\""
text = text.replace(target, replacement)
target_cleaned = "cleaned = re.sub(r\"@(?!(?:Image|Video|Vedie|Vedio)\\\\s*\\\\d+)(?=[A-Za-z0-9_\\\\u4e00-\\\\u9fff])\", \"\", text)"
replacement_cleaned = "cleaned = re.sub(r\"@(?!(?:Image|Video|Vedie|Vedio)\\\\s*\\\\d+)(?=[A-Za-z0-9_\\\\u4e00-\\\\u9fff])\", \"\", text, flags=re.IGNORECASE)"
text = text.replace(target_cleaned, replacement_cleaned)

with open(path, "w", encoding="utf-8") as f:
    f.write(text)
print("Done!")

