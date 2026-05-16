import codecs

with codecs.open('c:/AS/AIStory/backend/app/api/endpoints.py', 'r', 'utf-8') as f:
    text = f.read()

old_logic = '''            raw_entity_name = str(row.get(" name\) or \\).strip()
 entity_name = raw_entity_name[1:] if raw_entity_name.startswith(\@\) else raw_entity_name
 if not entity_name:
 entity_name = raw_name.lstrip(\@\).strip()'''

new_logic = ''' entity_name = raw_name.lstrip(\@\).strip()'''

text = text.replace(old_logic, new_logic)

with codecs.open('c:/AS/AIStory/backend/app/api/endpoints.py', 'w', 'utf-8') as f:
 f.write(text)
