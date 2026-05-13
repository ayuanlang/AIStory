import os
import re

file_path = r'c:\AS\AIStory\frontend\src\pages\editor\components\ShotsView.jsx'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Instead of doing it directly, we will insert code into handleGenerateVideo
insert_code = """
            if (usePrevVideo) {
                const currentIdx = shots.findIndex(s => s.id === targetShotId);
                if (currentIdx > 0) {
                    const prevShot = shots[currentIdx - 1];
                    const prevVideoUrl = prevShot?.video_url;
                    if (prevVideoUrl && !uniqueRefs.includes(prevVideoUrl)) {
                        uniqueRefs.push(prevVideoUrl);
                    }
                }
            }
"""

content = content.replace('const splitReferenceMediaUrls = (urls) => {', insert_code + '\n            const splitReferenceMediaUrls = (urls) => {')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
