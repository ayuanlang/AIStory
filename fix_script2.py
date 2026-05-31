import sys
path = 'c:/AS/AIStory/backend/app/api/endpoints.py'
with open(path, 'r', encoding='utf-8') as f:
    txt = f.read()

txt = txt.replace('("characters", "props", "environments", "covers")', '("characters", "props", "environments", "covers", "posters")')
txt = txt.replace('["characters", "props", "environments", "covers"]', '["characters", "props", "environments", "covers", "posters"]')
txt = txt.replace('{"environments", "covers"}', '{"environments", "covers", "posters"}')

# Wait, check if there's any ("characters", "props", "environments", "covers", "posters") generated already:
# no harm since replace is exact

with open(path, 'w', encoding='utf-8') as f:
    f.write(txt)
print("Done")