import csv
from collections import Counter, defaultdict
from pathlib import Path

p = Path(r'c:/storyboard/AIStory/_kie_input_enum_values_catalog.csv')
rows = list(csv.DictReader(p.open('r', encoding='utf-8-sig')))

field_counter = Counter(r['field_path'] for r in rows)

# Manual semantic buckets for analysis
bucket_rules = [
    ('模型与路由', lambda f: f in {'paths.post.model', 'paths.post.fallbackModel'}),
    ('视频时空规格', lambda f: any(k in f for k in ['n_frames', 'duration', 'resolution', 'image_resolution', 'aspectRatio', 'aspect_ratio', 'size', 'image_size', 'upscale_factor', 'acceleration', 'rendering_speed'])),
    ('风格与质量', lambda f: any(k in f for k in ['quality', 'style', 'mode', 'outputFormat', 'output_format', 'safetyTolerance'])),
    ('聊天消息结构', lambda f: f.startswith('Message.')),
    ('工具调用结构', lambda f: f.startswith('Tool.')),
    ('多图与语音', lambda f: any(k in f for k in ['num_images', 'voice'])),
    ('推理控制', lambda f: 'reasoning_effort' in f),
]

bucket_counts = Counter()
bucket_fields = defaultdict(list)
for f, c in field_counter.items():
    matched = False
    for name, fn in bucket_rules:
        if fn(f):
            bucket_counts[name] += c
            bucket_fields[name].append((f, c))
            matched = True
            break
    if not matched:
        bucket_counts['其他'] += c
        bucket_fields['其他'].append((f, c))

print('TOTAL_ROWS', len(rows))
print('UNIQUE_FIELDS', len(field_counter))
print('\nBUCKET_COUNTS')
for k, v in bucket_counts.most_common():
    print(f'- {k}: {v}')

print('\nTOP_FIELDS')
for f, c in field_counter.most_common(20):
    print(f'- {f}: {c}')

# show representative enum values for key fields
interesting = [
    'paths.post.model',
    'paths.post.input.n_frames',
    'paths.post.input.duration',
    'paths.post.input.resolution',
    'paths.post.input.aspect_ratio',
    'paths.post.input.mode',
    'paths.post.input.quality',
    'paths.post.input.style',
    'paths.post.reasoning_effort',
    'Message.role',
    'Tool.type',
]

vals = defaultdict(set)
for r in rows:
    f = r['field_path']
    if f in interesting:
        for x in (r['enum_values'] or '').split(';'):
            x = x.strip()
            if x:
                vals[f].add(x)

print('\nREPRESENTATIVE_ENUMS')
for f in interesting:
    if f in vals:
        arr = sorted(vals[f])
        preview = ', '.join(arr[:15])
        suffix = '' if len(arr) <= 15 else f' ...(+{len(arr)-15})'
        print(f'- {f}: {preview}{suffix}')
