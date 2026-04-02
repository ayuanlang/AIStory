import re

with open('c:/AIStory/frontend/src/pages/editor/components/ProjectOverview.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

# patch generateProjectCharacterProfile
text = text.replace(
    '''const updated = await generateProjectCharacterProfile(id, {
                name,
                identity,
                body_features: canonBody || '',
                style_tags,
                extra_notes: canonExtra || '',
            });''',
    '''const updated = await generateProjectCharacterProfile(id, {
                name,
                identity,
                body_features: canonBody || '',
                style_tags,
                extra_notes: canonExtra || '',
                function_name: 'generate_subjects',
            });'''
)

with open('c:/AIStory/frontend/src/pages/editor/components/ProjectOverview.jsx', 'w', encoding='utf-8') as f:
    f.write(text)

with open('c:/AIStory/frontend/src/pages/editor/components/SubjectLibrary.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

# SubjectLibrary calls generateProjectCharacterProfile? No wait, SubjectLibrary creates subjects too.
text = text.replace(
    '''const updated = await generateProjectCharacterProfile(project_id, {
                name,
                identity,
                body_features: canonBody || '',
                style_tags,
                extra_notes: canonExtra || '',
            });''',
    '''const updated = await generateProjectCharacterProfile(project_id, {
                name,
                identity,
                body_features: canonBody || '',
                style_tags,
                extra_notes: canonExtra || '',
                function_name: 'generate_subjects',
            });'''
)

with open('c:/AIStory/frontend/src/pages/editor/components/SubjectLibrary.jsx', 'w', encoding='utf-8') as f:
    f.write(text)

