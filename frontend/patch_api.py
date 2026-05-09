import re

with open(r'c:\AS\AIStory\frontend\src\services\api.js', 'r', encoding='utf-8') as f:
    text = f.read()

funcs = """
export const generateEntityFromText = async (projectId, textDesc, model = null) => {
    const formData = new FormData();
    formData.append('text_desc', textDesc);
    if (model) formData.append('model', model);
    const response = await instance.post(/projects//entities/llm-text, formData);
    return response.data;
};

export const generateEntityFromImage = async (projectId, imageFile, model = null) => {
    const formData = new FormData();
    formData.append('file', imageFile);
    if (model) formData.append('model', model);
    const response = await instance.post(/projects//entities/llm-image, formData);
    return response.data;
};

export const generateEntityDerived = async (projectId, baseEntityId, deriveDesc, model = null) => {
    const formData = new FormData();
    formData.append('base_entity_id', baseEntityId);
    formData.append('derive_desc', deriveDesc);
    if (model) formData.append('model', model);
    const response = await instance.post(/projects//entities/llm-derive, formData);
    return response.data;
};
"""

if 'generateEntityFromText' not in text:
    # append to bottom
    text += "\n" + funcs
    with open(r'c:\AS\AIStory\frontend\src\services\api.js', 'w', encoding='utf-8') as f:
        f.write(text)
    print("Patched api.js")
else:
    print("api.js already patched")

