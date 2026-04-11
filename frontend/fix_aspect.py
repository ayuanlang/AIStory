
with open(r'c:\AIStory\frontend\src\pages\editor\components\ShotsView.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

old = "const aspectParts = parseAspectRatioParts(project?.aspect_ratio || '16:9');"
new = "const aspectParts = parseAspectRatioParts(getProjectPreferredAspectRatio(project?.global_info, activeEpisode?.episode_info) || '16:9');"

if old in text:
    text = text.replace(old, new)
    with open(r'c:\AIStory\frontend\src\pages\editor\components\ShotsView.jsx', 'w', encoding='utf-8') as f:
        f.write(text)
    print('Fixed isPortrait bug!')
else:
    print('Not found')

