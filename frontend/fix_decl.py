import re
with open(r'c:\AIStory\frontend\src\pages\editor\components\ShotsView.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

old = '''    const isPortrait = aspectParts && aspectParts.heightPart > aspectParts.widthPart;
    const { generationConfig, saveToolConfig, savedToolConfigs, llmConfig } = useStore();'''
new = '''    const isPortrait = aspectParts && aspectParts.heightPart > aspectParts.widthPart;
    const mediaAspectStyle = isPortrait ? { aspectRatio: aspectParts.widthPart + "/" + aspectParts.heightPart } : undefined;
    const { generationConfig, saveToolConfig, savedToolConfigs, llmConfig } = useStore();'''

if old in text:
    text = text.replace(old, new)
    with open(r'c:\AIStory\frontend\src\pages\editor\components\ShotsView.jsx', 'w', encoding='utf-8') as f:
        f.write(text)
    print("Added mediaAspectStyle")
else:
    print("Not found old string")
