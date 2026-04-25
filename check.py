import re
print('\n'.join(set(re.findall(r'status=[\"\'']([^\"''\\]+)', open('c:/AS/AIStory/backend/app/api/endpoints.py', encoding='utf-8').read()))))
