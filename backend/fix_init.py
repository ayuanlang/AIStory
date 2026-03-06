with open('app/db/init_db.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

TO_DELETE = [
    '"grok-imagine"', '"flux-2"', '"imagen4-fast"', '"imagen4-ultra"', '"ideogram"', '"qwen-image"', '"recraft"', '"topaz"',
    '"kling-v2.1"', '"kling-v2.5"', '"sora2"', '"bytedance-v1-pro"', '"bytedance-v1-lite"', '"hailuo"', '"wan-turbo"', '"grok-imagine-video"'
]

new_lines = []
for line in lines:
    if '_kie_item' in line:
        found = False
        for td in TO_DELETE:
            if td in line:
                found = True
                break
        if not found:
            new_lines.append(line)
        else:
            if '(Canonical)' not in line:
                print('Removing:', line.strip())
            else:
                new_lines.append(line)
    else:
        new_lines.append(line)

with open('app/db/init_db.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
