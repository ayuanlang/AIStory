import os
with open('backend/app/api/settings.py', 'r', encoding='utf-8', errors='ignore') as file:
    text = file.read()
text = text.replace('"generate_videos", "script_analysis", "subject_image_analysis"', '"generate_videos", "script_analysis", "subject_image_analysis", "ai_shot"')
with open('backend/app/api/settings.py', 'w', encoding='utf-8') as file:
    file.write(text)
print("Done")
