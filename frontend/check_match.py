import io, sys, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

with open('src/pages/ProjectList.jsx', 'r', encoding='utf-8') as f:
    text1 = f.read()

with open('src/pages/editor/projectOptionConfig.js', 'r', encoding='utf-8') as f:
    text2 = f.read()

p1 = re.search(r'PROJECT_EP_VIDEO_GEN_PREFERENCE_OPTIONS', text1).group(0)
p2 = re.search(r'PROJECT_EP_VIDEO_GEN_PREFERENCE_OPTIONS', text2).group(0)

print("ProjectList.jsx:", repr(p1))
print("projectOptionConfig.js:", repr(p2))
print("Match?", p1 == p2)
