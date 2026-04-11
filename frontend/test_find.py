with open(r'c:\AIStory\frontend\src\pages\editor\components\ShotsView.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

search_tag = "t('\u8d77\u59cb\u5e27', 'Start Frame')"
idx = text.find(search_tag)
matches = []
print('Checking: ', idx)
while idx != -1:
    s = text[max(0, idx-100):idx]
    if 'uppercase font-bold' in s:
        matches.append(idx)
    idx = text.find(search_tag, idx+1)
print('Matches:', len(matches))
