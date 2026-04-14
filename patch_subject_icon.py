import re

with open('frontend/src/pages/editor/components/SubjectLibrary.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    '''className="absolute top-2 left-2 z-30 inline-flex items-center gap-1 rounded bg-amber-500/90 text-amber-950 px-1.5 py-0.5 text-[10px] font-bold shadow"''',
    '''className="absolute bottom-2 left-2 z-30 inline-flex items-center gap-1 rounded bg-amber-500/90 text-amber-950 px-1.5 py-0.5 text-[10px] font-bold shadow"'''
)

with open('frontend/src/pages/editor/components/SubjectLibrary.jsx', 'w', encoding='utf-8') as f:
    f.write(content)
print('Subject icon position patched')
