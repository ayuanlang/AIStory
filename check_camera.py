import re

with open(r'c:\AS\AIStory\backend\app\core\prompts\skills\shot_generation.md', 'r', encoding='utf-8') as f:
    text = f.read()

# Check what the transitions say
idx1 = text.find('#### 时空转场与特殊场景过渡')
idx2 = text.find('#### 正常时空转场：场景')
print(text[idx2:idx2+1500])

