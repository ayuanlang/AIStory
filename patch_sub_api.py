import re

with open('c:/AIStory/frontend/src/pages/editor/components/SubjectLibrary.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

# Replace analyzeEntityImage(entity.id)
text = text.replace(
    'await analyzeEntityImage(entity.id)',
    "await analyzeEntityImage(entity.id, 'subject_image_analysis')"
)

with open('c:/AIStory/frontend/src/pages/editor/components/SubjectLibrary.jsx', 'w', encoding='utf-8') as f:
    f.write(text)

with open('c:/AIStory/frontend/src/services/api.js', 'r', encoding='utf-8') as f:
    text = f.read()

# fix analyzeEntityImage in api.js
text = text.replace(
    '''export const analyzeEntityImage = async (entityId, functionName = null, systemApiId = null) => {
    try {
        const response = await api.post(/entities//analyze);''',
    '''export const analyzeEntityImage = async (entityId, functionName = null, systemApiId = null) => {
    try {
        let payload = {};
        if (functionName) {
            payload = { function_name: functionName, system_api_id: Number(localStorage.getItem('func_api_' + functionName)) || systemApiId || null };
        }
        const response = await api.post(/entities//analyze, payload);'''
)

with open('c:/AIStory/frontend/src/services/api.js', 'w', encoding='utf-8') as f:
    f.write(text)

